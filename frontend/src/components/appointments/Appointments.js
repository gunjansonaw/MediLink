import React, { useState, useEffect } from 'react';
import {
  Table, Button, Modal, Form, Select, DatePicker,
  Input, Tag, Space, Typography, message, Card,
} from 'antd';
import {
  PlusOutlined, CheckOutlined, CloseOutlined, CalendarOutlined, FileSearchOutlined, StopOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { useAuth } from '../../context/AuthContext';
import api from '../../services/api';
import BriefModal from '../ai/BriefModal';

const { Title } = Typography;
const { Option } = Select;
const { TextArea } = Input;

const statusColor = (status) => {
  switch (status) {
    case 'completed': return 'purple';
    case 'confirmed': return 'green';
    case 'cancelled': return 'red';
    case 'no_show': return 'volcano';
    default: return 'blue';
  }
};

function Appointments() {
  const { user } = useAuth();
  const [appointments, setAppointments] = useState([]);
  const [doctors, setDoctors] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [briefFor, setBriefFor] = useState(null);
  const [slots, setSlots] = useState([]);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [form] = Form.useForm();
  const selectedDoctor = Form.useWatch('doctor', form);
  const selectedDate = Form.useWatch('appointment_date', form);

  // Load real free slots whenever doctor + date are chosen
  useEffect(() => {
    if (!selectedDoctor || !selectedDate) {
      setSlots([]);
      return;
    }
    const day = dayjs(selectedDate).format('YYYY-MM-DD');
    setSlotsLoading(true);
    form.setFieldValue('appointment_time', undefined);
    api.get('/appointments/appointments/available_slots/', { params: { doctor: selectedDoctor, start: day, end: day } })
      .then((r) => setSlots(r.data.slots.map((sl) => sl.time)))
      .catch(() => setSlots([]))
      .finally(() => setSlotsLoading(false));
  }, [selectedDoctor, selectedDate]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchAppointments();
    if (user.role === 'patient') {
      fetchDoctors();
    }
  }, [user.role]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchAppointments = async () => {
    try {
      const response = await api.get('/appointments/appointments/');
      setAppointments(response.data.results || response.data);
    } catch (error) {
      message.error('Failed to load appointments');
    } finally {
      setLoading(false);
    }
  };

  const fetchDoctors = async () => {
    try {
      const response = await api.get('/users/doctors/');
      setDoctors(response.data);
    } catch (error) {
      message.error('Failed to load doctors list');
    }
  };

  const handleSubmit = async (values) => {
    setSubmitting(true);
    try {
      await api.post('/appointments/appointments/', {
        doctor: values.doctor,
        appointment_date: dayjs(values.appointment_date).format('YYYY-MM-DD'),
        appointment_time: values.appointment_time,
        reason: values.reason,
      });
      message.success('Appointment booked successfully');
      setShowModal(false);
      form.resetFields();
      fetchAppointments();
    } catch (error) {
      let errMsg = 'Failed to book appointment';
      const data = error.response?.data;
      if (typeof data === 'string') {
        errMsg = data;
      } else if (data?.detail) {
        errMsg = data.detail;
      } else if (typeof data === 'object') {
        errMsg = Object.values(data).flat().join(' | ');
      }
      message.error(errMsg);
    } finally {
      setSubmitting(false);
    }
  };

  const handleConfirm = async (id) => {
    try {
      await api.post(`/appointments/appointments/${id}/confirm/`);
      message.success('Appointment confirmed');
      fetchAppointments();
    } catch (error) {
      message.error('Failed to confirm appointment');
    }
  };

  const handleStatus = async (id, verb, label) => {
    try {
      await api.post(`/appointments/appointments/${id}/${verb}/`);
      message.success(label);
      fetchAppointments();
    } catch (error) {
      message.error(error.response?.data?.error || 'Could not update appointment');
    }
  };

  const handleCancel = (id) => {
    Modal.confirm({
      title: 'Cancel Appointment',
      content: 'Are you sure you want to cancel this appointment?',
      okText: 'Yes, Cancel',
      okType: 'danger',
      cancelText: 'No',
      onOk: async () => {
        try {
          await api.post(`/appointments/appointments/${id}/cancel/`);
          message.success('Appointment cancelled');
          fetchAppointments();
        } catch (error) {
          message.error('Failed to cancel appointment');
        }
      },
    });
  };

  const columns = [
    {
      title: 'Date',
      dataIndex: 'appointment_date',
      key: 'appointment_date',
    },
    {
      title: 'Time',
      dataIndex: 'appointment_time',
      key: 'appointment_time',
    },
    ...(user.role !== 'doctor'
      ? [{
          title: 'Doctor',
          key: 'doctor',
          render: (_, record) =>
            `Dr. ${record.doctor_details?.first_name || ''} ${record.doctor_details?.last_name || ''}`,
        }]
      : []),
    ...(user.role !== 'patient'
      ? [{
          title: 'Patient',
          key: 'patient',
          render: (_, record) =>
            `${record.patient_details?.first_name || ''} ${record.patient_details?.last_name || ''}`,
        }]
      : []),
    {
      title: 'Reason',
      dataIndex: 'reason',
      key: 'reason',
      ellipsis: true,
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status) => <Tag color={statusColor(status)}>{status}</Tag>,
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_, record) => (
        <Space wrap>
          {user.role !== 'patient' && record.status === 'scheduled' && (
            <Button
              type="primary"
              size="small"
              icon={<CheckOutlined />}
              onClick={() => handleConfirm(record.id)}
            >
              Confirm
            </Button>
          )}
          {user.role !== 'patient' && ['scheduled', 'confirmed'].includes(record.status) && (
            <>
              <Button size="small" onClick={() => handleStatus(record.id, 'complete', 'Appointment completed')}>
                Complete
              </Button>
              <Button size="small" icon={<StopOutlined />} onClick={() => handleStatus(record.id, 'no_show', 'Marked as no-show')}>
                No-show
              </Button>
            </>
          )}
          {user.role === 'doctor' && ['scheduled', 'confirmed'].includes(record.status) && (
            <Button size="small" icon={<FileSearchOutlined />} onClick={() => setBriefFor(record)}>
              Brief
            </Button>
          )}
          {['scheduled', 'confirmed'].includes(record.status) && (
            <Button
              danger
              size="small"
              icon={<CloseOutlined />}
              onClick={() => handleCancel(record.id)}
            >
              Cancel
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>
          <Space><CalendarOutlined />Appointments</Space>
        </Title>
        {user.role === 'patient' && (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setShowModal(true)}>
            Book Appointment
          </Button>
        )}
      </div>

      <Card bordered={false} style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
        <Table
          dataSource={appointments}
          columns={columns}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10, showSizeChanger: false }}
          scroll={{ x: 600 }}
        />
      </Card>

      <BriefModal appointment={briefFor} open={!!briefFor} onClose={() => setBriefFor(null)} />

      {/* Book Appointment Modal */}
      <Modal
        title="Book Appointment"
        open={showModal}
        onCancel={() => { setShowModal(false); form.resetFields(); }}
        footer={null}
        destroyOnClose
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          style={{ marginTop: 16 }}
        >
          <Form.Item
            name="doctor"
            label="Doctor"
            rules={[{ required: true, message: 'Please select a doctor' }]}
          >
            <Select placeholder="Select a doctor" showSearch optionFilterProp="children">
              {doctors.map((doc) => (
                <Option key={doc.id} value={doc.id}>
                  Dr. {doc.first_name} {doc.last_name}
                  {doc.doctor_profile?.specialization && ` — ${doc.doctor_profile.specialization}`}
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="appointment_date"
            label="Date"
            rules={[{ required: true, message: 'Please select a date' }]}
          >
            <DatePicker
              style={{ width: '100%' }}
              disabledDate={(d) => d && d.isBefore(dayjs().startOf('day'))}
            />
          </Form.Item>

          <Form.Item
            name="appointment_time"
            label="Available time"
            rules={[{ required: true, message: 'Please select a time slot' }]}
          >
            <Select
              placeholder={!selectedDoctor || !selectedDate ? 'Choose a doctor and date first' : 'Pick a free slot'}
              loading={slotsLoading}
              disabled={!selectedDoctor || !selectedDate}
              notFoundContent={slotsLoading ? 'Loading…' : 'No free slots on this day'}
              options={slots.map((t) => ({ value: t, label: t }))}
            />
          </Form.Item>

          <Form.Item
            name="reason"
            label="Reason"
            rules={[{ required: true, message: 'Please enter the reason for your visit' }]}
          >
            <TextArea rows={3} placeholder="Describe your reason for the visit..." />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
            <Space>
              <Button onClick={() => { setShowModal(false); form.resetFields(); }}>Cancel</Button>
              <Button type="primary" htmlType="submit" loading={submitting}>
                Book Appointment
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

export default Appointments;
