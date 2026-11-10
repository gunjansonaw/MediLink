# 🚀 MediLink — Deployment Guide

| Option | What you get | Cost |
|---|---|---|
| [1. Docker Compose](#-option-1-docker-compose-local) | Full stack on your laptop in one command | Free |
| [2. Kubernetes — local (kind)](#-option-2-kubernetes-on-your-laptop-kind) | Same manifests as production, on your laptop | Free |
| [3. Kubernetes — Oracle Cloud Always Free](#%EF%B8%8F-option-3-kubernetes-in-the-cloud-for-free-oracle-cloud-always-free--k3s) **(recommended)** | Real k8s cluster, HTTPS, Celery agents, always-on | **$0 forever** |
| [4. Render + Vercel + Neon](#-option-4-serverless-free-tier-render--vercel--neon-no-kubernetes) | No Kubernetes; sleeps when idle; no background agents | Free |

All options run the AI agents. Without `ANTHROPIC_API_KEY` they fall back to a **rules-only mode**: the safety engine, briefs, lab flags, claim checks and collections all still work. Add a key to turn on the Claude-powered chat agents.

---

## 🐳 Option 1: Docker Compose (local)

```bash
cp .env.example .env              # optional: add ANTHROPIC_API_KEY
docker compose up --build -d
docker compose exec backend python manage.py seed_demo_data
```

| Service | URL |
|---|---|
| Web app (nginx → React + API proxy) | http://localhost:3000 |
| Django REST API / Swagger | http://localhost:8000/api/ · http://localhost:3000/swagger/ |
| Django admin | http://localhost:3000/admin/ |

```bash
docker compose logs -f backend celery-worker      # tail logs
docker compose exec backend python manage.py test # run the test suite
docker compose down -v                            # stop and wipe volumes
```

---

## ☸️ Option 2: Kubernetes on your laptop (kind)

Prereqs: Docker, [`kind`](https://kind.sigs.k8s.io/), `kubectl` ≥ 1.27 (includes kustomize).

```bash
# 1. Cluster with port 80 of the ingress mapped to localhost:8080
kind create cluster --name medilink --config deploy/k8s/overlays/local/kind-config.yaml

# 2. Ingress controller
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.12.0/deploy/static/provider/kind/deploy.yaml
kubectl -n ingress-nginx wait --for=condition=ready pod -l app.kubernetes.io/component=controller --timeout=180s

# 3. Build images and load them into the cluster
docker build -t medilink-backend:local backend
docker build -t medilink-frontend:local frontend
kind load docker-image medilink-backend:local medilink-frontend:local --name medilink

# 4. Deploy (also runs a one-off Job that seeds the demo data)
kubectl apply -k deploy/k8s/overlays/local
kubectl -n medilink get pods -w
```

Open **http://medilink.localtest.me:8080** (`localtest.me` always resolves to 127.0.0.1).
To enable Claude, put your key in `deploy/k8s/overlays/local/local.secrets.env` and re-apply.

---

## ☁️ Option 3: Kubernetes in the cloud for free (Oracle Cloud Always Free + k3s)

Oracle's **Always Free** tier includes an Ampere (arm64) VM with up to **4 OCPUs and 24 GB RAM**, a public IP and 200 GB of storage, with no time limit. That is plenty for a single-node [k3s](https://k3s.io) cluster: a lightweight, CNCF-certified Kubernetes that bundles the Traefik ingress and local-path storage. The CI pipeline builds **multi-arch images** (amd64 + arm64), so the same images run there.

```
Internet ──HTTPS──▶ Traefik Ingress (k3s, Let's Encrypt TLS via cert-manager)
                         │
                         ▼
                 frontend (nginx, 2 pods) ──/api, /admin──▶ backend (Django/Gunicorn)
                                                              │        │
                                         celery-worker ◀──── redis     postgres (StatefulSet + PVC)
                                         celery-beat (AI agents on a schedule)
```

### Step 1 — Create the free VM
1. Sign up at [cloud.oracle.com](https://cloud.oracle.com) (a card is needed for identity checks; Always Free resources are never charged).
2. **Compute → Instances → Create instance**
   - Image: **Ubuntu 22.04 or 24.04**
   - Shape: **Ampere → VM.Standard.A1.Flex**, 2–4 OCPUs, 12–24 GB RAM (all inside the free allowance)
   - Add your SSH public key, then create.
   - *If you get "Out of capacity", try another availability domain or retry later. This is common in popular regions.*
3. **Open ports 80/443 in the cloud firewall:** Networking → Virtual Cloud Networks → your VCN → Security Lists → Default → **Add Ingress Rules**: source `0.0.0.0/0`, TCP, destination ports `80,443`.

### Step 2 — Install k3s + cert-manager (on the VM)
```bash
ssh ubuntu@<PUBLIC_IP>
git clone https://github.com/gunjansonaw/MediLink.git && cd MediLink
LETSENCRYPT_EMAIL=you@example.com sudo -E bash deploy/oracle/bootstrap-k3s.sh
```
The script also opens 80/443 in the VM's own iptables. Oracle's Ubuntu images block them by default, a classic gotcha.

### Step 3 — Publish the container images (once)
Push to `main`. The **CI / CD** workflow (`.github/workflows/ci.yml`) runs the tests and then pushes:
- `ghcr.io/gunjansonaw/medilink-backend:latest` (+ `:<commit sha>`)
- `ghcr.io/gunjansonaw/medilink-frontend:latest` (+ `:<commit sha>`)

Then on GitHub → your profile → **Packages** → each package → *Package settings* → **Change visibility → Public**, so the cluster can pull without credentials.
*(If you fork the repo, change the `ghcr.io/<owner>` names in `deploy/k8s/overlays/oracle/kustomization.yaml`.)*

### Step 4 — Deploy
No domain? [sslip.io](https://sslip.io) gives you one for free: `medilink.<PUBLIC_IP>.sslip.io` resolves to your IP.
```bash
sudo -E MEDILINK_HOST=medilink.$(curl -s ifconfig.me).sslip.io \
     ANTHROPIC_API_KEY=sk-ant-...   `# optional` \
     SEED_DEMO_DATA=1 \
     bash deploy/oracle/deploy.sh
```
The script generates strong `SECRET_KEY`/`DB_PASSWORD` values on first run and keeps them in `deploy/k8s/overlays/oracle/secrets.env`, which is git-ignored. It then applies the manifests and waits for every rollout. After ~1 minute cert-manager has a Let's Encrypt certificate:
```bash
kubectl -n medilink get pods,ingress,certificate
```
Open **https://medilink.&lt;PUBLIC_IP&gt;.sslip.io** 🎉

### Step 5 (optional) — Continuous deployment
Each push to `main` can roll out its own image tag automatically. In GitHub → Settings → *Secrets and variables → Actions*:

| Type | Name | Value |
|---|---|---|
| Variable | `DEPLOY_ENABLED` | `true` |
| Variable | `MEDILINK_HOST` | `medilink.<PUBLIC_IP>.sslip.io` |
| Secret | `KUBE_CONFIG` | `base64 -w0` of the VM's `/etc/rancher/k3s/k3s.yaml`, with `127.0.0.1` replaced by the public IP |
| Secret | `DJANGO_SECRET_KEY`, `DB_PASSWORD` | same values as in the VM's `secrets.env` |
| Secret | `ANTHROPIC_API_KEY` | optional |

For this, also open TCP **6443** in the Security List, ideally only to [GitHub's runner IPs](https://api.github.com/meta) or via a VPN.

### Day-2 operations
```bash
kubectl -n medilink logs deploy/backend -f                  # API logs
kubectl -n medilink logs deploy/celery-beat                 # scheduled AI agents
kubectl -n medilink exec deploy/backend -- python manage.py createsuperuser
kubectl -n medilink exec postgres-0 -- pg_dump -U medilink medilink > backup.sql   # backup
IMAGE_TAG=<sha> bash deploy/oracle/deploy.sh                # roll back / pin a version
```

### What the manifests include (`deploy/k8s/`)
- **base/**: Namespace with the *restricted* Pod Security Standard. Postgres StatefulSet with a PVC, Redis, a backend Deployment (migrations run in an initContainer, plus startup/readiness/liveness probes), Celery worker and beat (`Recreate`, so there is never a double scheduler), frontend nginx, an Ingress, and NetworkPolicies so only Django pods can reach Postgres and Redis. Every container runs as non-root with a read-only root filesystem (except nginx), drops all capabilities, and has resource requests and limits.
- **overlays/local/**: kind/minikube settings, plain HTTP, dev secrets, a demo-data Job.
- **overlays/oracle/**: k3s Traefik + cert-manager TLS + HTTPS redirect, GHCR images, and the host injected from `params.env` via kustomize `replacements`.

---

## 🌐 Option 4: Serverless free tier (Render + Vercel + Neon, no Kubernetes)

Simplest free option. It has limits: the API sleeps after 15 minutes idle, and there are no Celery workers, so the scheduled agents (collections, follow-ups, brief pre-generation) don't run. Tasks triggered by an event still run inline.

1. **Neon** ([neon.tech](https://neon.tech)): create a project and copy the connection string.
2. **Render** ([render.com](https://render.com)): New → Web Service → this repo, Root Directory `backend`, Build `./build.sh`, Start `gunicorn medilink.wsgi:application --timeout 180`, instance type Free. Environment:

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | Neon connection string |
   | `SECRET_KEY` | long random string |
   | `DEBUG` | `False` |
   | `CORS_ALLOWED_ORIGINS` | `https://<your-app>.vercel.app` |
   | `CSRF_TRUSTED_ORIGINS` | `https://<your-app>.vercel.app` |
   | `JWT_AUTH_COOKIE_SAMESITE` | `None` (frontend and API are on different sites) |
   | `CELERY_TASK_ALWAYS_EAGER` | `True` (no broker on the free tier) |
   | `ANTHROPIC_API_KEY` | optional |

   Seed demo data from Render's **Shell**: `python manage.py seed_demo_data`.
3. **Vercel** ([vercel.com](https://vercel.com)): import the repo, Root Directory `frontend`, env `REACT_APP_API_URL=https://<your-render-app>.onrender.com/api`.

> Some browsers (Safari, and Chrome with third-party cookies blocked) refuse cross-site cookies. If login doesn't stick, put both apps behind one domain, or use Option 3, where everything is same-origin.

---

## 🔑 Demo credentials

| Role | Username | Password | Try this |
|---|---|---|---|
| **Admin** | `admin` | `AdminPassword123!` | AI Operations → run the collections agent, pre-check claim 1; ask the assistant for "revenue by month" |
| **Doctor** | `doctor_sarah` | `DoctorPassword123!` | Dashboard → **Brief** on John's visit; prescribe Amoxicillin to John (penicillin allergy) |
| **Doctor** | `doctor_james` | `DoctorPassword123!` | Pediatric schedule |
| **Patient** | `patient_john` | `PatientPassword123!` | Assistant: "book a cardiologist next Monday morning"; lab result → *What does this mean?* |
| **Patient** | `patient_emma` | `PatientPassword123!` | Paid invoices, appointment history |

⚠️ These are public demo passwords. On a public deployment change them, or skip `SEED_DEMO_DATA`, before sharing the URL.
