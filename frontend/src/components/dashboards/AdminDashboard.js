import React, { useState, useEffect } from 'react';
import {
  Row, Col, Card, Statistic, Typography, Spin, Empty,
} from 'antd';
import {
  TeamOutlined, CalendarOutlined, DollarOutlined, RiseOutlined,
} from '@ant-design/icons';
import {
  PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer,
  LineChart, Line, XAxis, YAxis, CartesianGrid,
} from 'recharts';
import api from '../../services/api';

const { Title } = Typography;

const COLORS = ['#1677ff', '#52c41a', '#722ed1', '#ff4d4f'];

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
          totalUsers: Array.isArray(usersRes.data)
            ? usersRes.data.length
            : usersRes.data.count || 0,
          totalAppointments: appointmentsRes.data.total || 0,
          totalRevenue: billingRes.data.total_revenue || 0,
          pendingAmount: billingRes.data.pending_amount || 0,
        });
      } catch (error) {
        // silently fail
      } finally {
        setLoading(false);
      }
    };
    fetchDashboardData();
  }, []);

  const appointmentChartData = appointmentStats ? [
    { name: 'Scheduled', value: appointmentStats.scheduled || 0 },
    { name: 'Confirmed', value: appointmentStats.confirmed || 0 },
    { name: 'Completed', value: appointmentStats.completed || 0 },
    { name: 'Cancelled', value: appointmentStats.cancelled || 0 },
  ] : [];

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 80 }}>
        <Spin size="large" tip="Loading dashboard..." />
      </div>
    );
  }

  return (
    <div>
      <Title level={3} style={{ marginBottom: 24 }}>Admin Dashboard</Title>

      {/* Stats */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        {[
          { title: 'Total Users', value: stats.totalUsers, icon: <TeamOutlined />, color: '#1677ff', bg: '#e6f4ff' },
          { title: 'Total Appointments', value: stats.totalAppointments, icon: <CalendarOutlined />, color: '#52c41a', bg: '#f6ffed' },
          { title: 'Total Revenue', value: `$${Number(stats.totalRevenue).toFixed(2)}`, icon: <DollarOutlined />, color: '#059669', bg: '#f0fdf4' },
          { title: 'Pending Amount', value: `$${Number(stats.pendingAmount).toFixed(2)}`, icon: <RiseOutlined />, color: '#faad14', bg: '#fffbe6' },
        ].map((s) => (
          <Col xs={12} sm={6} key={s.title}>
            <Card className="stat-card-hover" bordered={false} style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{
                  width: 44,
                  height: 44,
                  borderRadius: 10,
                  background: s.bg,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 20,
                  color: s.color,
                  flexShrink: 0,
                }}>
                  {s.icon}
                </div>
                <Statistic
                  title={s.title}
                  value={s.value}
                  valueStyle={{ color: s.color, fontSize: 22 }}
                />
              </div>
            </Card>
          </Col>
        ))}
      </Row>

      {/* Charts */}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={10}>
          <Card
            title="Appointment Status Distribution"
            bordered={false}
            style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}
          >
            {appointmentChartData.every((d) => d.value === 0) ? (
              <Empty description="No appointment data" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie
                    data={appointmentChartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={3}
                    dataKey="value"
                    label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                  >
                    {appointmentChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            )}
          </Card>
        </Col>

        <Col xs={24} lg={14}>
          <Card
            title="Monthly Revenue"
            bordered={false}
            style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}
          >
            {!billingStats?.monthly_revenue?.length ? (
              <Empty description="No revenue data" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={billingStats.monthly_revenue}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="month" />
                  <YAxis />
                  <Tooltip formatter={(v) => [`$${v}`, 'Revenue']} />
                  <Line
                    type="monotone"
                    dataKey="revenue"
                    stroke="#1677ff"
                    strokeWidth={2}
                    dot={{ r: 4 }}
                    activeDot={{ r: 6 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}

export default AdminDashboard;
