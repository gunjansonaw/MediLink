# 🏥 MediLink — Enterprise Telehealth & Hospital SaaS Platform

[![Docker Compose](https://img.shields.io/badge/Docker-Compose_Ready-blue.svg?logo=docker)](./docker-compose.yml)
[![Django](https://img.shields.io/badge/Backend-Django_4.2_DRF-092E20.svg?logo=django)](./backend)
[![React](https://img.shields.io/badge/Frontend-React_18_SPA-61DAFB.svg?logo=react)](./frontend)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL_15-336791.svg?logo=postgresql)](./backend)
[![Celery](https://img.shields.io/badge/Async_Queue-Celery_+_Redis-37814A.svg?logo=celery)](./backend/medilink/celery.py)

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
- 🔌 **REST API & Swagger Docs:** [http://localhost:8000/api/](http://localhost:8000/api/)
- ⚙️ **Django Admin Portal:** [http://localhost:8000/admin/](http://localhost:8000/admin/)

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
| `celery-worker` | Celery 5.3 | Internal | Background task execution (emails, async processing) |
| `celery-beat` | Celery Beat | Internal | Scheduled cron tasks (hourly invoice reconciler) |
| `frontend` | React 18 + Nginx | `3000` | High-performance SPA with client-side routing & `/api/` reverse proxy |

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
