import React, { useState, useEffect } from 'react';
import { Users, Calendar, FileText, DollarSign, TrendingUp } from 'lucide-react';
import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import api from '../../services/api';
import './Dashboard.css';

function AdminDashboard() {
  const [stats, setStats] = useState({
    totalUsers: 0,
    totalAppointments: 0,
    totalRevenue: 0,
    pendingAmount: 0,
  });
  const [appointmentStats, setAppointmentStats] = useState(null);
  const [billingStats, setBillingStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      const [appointmentsRes, billingRes, usersRes] = await Promise.all([
        api.get('/appointments/appointments/statistics/'),
        api.get('/billing/invoices/statistics/'),
        api.get('/users/'),
      ]);

      setAppointmentStats(appointmentsRes.data);
      setBillingStats(billingRes.data);
      
      setStats({
        totalUsers: usersRes.data.length || 0,
        totalAppointments: appointmentsRes.data.total || 0,
        totalRevenue: billingRes.data.total_revenue || 0,
        pendingAmount: billingRes.data.pending_amount || 0,
      });
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const appointmentChartData = appointmentStats ? [
    { name: 'Scheduled', value: appointmentStats.scheduled },
    { name: 'Confirmed', value: appointmentStats.confirmed },
    { name: 'Completed', value: appointmentStats.completed },
    { name: 'Cancelled', value: appointmentStats.cancelled },
  ] : [];

  const COLORS = ['#3b82f6', '#10b981', '#8b5cf6', '#ef4444'];

  if (loading) {
    return <div className="loading">Loading dashboard...</div>;
  }

  return (
    <div className="dashboard">
      <h1>Admin Dashboard</h1>
      
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon" style={{ backgroundColor: '#dbeafe' }}>
            <Users size={24} color="#3b82f6" />
          </div>
          <div className="stat-content">
            <h3>Total Users</h3>
            <p className="stat-value">{stats.totalUsers}</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ backgroundColor: '#dcfce7' }}>
            <Calendar size={24} color="#10b981" />
          </div>
          <div className="stat-content">
            <h3>Total Appointments</h3>
            <p className="stat-value">{stats.totalAppointments}</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ backgroundColor: '#d1fae5' }}>
            <DollarSign size={24} color="#059669" />
          </div>
          <div className="stat-content">
            <h3>Total Revenue</h3>
            <p className="stat-value">${stats.totalRevenue.toFixed(2)}</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ backgroundColor: '#fef3c7' }}>
            <TrendingUp size={24} color="#f59e0b" />
          </div>
          <div className="stat-content">
            <h3>Pending Amount</h3>
            <p className="stat-value">${stats.pendingAmount.toFixed(2)}</p>
          </div>
        </div>
      </div>

      <div className="charts-grid">
        <div className="card">
          <h3>Appointment Status Distribution</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={appointmentChartData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {appointmentChartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h3>Monthly Revenue</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={billingStats?.monthly_revenue || []}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="revenue" stroke="#3b82f6" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

export default AdminDashboard;
