import React, { useState, useEffect } from 'react';
import {
  List, Card, Descriptions, Table, Tag, Typography, Space, Spin,
  Empty, Row, Col, Button, Modal, Form, Input, Select, message,
} from 'antd';
import { FileTextOutlined, PlusOutlined, MedicineBoxOutlined } from '@ant-design/icons';
import api from '../../services/api';
import { useAuth } from '../../context/AuthContext';

const { Title, Text } = Typography;
const { TextArea } = Input;
const { Option } = Select;

const statusColor = (status) =>
  status === 'completed' ? 'green' : 'orange';

function MedicalRecords() {
  const { user } = useAuth();
  const [records, setRecords] = useState([]);
  const [patients, setPatients] = useState([]);
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    fetchRecords();
    if (user.role === 'doctor' || user.role === 'admin') {
      fetchPatients();
    }
  }, [user.role]);

  const fetchRecords = async () => {
    try {
      const endpoint = user.role === 'patient'
        ? '/medical-records/records/my_records/'
        : '/medical-records/records/';
      const response = await api.get(endpoint);
      const data = response.data.results || response.data;
      setRecords(data);
      if (data.length > 0 && !selectedRecord) {
        setSelectedRecord(data[0]);
      }
    } catch (error) {
      message.error('Failed to load medical records');
    } finally {
      setLoading(false);
    }
  };

  const fetchPatients = async () => {
    try {
      const response = await api.get('/users/?role=patient');
      setPatients(response.data.results || response.data);
    } catch (error) {
      console.error('Could not load patient list', error);
    }
  };

  const handleCreateRecord = async (values) => {
    setCreating(true);
    try {
      const recordPayload = {
        patient: values.patient,
        diagnosis: values.diagnosis,
        symptoms: values.symptoms,
        treatment_plan: values.treatment_plan,
        notes: values.notes || '',
      };

      const recordResp = await api.post('/medical-records/records/', recordPayload);
      const createdRecord = recordResp.data;

      // If prescription details are provided, save prescription as well
      if (values.medication_name) {
        await api.post('/medical-records/prescriptions/', {
          medical_record: createdRecord.id,
          medication_name: values.medication_name,
          dosage: values.dosage || 'Standard dose',
          frequency: values.frequency || 'Once daily',
          duration: values.duration || '7 days',
          instructions: values.instructions || '',
        });
      }

      message.success('Medical record created successfully');
      form.resetFields();
      setIsModalOpen(false);
      await fetchRecords();
      setSelectedRecord(createdRecord);
    } catch (error) {
      const err = error.response?.data?.detail || 'Failed to create medical record';
      message.error(err);
    } finally {
      setCreating(false);
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 80 }}>
        <Spin size="large" tip="Loading medical records..." />
      </div>
    );
  }

  const prescriptionColumns = [
    { title: 'Medication', dataIndex: 'medication_name', key: 'medication_name' },
    { title: 'Dosage', dataIndex: 'dosage', key: 'dosage' },
    { title: 'Frequency', dataIndex: 'frequency', key: 'frequency' },
    { title: 'Duration', dataIndex: 'duration', key: 'duration' },
  ];

  const labTestColumns = [
    { title: 'Test Name', dataIndex: 'test_name', key: 'test_name' },
    { title: 'Type', dataIndex: 'test_type', key: 'test_type' },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (s) => <Tag color={statusColor(s)}>{s}</Tag>,
    },
    {
      title: 'Result',
      dataIndex: 'result',
      key: 'result',
      render: (r) => r || 'Pending',
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>
          <Space><FileTextOutlined />Medical Records</Space>
        </Title>
        {(user.role === 'doctor' || user.role === 'admin') && (
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setIsModalOpen(true)}
          >
            New Medical Record
          </Button>
        )}
      </div>

      <Row gutter={[16, 16]}>
        {/* Records List */}
        <Col xs={24} lg={selectedRecord ? 8 : 24}>
          {records.length === 0 ? (
            <Card bordered={false} style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
              <Empty description="No medical records found" />
            </Card>
          ) : (
            <List
              dataSource={records}
              renderItem={(record) => (
                <Card
                  key={record.id}
                  bordered={false}
                  className={`stat-card-hover ${selectedRecord?.id === record.id ? 'record-card-active' : ''}`}
                  style={{
                    marginBottom: 12,
                    cursor: 'pointer',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
                    border: selectedRecord?.id === record.id ? '1px solid #1677ff' : '1px solid transparent',
                    transition: 'all 0.2s',
                  }}
                  onClick={() => setSelectedRecord(record)}
                >
                  <Space>
                    <FileTextOutlined style={{ color: '#1677ff', fontSize: 18 }} />
                    <div>
                      <Text strong>{record.diagnosis}</Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        Dr. {record.doctor_details?.first_name || ''} {record.doctor_details?.last_name || ''}
                        {' · '}
                        {new Date(record.created_at).toLocaleDateString()}
                      </Text>
                    </div>
                  </Space>
                </Card>
              )}
            />
          )}
        </Col>

        {/* Record Details */}
        {selectedRecord && (
          <Col xs={24} lg={16}>
            <Card
              bordered={false}
              title={selectedRecord.diagnosis}
              style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}
            >
              <Descriptions bordered column={2} size="small" style={{ marginBottom: 20 }}>
                <Descriptions.Item label="Patient">
                  {selectedRecord.patient_details?.first_name} {selectedRecord.patient_details?.last_name}
                </Descriptions.Item>
                <Descriptions.Item label="Doctor">
                  Dr. {selectedRecord.doctor_details?.first_name} {selectedRecord.doctor_details?.last_name}
                </Descriptions.Item>
                <Descriptions.Item label="Date">
                  {new Date(selectedRecord.created_at).toLocaleDateString()}
                </Descriptions.Item>
                <Descriptions.Item label="Last Updated">
                  {new Date(selectedRecord.updated_at).toLocaleDateString()}
                </Descriptions.Item>
              </Descriptions>

              <div style={{ marginBottom: 20 }}>
                <Title level={5}>Symptoms</Title>
                <Card size="small" style={{ background: '#fafafa' }}>
                  <Text>{selectedRecord.symptoms}</Text>
                </Card>
              </div>

              <div style={{ marginBottom: 20 }}>
                <Title level={5}>Treatment Plan</Title>
                <Card size="small" style={{ background: '#fafafa' }}>
                  <Text>{selectedRecord.treatment_plan}</Text>
                </Card>
              </div>

              {selectedRecord.notes && (
                <div style={{ marginBottom: 20 }}>
                  <Title level={5}>Doctor Notes</Title>
                  <Card size="small" style={{ background: '#fafafa' }}>
                    <Text>{selectedRecord.notes}</Text>
                  </Card>
                </div>
              )}

              {selectedRecord.prescriptions?.length > 0 && (
                <div style={{ marginBottom: 20 }}>
                  <Title level={5}><Space><MedicineBoxOutlined />Prescriptions</Space></Title>
                  <Table
                    dataSource={selectedRecord.prescriptions}
                    columns={prescriptionColumns}
                    rowKey="id"
                    size="small"
                    pagination={false}
                  />
                </div>
              )}

              {selectedRecord.lab_tests?.length > 0 && (
                <div>
                  <Title level={5}>Lab Tests</Title>
                  <Table
                    dataSource={selectedRecord.lab_tests}
                    columns={labTestColumns}
                    rowKey="id"
                    size="small"
                    pagination={false}
                  />
                </div>
              )}
            </Card>
          </Col>
        )}
      </Row>

      {/* Doctor Create Medical Record Modal */}
      <Modal
        title="Add Clinical Medical Record"
        open={isModalOpen}
        onCancel={() => setIsModalOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={creating}
        width={650}
        okText="Save Record"
      >
        <Form form={form} layout="vertical" onFinish={handleCreateRecord}>
          <Form.Item
            name="patient"
            label="Select Patient"
            rules={[{ required: true, message: 'Please select a patient' }]}
          >
            <Select placeholder="Choose patient">
              {patients.map((p) => (
                <Option key={p.id} value={p.id}>
                  {p.first_name} {p.last_name} ({p.email || p.username})
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="diagnosis"
            label="Primary Diagnosis"
            rules={[{ required: true, message: 'Please enter diagnosis' }]}
          >
            <Input placeholder="e.g. Acute Bronchitis" />
          </Form.Item>

          <Form.Item
            name="symptoms"
            label="Reported Symptoms"
            rules={[{ required: true, message: 'Please describe symptoms' }]}
          >
            <TextArea rows={2} placeholder="e.g. Persistent dry cough, mild fever (38C), fatigue for 4 days" />
          </Form.Item>

          <Form.Item
            name="treatment_plan"
            label="Treatment Plan"
            rules={[{ required: true, message: 'Please outline treatment plan' }]}
          >
            <TextArea rows={2} placeholder="e.g. Prescribed antibiotics, hydration, bed rest for 3 days" />
          </Form.Item>

          <Form.Item name="notes" label="Clinical Notes (optional)">
            <TextArea rows={2} placeholder="Internal observations or follow-up notes" />
          </Form.Item>

          <div style={{
            background: '#f9fafb',
            padding: 16,
            borderRadius: 8,
            border: '1px solid #e5e7eb',
            marginTop: 12,
          }}>
            <Text strong style={{ display: 'block', marginBottom: 12 }}>
              <MedicineBoxOutlined style={{ marginRight: 6, color: '#1677ff' }} />
              Attach Initial Prescription (Optional)
            </Text>
            <Row gutter={12}>
              <Col span={12}>
                <Form.Item name="medication_name" label="Medication Name" style={{ marginBottom: 8 }}>
                  <Input placeholder="e.g. Amoxicillin" />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="dosage" label="Dosage" style={{ marginBottom: 8 }}>
                  <Input placeholder="e.g. 500mg" />
                </Form.Item>
              </Col>
            </Row>
            <Row gutter={12}>
              <Col span={12}>
                <Form.Item name="frequency" label="Frequency" style={{ marginBottom: 8 }}>
                  <Input placeholder="e.g. 3 times daily after meals" />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="duration" label="Duration" style={{ marginBottom: 8 }}>
                  <Input placeholder="e.g. 7 days" />
                </Form.Item>
              </Col>
            </Row>
          </div>
        </Form>
      </Modal>
    </div>
  );
}

export default MedicalRecords;
