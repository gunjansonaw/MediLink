import React, { useState, useEffect } from 'react';
import {
  List, Card, Descriptions, Table, Tag, Typography, Space, Spin,
  Empty, Row, Col, Button, Modal, Form, Input, Select, message, Tooltip,
} from 'antd';
import {
  FileTextOutlined, PlusOutlined, MedicineBoxOutlined, SafetyOutlined, BulbOutlined,
} from '@ant-design/icons';
import api from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { SafetyFindings } from '../ai/ToolResultCard';

const { Title, Text } = Typography;
const { TextArea } = Input;
const { Option } = Select;

const statusColor = (status) =>
  status === 'completed' ? 'green' : 'orange';

const SEVERITY_COLOR = { critical: 'red', warning: 'orange', info: 'blue' };

const fieldErrors = (data) => {
  if (!data) return null;
  if (typeof data === 'string') return data;
  if (data.detail) return data.detail;
  return Object.entries(data).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`).join(' | ');
};

function MedicalRecords() {
  const { user } = useAuth();
  const [records, setRecords] = useState([]);
  const [patients, setPatients] = useState([]);
  const [doctors, setDoctors] = useState([]);
  const [labInsight, setLabInsight] = useState(null);
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
    if (user.role === 'admin') {
      api.get('/users/doctors/').then((r) => setDoctors(r.data)).catch(() => {});
    }
  }, [user.role]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchRecords = async (selectId = null) => {
    try {
      const endpoint = user.role === 'patient'
        ? '/medical-records/records/my_records/'
        : '/medical-records/records/';
      const response = await api.get(endpoint);
      const data = response.data.results || response.data;
      setRecords(data);
      const wanted = selectId ?? selectedRecord?.id;
      setSelectedRecord(data.find((r) => r.id === wanted) || data[0] || null);
    } catch (error) {
      message.error('Failed to load medical records');
    } finally {
      setLoading(false);
    }
  };

  const fetchPatients = async () => {
    try {
      // /users/?role=... was ignored by the API and returned a paginated mix of all users
      const response = await api.get('/users/patients/');
      setPatients(response.data.results || response.data);
    } catch (error) {
      console.error('Could not load patient list', error);
    }
  };

  const saveRecord = async (values) => {
    setCreating(true);
    try {
      const recordPayload = {
        patient: values.patient,
        diagnosis: values.diagnosis,
        symptoms: values.symptoms,
        treatment_plan: values.treatment_plan,
        notes: values.notes || '',
      };
      if (user.role === 'admin') recordPayload.doctor = values.doctor;

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
      await fetchRecords(createdRecord.id);
    } catch (error) {
      message.error(fieldErrors(error.response?.data) || 'Failed to create medical record');
    } finally {
      setCreating(false);
    }
  };

  // Run the prescription safety agent BEFORE saving; require explicit override on findings.
  const handleCreateRecord = async (values) => {
    if (!values.medication_name) {
      saveRecord(values);
      return;
    }
    setCreating(true);
    let check;
    try {
      const resp = await api.post('/ai/prescription-check/', {
        patient: values.patient,
        medication_name: values.medication_name,
        dosage: values.dosage || '',
        frequency: values.frequency || '',
      });
      check = resp.data;
    } catch (error) {
      // A patient with no prior relationship is fine to prescribe for; the post-save check still runs.
      check = null;
    } finally {
      setCreating(false);
    }
    const serious = (check?.findings || []).filter((f) => f.severity !== 'info');
    if (!serious.length) {
      saveRecord(values);
      return;
    }
    Modal.confirm({
      title: <Space><SafetyOutlined style={{ color: '#ff4d4f' }} />Prescription safety check</Space>,
      width: 640,
      icon: null,
      content: (
        <Space direction="vertical" style={{ width: '100%' }}>
          <SafetyFindings findings={check.findings} />
          <Text type="secondary" style={{ fontSize: 12 }}>{check.disclaimer}</Text>
        </Space>
      ),
      okText: 'Prescribe anyway',
      okButtonProps: { danger: true },
      cancelText: 'Go back and edit',
      onOk: () => saveRecord(values),
    });
  };

  const acknowledgeAlert = (alert) => {
    let note = '';
    Modal.confirm({
      title: 'Acknowledge safety alert',
      content: (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Text>{alert.message}</Text>
          <TextArea rows={3} placeholder={alert.severity === 'critical' ? 'Clinical justification (required)' : 'Note (optional)'}
            onChange={(e) => { note = e.target.value; }} />
        </Space>
      ),
      onOk: async () => {
        try {
          await api.post(`/ai/safety-alerts/${alert.id}/acknowledge/`, { note });
          message.success('Alert acknowledged');
          fetchRecords();
        } catch (error) {
          message.error(error.response?.data?.error || 'Could not acknowledge');
          throw error;
        }
      },
    });
  };

  const explainLab = async (lab) => {
    try {
      const resp = await api.get(`/ai/lab-insights/${lab.id}/`);
      setLabInsight({ lab, ...resp.data });
    } catch (error) {
      message.error(error.response?.data?.error || 'Explanation not available');
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
    ...(user.role !== 'patient' ? [{
      title: 'Safety',
      key: 'safety',
      render: (_, rx) => (
        <Space wrap size={[2, 4]}>
          {(rx.safety_alerts || []).length === 0 && <Tag color="green">OK</Tag>}
          {(rx.safety_alerts || []).filter((a) => a.category !== 'unrecognized').map((a) => (
            <Tooltip key={a.id} title={a.message}>
              <Tag
                color={a.acknowledged ? 'default' : SEVERITY_COLOR[a.severity]}
                style={{ cursor: a.acknowledged ? 'default' : 'pointer' }}
                onClick={() => !a.acknowledged && acknowledgeAlert(a)}
              >
                {a.acknowledged ? '✓ ' : ''}{a.category}
              </Tag>
            </Tooltip>
          ))}
        </Space>
      ),
    }] : []),
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
    {
      title: '',
      key: 'explain',
      render: (_, lab) => lab.status === 'completed' && (
        <Button size="small" icon={<BulbOutlined />} onClick={() => explainLab(lab)}>
          {user.role === 'patient' ? 'What does this mean?' : 'Patient explanation'}
        </Button>
      ),
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

      <Modal
        open={!!labInsight}
        onCancel={() => setLabInsight(null)}
        footer={null}
        title={<Space><BulbOutlined />{labInsight?.lab?.test_name}</Space>}
      >
        {labInsight && (
          <Space direction="vertical" style={{ width: '100%' }}>
            {labInsight.abnormal_flags?.length > 0 && (
              <Space wrap>
                {labInsight.abnormal_flags.map((f) => (
                  <Tag key={f.analyte} color="orange">{f.label}: {f.value} {f.unit} ({f.direction}; typical {f.range})</Tag>
                ))}
              </Space>
            )}
            <Text style={{ whiteSpace: 'pre-wrap' }}>{labInsight.patient_explanation}</Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {labInsight.source === 'llm' ? 'AI-generated' : 'Automatically generated'} explanation — not a diagnosis. Your doctor will review the result.
            </Text>
          </Space>
        )}
      </Modal>

      {/* Doctor Create Medical Record Modal */}
      <Modal
        title="Add Clinical Medical Record"
        open={isModalOpen}
        onCancel={() => setIsModalOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={creating}
        width={650}
        okText="Check & Save Record"
      >
        <Form form={form} layout="vertical" onFinish={handleCreateRecord}>
          <Form.Item
            name="patient"
            label="Select Patient"
            rules={[{ required: true, message: 'Please select a patient' }]}
          >
            <Select placeholder="Choose patient" showSearch optionFilterProp="children">
              {patients.map((p) => (
                <Option key={p.id} value={p.id}>
                  {p.first_name} {p.last_name} ({p.email || p.username})
                </Option>
              ))}
            </Select>
          </Form.Item>

          {user.role === 'admin' && (
            <Form.Item name="doctor" label="Attending Doctor" rules={[{ required: true, message: 'Please select a doctor' }]}>
              <Select placeholder="Choose doctor">
                {doctors.map((d) => (
                  <Option key={d.id} value={d.id}>Dr. {d.first_name} {d.last_name}</Option>
                ))}
              </Select>
            </Form.Item>
          )}

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
