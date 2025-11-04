# MediLink Frontend - React Application

Modern hospital management system frontend built with React.js

## Features

- **Role-Based Dashboards**: Separate interfaces for Admin, Doctor, and Patient
- **Appointment Booking**: Real-time appointment scheduling system
- **Medical Records**: View and manage electronic health records
- **Billing Management**: Invoice tracking and payment history
- **Analytics Visualization**: Charts and graphs using Recharts
- **Responsive Design**: Mobile-friendly interface

## Tech Stack

- React 18.2
- React Router 6
- Axios (API calls)
- Recharts (Data visualization)
- Lucide React (Icons)
- CSS3 (Styling)

## Prerequisites

- Node.js 14+ and npm

## Installation

1. **Install dependencies**:
```bash
npm install
```

2. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your backend API URL
```

3. **Start development server**:
```bash
npm start
```

The application will run at `http://localhost:3000`

## Available Scripts

- `npm start` - Run development server
- `npm build` - Build for production
- `npm test` - Run tests
- `npm run eject` - Eject from Create React App

## Project Structure

```
src/
├── components/
│   ├── auth/            # Login and registration
│   ├── dashboards/      # Role-based dashboards
│   ├── appointments/    # Appointment management
│   ├── medical-records/ # Medical records interface
│   ├── billing/         # Billing and invoices
│   └── layout/          # Layout components
├── context/             # React contexts
├── services/            # API services
├── App.js              # Main app component
└── index.js            # Entry point
```

## User Roles

1. **Admin**: Full system access, analytics, user management
2. **Doctor**: Manage appointments, medical records, patient data
3. **Patient**: Book appointments, view records, manage billing

## Building for Production

```bash
npm run build
```

This creates an optimized production build in the `build/` folder.

## Deployment

The application can be deployed to:
- AWS S3 + CloudFront
- Netlify
- Vercel
- Any static hosting service

Configure the `REACT_APP_API_URL` environment variable to point to your production API.
