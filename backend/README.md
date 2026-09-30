# MediLink Backend - Django REST Framework

Hospital Management System backend built with Django REST Framework.

## Features

- **Role-Based Authentication**: Admin, Doctor, and Patient roles with JWT authentication
- **Appointment Management**: Booking, scheduling, and management system
- **Medical Records**: Electronic health records with prescriptions and lab tests
- **Billing System**: Invoice management, payments, and insurance claims
- **RESTful APIs**: Comprehensive API endpoints with Swagger documentation

## Tech Stack

- Django 4.2.7
- Django REST Framework 3.14.0
- PostgreSQL (Database)
- JWT Authentication
- Celery (Background Tasks)
- Redis (Cache & Message Broker)

## Setup Instructions

### Prerequisites

- Python 3.8+
- PostgreSQL
- Redis (optional, for Celery tasks)

### Installation

1. **Create and activate virtual environment**:
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Configure environment variables**:
```bash
cp .env.example .env
# Edit .env with your database credentials
```

4. **Create PostgreSQL database**:
```sql
CREATE DATABASE medilink;
```

5. **Run migrations**:
```bash
python manage.py makemigrations
python manage.py migrate
```

6. **Create superuser**:
```bash
python manage.py createsuperuser
```

7. **Collect static files**:
```bash
python manage.py collectstatic
```

8. **Run development server**:
```bash
python manage.py runserver
```

The API will be available at `http://localhost:8000`

## API Documentation

- **Swagger UI**: http://localhost:8000/swagger/
- **ReDoc**: http://localhost:8000/redoc/

## API Endpoints

### Authentication
- `POST /api/users/login/` - User login
- `POST /api/users/` - User registration
- `GET /api/users/me/` - Get current user

### Appointments
- `GET /api/appointments/appointments/` - List appointments
- `POST /api/appointments/appointments/` - Create appointment
- `GET /api/appointments/appointments/upcoming/` - Get upcoming appointments
- `POST /api/appointments/appointments/{id}/confirm/` - Confirm appointment

### Medical Records
- `GET /api/medical-records/records/` - List medical records
- `POST /api/medical-records/records/` - Create medical record
- `GET /api/medical-records/prescriptions/` - List prescriptions
- `GET /api/medical-records/lab-tests/` - List lab tests

### Billing
- `GET /api/billing/invoices/` - List invoices
- `POST /api/billing/invoices/` - Create invoice
- `GET /api/billing/payments/` - List payments
- `POST /api/billing/payments/` - Record payment

## Running with Celery (Optional)

Start Celery worker:
```bash
celery -A medilink worker -l info
```

Start Celery beat (for scheduled tasks):
```bash
celery -A medilink beat -l info
```

## Testing

Run tests:
```bash
python manage.py test
```

## Deployment

See deployment configuration in the deployment section for AWS EC2 setup with Nginx and PostgreSQL.
