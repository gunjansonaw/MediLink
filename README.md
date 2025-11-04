# 🏥 MediLink – Hospital Management System

A comprehensive, full-stack hospital management system with role-based dashboards for doctors, patients, and administrators.

## 🚀 Tech Stack

### Backend
- **Django REST Framework** - RESTful API development
- **PostgreSQL** - Robust relational database
- **JWT Authentication** - Secure token-based auth
- **Celery & Redis** - Background task processing
- **Swagger/ReDoc** - API documentation

### Frontend
- **React.js** - Modern UI library
- **React Router** - Client-side routing
- **Recharts** - Data visualization
- **Axios** - HTTP client
- **Lucide React** - Icon library

### Deployment
- **AWS EC2** - Cloud hosting
- **Nginx** - Web server & reverse proxy
- **Gunicorn** - Python WSGI HTTP server

## ✨ Features

### 👨‍⚕️ For Doctors
- View and manage appointments
- Create and update medical records
- Prescribe medications
- Order lab tests
- Track patient vitals

### 🏥 For Administrators
- Complete system oversight
- User management
- Analytics dashboard with charts
- Billing and invoice management
- Appointment statistics
- Revenue tracking

### 👤 For Patients
- Book and manage appointments
- View medical history
- Access prescriptions
- Track lab test results
- Manage billing and payments
- View vital signs history

## 📁 Project Structure

```
medilink/
├── backend/                    # Django REST Framework API
│   ├── medilink/              # Main project settings
│   ├── users/                 # User management & authentication
│   ├── appointments/          # Appointment system
│   ├── medical_records/       # Medical records & prescriptions
│   ├── billing/               # Billing & invoicing
│   ├── manage.py
│   └── requirements.txt
│
├── frontend/                   # React application
│   ├── public/
│   ├── src/
│   │   ├── components/        # React components
│   │   ├── context/          # React contexts
│   │   ├── services/         # API services
│   │   ├── App.js
│   │   └── index.js
│   └── package.json
│
└── deployment/                 # Deployment configuration
    ├── nginx.conf             # Nginx configuration
    ├── gunicorn.service       # Systemd service
    ├── deploy.sh              # Deployment script
    └── README.md              # Deployment guide
```

## 🛠️ Installation & Setup

### Backend Setup

1. **Create virtual environment**:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your database credentials
```

4. **Setup database**:
```bash
# Create PostgreSQL database
createdb medilink

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

5. **Run development server**:
```bash
python manage.py runserver
```

Backend API: `http://localhost:8000`
Admin Panel: `http://localhost:8000/admin`
API Docs: `http://localhost:8000/swagger`

### Frontend Setup

1. **Install dependencies**:
```bash
cd frontend
npm install
```

2. **Configure environment**:
```bash
cp .env.example .env
# Edit REACT_APP_API_URL if needed
```

3. **Start development server**:
```bash
npm start
```

Frontend: `http://localhost:3000`

## 🔑 API Endpoints

### Authentication
- `POST /api/users/login/` - User login
- `POST /api/users/` - User registration
- `GET /api/users/me/` - Current user info

### Appointments
- `GET /api/appointments/appointments/` - List appointments
- `POST /api/appointments/appointments/` - Create appointment
- `POST /api/appointments/appointments/{id}/confirm/` - Confirm appointment
- `POST /api/appointments/appointments/{id}/cancel/` - Cancel appointment

### Medical Records
- `GET /api/medical-records/records/` - List medical records
- `POST /api/medical-records/records/` - Create record
- `GET /api/medical-records/prescriptions/` - List prescriptions
- `GET /api/medical-records/lab-tests/` - List lab tests

### Billing
- `GET /api/billing/invoices/` - List invoices
- `POST /api/billing/invoices/` - Create invoice
- `GET /api/billing/payments/` - List payments
- `POST /api/billing/payments/` - Record payment

## 🚀 Deployment

### AWS EC2 Deployment

1. **Launch EC2 instance** (Ubuntu 20.04+)

2. **Upload files to server**:
```bash
scp -r medilink ubuntu@your-ec2-ip:/home/ubuntu/
```

3. **Run deployment script**:
```bash
ssh ubuntu@your-ec2-ip
cd medilink/deployment
chmod +x deploy.sh
./deploy.sh
```

Detailed deployment guide: [deployment/README.md](deployment/README.md)

## 📊 Database Schema

### Users
- Custom user model with role field (admin/doctor/patient)
- Doctor profiles with specialization, license, fees
- Patient profiles with medical history, insurance info

### Appointments
- Appointment scheduling with doctor availability
- Status tracking (scheduled, confirmed, completed, cancelled)
- Conflict prevention

### Medical Records
- Diagnosis, symptoms, treatment plans
- Prescriptions with dosage and frequency
- Lab tests with results
- Vital signs tracking

### Billing
- Invoice generation
- Payment tracking
- Insurance claims management

## 🔒 Security Features

- JWT token authentication
- Role-based access control
- Password hashing (Django default)
- CORS configuration
- Environment variable management
- SQL injection prevention (Django ORM)
- XSS protection

## 🧪 Testing

```bash
# Backend tests
cd backend
python manage.py test

# Frontend tests
cd frontend
npm test
```

## 📝 License

This project is created for educational and portfolio purposes.

## 👨‍💻 Developer

Built as a demonstration of full-stack development capabilities including:
- RESTful API design
- Role-based authentication
- Real-time scheduling systems
- Data visualization
- Cloud deployment

## 📞 Support

For questions or issues, please create an issue in the repository.

---

**Note**: Remember to change default passwords and secret keys before deploying to production!
