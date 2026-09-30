# 🚀 MediLink — Production Deployment & Docker Guide

This guide covers two deployment paradigms:
1. **Docker Compose Orchestration (Local & Self-Hosted / VPS / AWS EC2 / DigitalOcean)**
2. **Cloud Free-Tier Serverless (Railway Backend + PostgreSQL + Vercel Frontend)**

---

## 🐳 Option 1: Docker Compose Deployment (Recommended)

MediLink comes with a production-ready `docker-compose.yml` that orchestrates 6 containerized micro-services:
- `db` (PostgreSQL 15)
- `redis` (Redis 7 In-Memory Queue)
- `backend` (Django 4.2 REST API + Gunicorn WSGI)
- `celery-worker` (Background Async Task Worker)
- `celery-beat` (Scheduled Cron Jobs)
- `frontend` (React 18 SPA served via Alpine Nginx with reverse proxy)

### Quickstart Command

```bash
# 1. Build and boot all containers in detached mode
docker compose up --build -d

# 2. Seed realistic SaaS demonstration data (creates Admin, Doctors, Patients, Records, and Invoices)
docker compose exec backend python manage.py seed_demo_data

# 3. View live aggregate logs
docker compose logs -f
```

### Access Ports
- **Frontend Web UI:** [http://localhost:3000](http://localhost:3000)
- **Django REST API:** [http://localhost:8000/api/](http://localhost:8000/api/)
- **Swagger / OpenAPI Documentation:** [http://localhost:8000/swagger/](http://localhost:8000/swagger/)
- **Django Administration:** [http://localhost:8000/admin/](http://localhost:8000/admin/)

### Useful Docker Maintenance Commands
```bash
# Stop all containers
docker compose down

# Stop and wipe persistent database & cache volumes
docker compose down -v

# Run Django management tests inside container
docker compose exec backend python manage.py test

# Create custom Django superuser inside container
docker compose exec backend python manage.py createsuperuser
```

---

## ☁️ Option 2: 100% Free Forever Cloud Deployment (Neon + Render + Vercel)

This setup is **completely free** with no credit card required:
- **Database:** [Neon.tech](https://neon.tech) (Serverless PostgreSQL — 0.5 GB free storage, never expires)
- **Backend API:** [Render.com](https://render.com) (Free Web Service — 750 free hours/month, automatic HTTPS)
- **Frontend SPA:** [Vercel.com](https://vercel.com) (Free Edge CDN — instant worldwide deployments)

```
┌──────────────┐          ┌───────────────────────┐          ┌─────────────────────────┐
│ React SPA    │ ───────> │ Django REST API       │ ───────> │ Serverless PostgreSQL   │
│ (Vercel)     │ HTTPS    │ (Render Web Service)  │ SSL      │ (Neon.tech)             │
└──────────────┘          └───────────────────────┘          └─────────────────────────┘
```

---

### Step 1: Create Free PostgreSQL Database on Neon
1. Sign up for free at [neon.tech](https://neon.tech) (no credit card required).
2. Click **Create Project** (e.g. name it `medilink-db`).
3. Under **Connection Details**, select **Connection string** (PostgreSQL) and copy the URL:
   ```text
   postgresql://<user>:<password>@<endpoint>.neon.tech/neondb?sslmode=require
   ```

---

### Step 2: Push Your Code to GitHub
Ensure all your latest code is committed and pushed to your GitHub repository:
```bash
git add .
git commit -m "feat: configure cloud deployment files"
git push origin main
```

---

### Step 3: Deploy Django Backend on Render
1. Sign up or log into [render.com](https://render.com).
2. Click **New +** → **Web Service**.
3. Connect your GitHub account and select the `MediLink` repository.
4. Configure the Web Service settings:
   - **Name:** `medilink-backend` (or any name you like)
   - **Region:** Choose closest to your Neon database region (e.g., Frankfurt, Oregon, Singapore)
   - **Branch:** `main`
   - **Root Directory:** `backend`
   - **Runtime:** `Python 3`
   - **Build Command:** `./build.sh` (or `pip install -r requirements.txt && python manage.py collectstatic --no-input && python manage.py migrate`)
   - **Start Command:** `gunicorn medilink.wsgi:application`
   - **Instance Type:** `Free`
5. Scroll down to **Environment Variables** and add:
   | Key | Value | Notes |
   |---|---|---|
   | `DATABASE_URL` | `postgresql://<user>:<pass>@<endpoint>.neon.tech/neondb?sslmode=require` | From Neon |
   | `SECRET_KEY` | *generate a random string of 50 characters* | Security |
   | `DEBUG` | `False` | Production mode |
   | `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Render domain auto-detected |
   | `CORS_ALLOWED_ORIGINS` | `http://localhost:3000` | Will update after Vercel step |
6. Click **Create Web Service**. Wait for the build to finish.
7. Once deployed, note your Render URL (e.g. `https://medilink-backend.onrender.com`).
8. *(Optional)* Seed initial data: Open the Render dashboard → click **Shell** → run:
   ```bash
   python manage.py seed_demo_data
   ```

---

### Step 4: Deploy React Frontend on Vercel
1. Sign up or log in at [vercel.com](https://vercel.com).
2. Click **Add New...** → **Project**.
3. Select your `MediLink` GitHub repository.
4. Configure the project:
   - **Framework Preset:** `Create React App`
   - **Root Directory:** Click `Edit` and select `frontend`
   - **Build Command:** `npm run build` (default)
   - **Output Directory:** `build` (default)
5. Expand **Environment Variables** and add:
   - **Key:** `REACT_APP_API_URL`
   - **Value:** `https://your-render-app.onrender.com/api` *(replace with your actual Render URL + `/api`)*
6. Click **Deploy**. Vercel will build and deploy your React frontend in ~1-2 minutes.
7. Copy your production Vercel URL (e.g., `https://medilink-xxx.vercel.app`).

---

### Step 5: Connect Backend CORS
1. Return to your Render Web Service dashboard → **Environment**.
2. Update the `CORS_ALLOWED_ORIGINS` variable:
   ```text
   https://your-vercel-domain.vercel.app,http://localhost:3000
   ```
3. Click **Save Changes** (Render will redeploy with CORS permissions applied).

---

## ⚡ Free Tier Behavior & Notes
- **Render Cold Start:** Free web services sleep after 15 minutes of inactivity. When a request comes in, it takes ~30-45 seconds to wake up. Once awake, performance is snappy.
- **Neon Storage:** Neon provides 0.5 GB of Postgres storage for free, which easily accommodates tens of thousands of medical records and appointments.
- **Background Tasks (Celery):** On the free web tier, background Celery workers are optional. The web API executes all normal requests synchronously. If you want asynchronous Celery, you can use [Upstash Redis](https://upstash.com) (free 10,000 commands/day) with a local or secondary worker.

---

## 🔑 Interview Demonstration Credentials

| Role | Username | Password | Purpose |
|---|---|---|---|
| **Admin** | `admin` | `AdminPassword123!` | Executive analytics, system audits, claim approvals |
| **Doctor** | `doctor_sarah` | `DoctorPassword123!` | Clinical notes, patient history, prescriptions |
| **Doctor** | `doctor_james` | `DoctorPassword123!` | Pediatric appointments & scheduling |
| **Patient** | `patient_john` | `PatientPassword123!` | Active record, partial invoice payment |
| **Patient** | `patient_emma` | `PatientPassword123!` | Paid invoices, appointment requests |
