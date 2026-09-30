import React, { useState, useEffect } from 'react';
import {
  Row, Col, Card, Statistic, List, Tag, Typography, Space, Spin, Empty,
} from 'antd';
import {
  CalendarOutlined, CheckCircleOutlined, ClockCircleOutlined, TeamOutlined,
} from '@ant-design/icons';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import api from '../../services/api';

const { Title } = Typography;

const statusColor = (status) => {
  switch (status) {
    case 'confirmed': return 'green';
    case 'scheduled': return 'blue';
    case 'cancelled': return 'red';
    case 'completed': return 'purple';
    default: return 'default';
  }
};

function DoctorDashboard() {
  const [stats, setStats] = useState({ total: 0, today: 0, scheduled: 0, completed: 0 });
  const [upcomingAppointments, setUpcomingAppointments] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        const [statsRes, appointmentsRes] = await Promise.all([
          api.get('/appointments/appointments/statistics/'),
          api.get('/appointments/appointments/upcoming/'),
        ]);
        setStats(statsRes.data);
        setUpcomingAppointments(appointmentsRes.data.slice(0, 5));
      } catch (error) {
        // silently fail
      } finally {
        setLoading(false);
      }
    };
    fetchDashboardData();
  }, []);

  const chartData = [
    { name: 'Today', count: stats.today },
    { name: 'Scheduled', count: stats.scheduled },
    { name: 'Completed', count: stats.completed },
  ];

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 80 }}>
        <Spin size="large" tip="Loading dashboard..." />
      </div>
    );
  }

  return (
    <div>
      <Title level={3} style={{ marginBottom: 24 }}>Doctor Dashboard</Title>

      {/* Stats */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        {[
          { title: 'Total Appointments', value: stats.total, icon: <CalendarOutlined />, color: '#1677ff', bg: '#e6f4ff' },
          { title: "Today's Appointments", value: stats.today, icon: <ClockCircleOutlined />, color: '#faad14', bg: '#fffbe6' },
          { title: 'Scheduled', value: stats.scheduled, icon: <TeamOutlined />, color: '#1677ff', bg: '#e6f4ff' },
          { title: 'Completed', value: stats.completed, icon: <CheckCircleOutlined />, color: '#52c41a', bg: '#f6ffed' },
        ].map((s) => (
          <Col xs={12} sm={6} key={s.title}>
            <Card
              className="stat-card-hover"
              bordered={false}
              style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}
            >
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
                  valueStyle={{ color: s.color, fontSize: 24 }}
                />
              </div>
            </Card>
          </Col>
        ))}
      </Row>

      {/* Charts + Upcoming */}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card
            title="Appointment Overview"
            bordered={false}
            style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}
          >
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="name" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Legend />
                <Bar dataKey="count" fill="#1677ff" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card
            title={<Space><CalendarOutlined style={{ color: '#1677ff' }} /><span>Upcoming Appointments</span></Space>}
            bordered={false}
            style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}
          >
            {upcomingAppointments.length === 0 ? (
              <Empty description="No upcoming appointments" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <List
                dataSource={upcomingAppointments}
                renderItem={(apt) => (
                  <List.Item
                    key={apt.id}
                    extra={<Tag color={statusColor(apt.status)}>{apt.status}</Tag>}
                  >
                    <List.Item.Meta
                      title={`${apt.patient_details?.first_name || ''} ${apt.patient_details?.last_name || ''}`}
                      description={`${apt.appointment_date} at ${apt.appointment_time}`}
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}

export default DoctorDashboard;
