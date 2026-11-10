import React, { useState, useEffect } from 'react';
import {
  Row, Col, Card, Statistic, List, Tag, Typography,
  Space, Spin, Empty,
} from 'antd';
import {
  CalendarOutlined, FileTextOutlined, DollarOutlined,
} from '@ant-design/icons';
import api from '../../services/api';

const { Title, Text } = Typography;

const statusColor = (status) => {
  switch (status) {
    case 'confirmed': return 'green';
    case 'scheduled': return 'blue';
    case 'cancelled': return 'red';
    case 'completed': return 'purple';
    default: return 'default';
  }
};

function PatientDashboard() {
  const [upcomingAppointments, setUpcomingAppointments] = useState([]);
  const [recentRecords, setRecentRecords] = useState([]);
  const [pendingInvoices, setPendingInvoices] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        const [appointmentsRes, recordsRes, invoicesRes] = await Promise.all([
          api.get('/appointments/appointments/upcoming/'),
          api.get('/medical-records/records/my_records/'),
          // partially paid and overdue invoices also have money owing
          api.get('/billing/invoices/?status_in=pending,partially_paid,overdue'),
        ]);

        setUpcomingAppointments(appointmentsRes.data);
        setRecentRecords(recordsRes.data);
        setPendingInvoices(invoicesRes.data.results || invoicesRes.data || []);
      } catch (error) {
        // silently fail on dashboard load errors
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardData();
  }, []);

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 80 }}>
        <Spin size="large" tip="Loading dashboard..." />
      </div>
    );
  }

  return (
    <div>
      <Title level={3} style={{ marginBottom: 24 }}>Patient Dashboard</Title>

      {/* Summary stats */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={8}>
          <Card className="stat-card-hover" bordered={false} style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
            <Statistic
              title="Upcoming Appointments"
              value={upcomingAppointments.length}
              prefix={<CalendarOutlined style={{ color: '#1677ff' }} />}
              valueStyle={{ color: '#1677ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card className="stat-card-hover" bordered={false} style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
            <Statistic
              title="Medical Records"
              value={recentRecords.length}
              prefix={<FileTextOutlined style={{ color: '#52c41a' }} />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card className="stat-card-hover" bordered={false} style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
            <Statistic
              title="Open Invoices"
              value={pendingInvoices.length}
              prefix={<DollarOutlined style={{ color: '#faad14' }} />}
              valueStyle={{ color: '#faad14' }}
            />
          </Card>
        </Col>
      </Row>

      {/* Detail cards */}
      <Row gutter={[16, 16]}>
        {/* Upcoming Appointments */}
        <Col xs={24} lg={8}>
          <Card
            title={<Space><CalendarOutlined style={{ color: '#1677ff' }} /><span>Upcoming Appointments</span></Space>}
            bordered={false}
            style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)', height: '100%' }}
          >
            {upcomingAppointments.length === 0 ? (
              <Empty description="No upcoming appointments" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <List
                dataSource={upcomingAppointments.slice(0, 5)}
                renderItem={(apt) => (
                  <List.Item
                    key={apt.id}
                    extra={<Tag color={statusColor(apt.status)}>{apt.status}</Tag>}
                  >
                    <List.Item.Meta
                      title={`Dr. ${apt.doctor_details?.first_name || ''} ${apt.doctor_details?.last_name || ''}`}
                      description={`${apt.appointment_date} at ${apt.appointment_time}`}
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>

        {/* Recent Medical Records */}
        <Col xs={24} lg={8}>
          <Card
            title={<Space><FileTextOutlined style={{ color: '#52c41a' }} /><span>Recent Medical Records</span></Space>}
            bordered={false}
            style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)', height: '100%' }}
          >
            {recentRecords.length === 0 ? (
              <Empty description="No medical records" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <List
                dataSource={recentRecords.slice(0, 5)}
                renderItem={(record) => (
                  <List.Item key={record.id}>
                    <List.Item.Meta
                      title={record.diagnosis}
                      description={`Dr. ${record.doctor_details?.first_name || ''} · ${new Date(record.created_at).toLocaleDateString()}`}
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>

        {/* Pending Invoices */}
        <Col xs={24} lg={8}>
          <Card
            title={<Space><DollarOutlined style={{ color: '#faad14' }} /><span>Open Invoices</span></Space>}
            bordered={false}
            style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)', height: '100%' }}
          >
            {pendingInvoices.length === 0 ? (
              <Empty description="No open invoices" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <List
                dataSource={pendingInvoices.slice(0, 5)}
                renderItem={(inv) => (
                  <List.Item
                    key={inv.id}
                    extra={<Text strong style={{ color: inv.status === 'overdue' ? '#ff4d4f' : '#faad14' }}>
                      ${parseFloat(inv.remaining_balance ?? inv.total).toFixed(2)}
                    </Text>}
                  >
                    <List.Item.Meta
                      title={`Invoice #${inv.invoice_number}`}
                      description={`Due: ${inv.due_date}${inv.status === 'overdue' ? ' · overdue' : ''}`}
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

export default PatientDashboard;
