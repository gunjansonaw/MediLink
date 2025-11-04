import React, { useState, useEffect } from 'react';
import { Calendar, Users, CheckCircle, Clock } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import api from '../../services/api';
import './Dashboard.css';

function DoctorDashboard() {
  const [stats, setStats] = useState({
    total: 0,
    today: 0,
    scheduled: 0,
    completed: 0,
  });
  const [upcomingAppointments, setUpcomingAppointments] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      const [statsRes, appointmentsRes] = await Promise.all([
        api.get('/appointments/appointments/statistics/'),
        api.get('/appointments/appointments/upcoming/'),
      ]);

      setStats(statsRes.data);
      setUpcomingAppointments(appointmentsRes.data.slice(0, 5));
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const chartData = [
    { name: 'Today', count: stats.today },
    { name: 'Scheduled', count: stats.scheduled },
    { name: 'Completed', count: stats.completed },
  ];

  if (loading) {
    return <div className="loading">Loading dashboard...</div>;
  }

  return (
    <div className="dashboard">
      <h1>Doctor Dashboard</h1>
      
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon" style={{ backgroundColor: '#dbeafe' }}>
            <Calendar size={24} color="#3b82f6" />
          </div>
          <div className="stat-content">
            <h3>Total Appointments</h3>
            <p className="stat-value">{stats.total}</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ backgroundColor: '#fef3c7' }}>
            <Clock size={24} color="#f59e0b" />
          </div>
          <div className="stat-content">
            <h3>Today's Appointments</h3>
            <p className="stat-value">{stats.today}</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ backgroundColor: '#dbeafe' }}>
            <Users size={24} color="#3b82f6" />
          </div>
          <div className="stat-content">
            <h3>Scheduled</h3>
            <p className="stat-value">{stats.scheduled}</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ backgroundColor: '#d1fae5' }}>
            <CheckCircle size={24} color="#10b981" />
          </div>
          <div className="stat-content">
            <h3>Completed</h3>
            <p className="stat-value">{stats.completed}</p>
          </div>
        </div>
      </div>

      <div className="charts-grid">
        <div className="card">
          <h3>Appointment Overview</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="count" fill="#3b82f6" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h3>Upcoming Appointments</h3>
          <div className="appointments-list">
            {upcomingAppointments.length === 0 ? (
              <p className="no-data">No upcoming appointments</p>
            ) : (
              upcomingAppointments.map((appointment) => (
                <div key={appointment.id} className="appointment-item">
                  <div className="appointment-info">
                    <h4>{appointment.patient_details?.first_name} {appointment.patient_details?.last_name}</h4>
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
      </div>
    </div>
  );
}

export default DoctorDashboard;
