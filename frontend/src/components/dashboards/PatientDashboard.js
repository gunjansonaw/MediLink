import React, { useState, useEffect } from 'react';
import { Calendar, FileText, DollarSign, AlertCircle } from 'lucide-react';
import api from '../../services/api';
import './Dashboard.css';

function PatientDashboard() {
  const [upcomingAppointments, setUpcomingAppointments] = useState([]);
  const [recentRecords, setRecentRecords] = useState([]);
  const [pendingInvoices, setPendingInvoices] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      const [appointmentsRes, recordsRes, invoicesRes] = await Promise.all([
        api.get('/appointments/appointments/upcoming/'),
        api.get('/medical-records/records/my_records/'),
        api.get('/billing/invoices/?status=pending'),
      ]);

      setUpcomingAppointments(appointmentsRes.data.slice(0, 3));
      setRecentRecords(recordsRes.data.slice(0, 3));
      setPendingInvoices(invoicesRes.data.results?.slice(0, 3) || []);
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading dashboard...</div>;
  }

  return (
    <div className="dashboard">
      <h1>Patient Dashboard</h1>
      
      <div className="dashboard-grid">
        <div className="card">
          <div className="card-header">
            <Calendar size={24} color="#3b82f6" />
            <h3>Upcoming Appointments</h3>
          </div>
          <div className="card-content">
            {upcomingAppointments.length === 0 ? (
              <p className="no-data">No upcoming appointments</p>
            ) : (
              upcomingAppointments.map((appointment) => (
                <div key={appointment.id} className="list-item">
                  <div>
                    <h4>Dr. {appointment.doctor_details?.first_name} {appointment.doctor_details?.last_name}</h4>
                    <p>{appointment.appointment_date} at {appointment.appointment_time}</p>
                  </div>
                  <span className={`badge badge-${appointment.status === 'confirmed' ? 'success' : 'warning'}`}>
                    {appointment.status}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <FileText size={24} color="#10b981" />
            <h3>Recent Medical Records</h3>
          </div>
          <div className="card-content">
            {recentRecords.length === 0 ? (
              <p className="no-data">No medical records</p>
            ) : (
              recentRecords.map((record) => (
                <div key={record.id} className="list-item">
                  <div>
                    <h4>{record.diagnosis}</h4>
                    <p>Dr. {record.doctor_details?.first_name} - {new Date(record.created_at).toLocaleDateString()}</p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <DollarSign size={24} color="#f59e0b" />
            <h3>Pending Invoices</h3>
          </div>
          <div className="card-content">
            {pendingInvoices.length === 0 ? (
              <p className="no-data">No pending invoices</p>
            ) : (
              pendingInvoices.map((invoice) => (
                <div key={invoice.id} className="list-item">
                  <div>
                    <h4>Invoice #{invoice.invoice_number}</h4>
                    <p>Due: {invoice.due_date}</p>
                  </div>
                  <span className="amount">${invoice.total}</span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default PatientDashboard;
