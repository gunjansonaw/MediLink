import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Login from './components/auth/Login';
import Register from './components/auth/Register';
import AdminDashboard from './components/dashboards/AdminDashboard';
import DoctorDashboard from './components/dashboards/DoctorDashboard';
import PatientDashboard from './components/dashboards/PatientDashboard';
import Layout from './components/layout/Layout';
import Appointments from './components/appointments/Appointments';
import MedicalRecords from './components/medical-records/MedicalRecords';
import Billing from './components/billing/Billing';

function PrivateRoute({ children, allowedRoles }) {
  const { user } = useAuth();
  
  if (!user) {
    return <Navigate to="/login" />;
  }
  
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to="/" />;
  }
  
  return children;
}

function DashboardRedirect() {
  const { user } = useAuth();
  
  if (!user) {
    return <Navigate to="/login" />;
  }
  
  switch (user.role) {
    case 'admin':
      return <Navigate to="/admin/dashboard" />;
    case 'doctor':
      return <Navigate to="/doctor/dashboard" />;
    case 'patient':
      return <Navigate to="/patient/dashboard" />;
    default:
      return <Navigate to="/login" />;
  }
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          
          <Route path="/" element={<DashboardRedirect />} />
          
          {/* Admin Routes */}
          <Route path="/admin/*" element={
            <PrivateRoute allowedRoles={['admin']}>
              <Layout>
                <Routes>
                  <Route path="dashboard" element={<AdminDashboard />} />
                  <Route path="appointments" element={<Appointments />} />
                  <Route path="medical-records" element={<MedicalRecords />} />
                  <Route path="billing" element={<Billing />} />
                </Routes>
              </Layout>
            </PrivateRoute>
          } />
          
          {/* Doctor Routes */}
          <Route path="/doctor/*" element={
            <PrivateRoute allowedRoles={['doctor']}>
              <Layout>
                <Routes>
                  <Route path="dashboard" element={<DoctorDashboard />} />
                  <Route path="appointments" element={<Appointments />} />
                  <Route path="medical-records" element={<MedicalRecords />} />
                </Routes>
              </Layout>
            </PrivateRoute>
          } />
          
          {/* Patient Routes */}
          <Route path="/patient/*" element={
            <PrivateRoute allowedRoles={['patient']}>
              <Layout>
                <Routes>
                  <Route path="dashboard" element={<PatientDashboard />} />
                  <Route path="appointments" element={<Appointments />} />
                  <Route path="medical-records" element={<MedicalRecords />} />
                  <Route path="billing" element={<Billing />} />
                </Routes>
              </Layout>
            </PrivateRoute>
          } />
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;
