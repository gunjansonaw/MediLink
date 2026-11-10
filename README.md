# 🏥 MediLink — Enterprise Telehealth & Hospital SaaS Platform

[![Docker Compose](https://img.shields.io/badge/Docker-Compose_Ready-blue.svg?logo=docker)](./docker-compose.yml)
[![Django](https://img.shields.io/badge/Backend-Django_4.2_DRF-092E20.svg?logo=django)](./backend)
[![React](https://img.shields.io/badge/Frontend-React_18_SPA-61DAFB.svg?logo=react)](./frontend)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL_15-336791.svg?logo=postgresql)](./backend)
[![Celery](https://img.shields.io/badge/Async_Queue-Celery_+_Redis-37814A.svg?logo=celery)](./backend/medilink/celery.py)
[![Kubernetes](https://img.shields.io/badge/Deploy-Kubernetes_(kustomize)-326CE5.svg?logo=kubernetes)](./deploy/k8s)
[![Claude](https://img.shields.io/badge/AI_Agents-Claude_API-D97757.svg)](./backend/ai_agents)

**MediLink** is a modern, scalable, containerized SaaS platform engineered for clinical workflows, multi-role hospital management (Patients, Doctors, Administrators), electronic health records (EHR), scheduling, and billing.

---

## 🌟 Key Architecture & SaaS Features

- **Multi-Role Access Control (RBAC):**
  - **Patients:** Book doctor appointments, view diagnosis history, access prescriptions, and process full/partial medical payments.
  - **Doctors:** Manage clinical appointments, record diagnoses, issue prescriptions, and view assigned patient charts.
  - **Hospital Admins:** Monitor platform revenue, oversee appointment metrics, approve insurance claims, and audit platform activity.
- **Enterprise Performance & Query Optimization:**
  - **Zero N+1 Query Overhead:** All DRF ViewSets utilize explicit `select_related()` and `prefetch_related()` joins.
  - **Double-Booking Prevention:** Transactional slot locking prevents overlapping doctor schedules.
  - **Invoice & Partial Payment Tracking:** Supports itemized billing, auto-calculated tax/discounts, instant PDF invoice generation, and status sync (`pending`, `partially_paid`, `paid`).
- **Asynchronous Task Processing:**
  - **Celery + Redis:** Background worker handles automated appointment reminders and hourly overdue invoice reconciliation.
- **Production Containerization:**
  - **Docker Compose:** Orchestrates 6 micro-services (Postgres, Redis, Django API, Celery Worker, Celery Beat, and React Nginx SPA).

---

## 🤖 Agentic AI Features (`backend/ai_agents`)

Agents run on the Claude API (default model `claude-opus-5-5`, configurable with `AI_MODEL`) with a manual tool-use loop. Three rules apply to all of them:
- **RBAC on every tool.** Each agent only sees its user's tools, and every tool re-uses the same data scoping as the REST API.
- **Human in the loop.** Tools that change data (book, cancel, invoice, message) only *propose* an action card. Nothing is written until a person clicks **Approve**, and everything is re-validated at that point.
- **Audit log.** Every tool call is recorded (`AgentToolCall`) and visible in *AI Operations*.

| Agent | Who | What it does |
|---|---|---|
| **Booking assistant** | Patient | "Chest discomfort, cardiologist next week, mornings" → picks the specialty, finds doctors, checks real free slots, proposes a booking for approval. Also explains the patient's own records and bills. |
| **Emergency guardrail** | Patient | Deterministic detection (chest pain + breathlessness, stroke signs, self-harm…) that never calls the model and always tells the patient to call emergency services. |
| **Prescription safety agent** | Doctor | Deterministic engine: allergy cross-reactivity (incl. brand names), drug–drug interactions, duplicate therapy, condition contraindications, age cautions, dose ceilings. Runs **before** saving (blocking modal) and **after** (persisted alerts that need acknowledgement, with a mandatory note for critical alerts). |
| **Pre-visit brief** | Doctor | One-screen summary of history, meds, vitals trends and pending labs, with computed red flags. Pre-generated hourly by Celery for visits in the next 36 hours. |
| **Clinical copilot chat** | Doctor | Patient-history Q&A and medication checks, limited to patients the doctor actually treats. |
| **Lab result explainer** | Patient + Doctor | Flags out-of-range analytes, writes a plain-language, non-diagnostic explanation, notifies the patient, and alerts the doctor on abnormal results. |
| **Operations analyst** | Admin | Natural-language analytics (revenue, no-shows, appointments, outstanding balances) over *parameterised ORM tools* (no free-form SQL), rendered as charts in the chat. |
| **Billing / claims agent** | Admin | Insurance claim pre-check (policy mismatch, missing diagnosis, duplicates, late filing → risk score), invoice drafting from completed visits, patient outreach drafts. |
| **Collections agent** | Celery (daily) | Overdue invoices: gentle reminder → payment-plan offer → escalation to admins. Idempotent and audited. |
| **Care follow-up agent** | Celery (daily) | Nudges chronic-condition patients with no recent visit, and patients with abnormal labs and no follow-up booked. |

**No API key? It still works.** Without `ANTHROPIC_API_KEY` the app runs in *rules-only mode*. The safety engine, briefs, lab flags, claim checks and proactive agents are deterministic, and the chat answers common requests with the same audited tools. Server-side refusal fallback (`fallbacks: "default"`) is enabled on every Claude call.

---

## 🏛 Architecture Diagram

```
┌────────────────────────────────────────────────────────┐
│                   Client Browser                       │
└──────────────┬─────────────────────────┬───────────────┘
               │ Port 3000               │ Port 8000
               ▼                         ▼
    ┌──────────────────────┐  Proxy   ┌──────────────────────┐
    │  React 18 + Nginx    │ ───────> │  Django REST API     │
    │  (Static SPA Server) │  /api/   │  (Gunicorn WSGI)     │
    └──────────────────────┘          └──────────┬───────────┘
                                                 │
                        ┌────────────────────────┼────────────────────────┐
                        ▼                        ▼                        ▼
               ┌────────────────┐       ┌────────────────┐       ┌────────────────┐
               │  PostgreSQL 15 │       │  Redis 7 Cache │ <──── │ Celery Worker  │
               │  (Primary DB)  │       │  & Message Bus │ <──── │ & Celery Beat  │
               └────────────────┘       └────────────────┘       └────────────────┘
```

---

## 🚀 Quickstart (One-Command Docker Compose)

### 1. Clone & Start Containers
Ensure **Docker Desktop** is running, then run:

```bash
# Start all 6 services (Database, Redis, API, Worker, Beat, Frontend)
docker compose up --build -d
```

### 2. Seed Realistic SaaS Demo Data (For Interviews)
Populate the database with pre-configured Doctors, Patients, Appointments, Medical Records, and Billing:

```bash
docker compose exec backend python manage.py seed_demo_data
```

### 3. Access the Platform
- 🌐 **Web Application:** [http://localhost:3000](http://localhost:3000)
- 🔌 **REST API & Swagger Docs:** [http://localhost:8000/api/](http://localhost:8000/api/) · [http://localhost:3000/swagger/](http://localhost:3000/swagger/)
- ⚙️ **Django Admin Portal:** [http://localhost:3000/admin/](http://localhost:3000/admin/)

To enable the Claude-powered agents, set `ANTHROPIC_API_KEY` (e.g. in a `.env` file next to `docker-compose.yml`) before `docker compose up`.

### ☸️ Kubernetes & free cloud hosting
Kustomize manifests for a local kind cluster and for a **free, always-on k3s cluster on Oracle Cloud's Always Free tier** (HTTPS via Let's Encrypt, multi-arch images built by GitHub Actions) live in [`deploy/k8s`](./deploy/k8s). Step-by-step guide: **[DEPLOYMENT.md](./DEPLOYMENT.md)**.

---

## 🔑 Pre-Configured Demo Credentials

Use these credentials to seamlessly demonstrate different user perspectives in interviews:

| Role | Username | Password | Key Responsibilities |
|---|---|---|---|
| **Hospital Admin** | `admin` | `AdminPassword123!` | System statistics, revenue metrics, insurance claim approvals |
| **Cardiologist** | `doctor_sarah` | `DoctorPassword123!` | Patient chart review, clinical record creation, appointments |
| **Pediatrician** | `doctor_james` | `DoctorPassword123!` | Availability schedules, prescription management |
| **Patient 1** | `patient_john` | `PatientPassword123!` | Active hypertension record, partial invoice payment |
| **Patient 2** | `patient_emma` | `PatientPassword123!` | Paid invoices, upcoming scheduled appointments |

---

## 🧪 Service Composition in `docker-compose.yml`

| Service | Technology | Port | Description |
|---|---|---|---|
| `db` | PostgreSQL 15 | `5432` | Relational storage with persistent volume & health check |
| `redis` | Redis 7 Alpine | `6379` | Fast in-memory cache & Celery task queue broker |
| `backend` | Django 4.2 + Gunicorn | `8000` | REST API with automated migrations on boot |
| `celery-worker` | Celery 5.3 | Internal | Background tasks: reminders, lab explanations, pre-visit briefs |
| `celery-beat` | Celery Beat | Internal | Scheduled agents: invoice reconciler, reminders, briefs, collections, care follow-ups |
| `frontend` | React 18 + Nginx (unprivileged) | `3000` | SPA + reverse proxy for `/api/`, `/admin/`, `/django-static/` |

---

## 🛠 Manual Local Development (Without Docker)

### Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows (or source venv/bin/activate on Linux/Mac)
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo_data
python manage.py runserver
python manage.py test          # 45 tests: RBAC, billing, auth cookies, agents, safety engine
```

### Frontend
```bash
cd frontend
npm install --legacy-peer-deps
npm start
```

---

## 🔒 Security Implementations

1. **Privilege Escalation Prevention:** Public registration strictly denies unauthorized `admin` role elevation.
2. **Password Validation:** Enforces complexity checks and confirmation checks across frontend and backend.
3. **Robust DRF Permissions:** Custom permission classes verify authentication state before inspecting user attributes, preventing `AnonymousUser` crashes.
4. **CORS Hardening:** Configurable origin whitelists preventing cross-origin resource exploitation.
5. **Cookie JWT + CSRF:** HttpOnly access/refresh cookies with real refresh-token rotation and blacklisting on logout. CSRF is enforced on every cookie-authenticated request.
6. **Least-privilege data access:** Users only see patients/users they have a relationship with. Payments, claims decisions and invoice edits are admin-only, and payments are locked per invoice to prevent overpayment races.
7. **Hardened containers:** Non-root images, read-only root filesystems, restricted Pod Security Standard, and NetworkPolicies isolating Postgres and Redis.
