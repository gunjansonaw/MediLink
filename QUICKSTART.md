# MediLink - Quick Start Guide

Get MediLink running in 10 minutes!

## Prerequisites

- Python 3.8+
- Node.js 14+
- PostgreSQL 12+
- Git (optional)

## 🚀 Quick Setup (Development)

### Step 1: Database Setup

```bash
# Create PostgreSQL database
createdb medilink

# Or using psql
psql -U postgres
CREATE DATABASE medilink;
\q
```

### Step 2: Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create environment file
copy .env.example .env  # Windows
cp .env.example .env    # Linux/Mac

# Edit .env with your database credentials:
# DB_NAME=medilink
# DB_USER=postgres
# DB_PASSWORD=your_password
# DB_HOST=localhost

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Create admin user
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput

# Start backend server
python manage.py runserver
```

Backend is now running at: http://localhost:8000

### Step 3: Frontend Setup (New Terminal)

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Create environment file
copy .env.example .env  # Windows
cp .env.example .env    # Linux/Mac

# Start frontend server
npm start
```

Frontend is now running at: http://localhost:3000

## 🎯 Access Points

- **Frontend App**: http://localhost:3000
- **Backend API**: http://localhost:8000/api
- **Admin Panel**: http://localhost:8000/admin
- **API Docs**: http://localhost:8000/swagger
- **ReDoc**: http://localhost:8000/redoc

## 👥 Test Users

Create test users for each role:

### Admin User
```bash
# Already created with createsuperuser
# Role: admin
```

### Doctor User
1. Go to http://localhost:3000/register
2. Fill in details and select "Doctor" role
3. Or create via Django admin

### Patient User
1. Go to http://localhost:3000/register
2. Fill in details and select "Patient" role
3. Or create via Django admin

## 📝 Testing the Application

### As Patient:
1. Login at http://localhost:3000/login
2. View dashboard
3. Book an appointment with a doctor
4. View medical records
5. Check billing/invoices

### As Doctor:
1. Login as doctor
2. View appointments
3. Confirm appointments
4. Create medical records
5. Add prescriptions and lab tests

### As Admin:
1. Login as admin
2. View analytics dashboard
3. Manage all appointments
4. View billing statistics
5. Access all user data

## 🔧 Troubleshooting

### Database Connection Error
```bash
# Check if PostgreSQL is running
# Windows: Check Services
# Linux/Mac: sudo systemctl status postgresql

# Verify database exists
psql -U postgres -l
```

### Port Already in Use
```bash
# Backend (port 8000)
python manage.py runserver 8001

# Frontend (port 3000)
set PORT=3001 && npm start  # Windows
PORT=3001 npm start         # Linux/Mac
```

### Module Not Found
```bash
# Backend
pip install -r requirements.txt

# Frontend
npm install
```

### Migration Issues
```bash
cd backend
python manage.py makemigrations
python manage.py migrate --run-syncdb
```

## 🎨 Sample Data (Optional)

Create sample data for testing:

```python
# Run Django shell
python manage.py shell

# Create sample doctor
from users.models import User, DoctorProfile
doctor = User.objects.create_user(
    username='doctor1',
    email='doctor@test.com',
    password='password123',
    first_name='John',
    last_name='Doe',
    role='doctor'
)
DoctorProfile.objects.create(
    user=doctor,
    specialization='Cardiology',
    license_number='LIC12345',
    consultation_fee=100.00,
    experience_years=10
)
```

## 📚 Next Steps

1. Explore the API documentation at http://localhost:8000/swagger
2. Check out the main README.md for detailed features
3. Review the deployment guide in deployment/README.md
4. Customize the application for your needs

## 🆘 Need Help?

- Check the main [README.md](README.md)
- Review API docs at http://localhost:8000/swagger
- Check deployment guide in [deployment/README.md](deployment/README.md)

## 🎉 You're All Set!

MediLink is now running locally. Happy coding!
