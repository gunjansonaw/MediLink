import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  Form, Input, Button, Card, Alert, Typography,
  Space, Select, Row, Col, InputNumber,
} from 'antd';
import {
  UserOutlined, LockOutlined, MailOutlined,
  PhoneOutlined, HeartFilled, TeamOutlined,
  IdcardOutlined, DollarOutlined,
} from '@ant-design/icons';
import { useAuth } from '../../context/AuthContext';

const { Title, Text } = Typography;
const { Option } = Select;

function Register() {
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { register } = useAuth();
  const [form] = Form.useForm();
  const selectedRole = Form.useWatch('role', form);

  const handleSubmit = async (values) => {
    setError('');
    setLoading(true);

    const userData = {
      username: values.username,
      first_name: values.first_name,
      last_name: values.last_name,
      email: values.email,
      phone: values.phone || '',
      role: values.role,
      password: values.password,
      password2: values.password2,
    };

    if (values.role === 'patient') {
      userData.patient_profile = {
        emergency_contact: values.phone || '',
        emergency_contact_name: '',
      };
    } else if (values.role === 'doctor') {
      userData.doctor_profile = {
        specialization: values.specialization || 'General Medicine',
        license_number: values.license_number || `MED-${Math.floor(100000 + Math.random() * 900000)}`,
        experience_years: values.experience_years || 1,
        consultation_fee: values.consultation_fee || 50.00,
      };
    }

    const result = await register(userData);

    if (result.success) {
      navigate('/login');
    } else {
      const errMsg = typeof result.error === 'object'
        ? Object.entries(result.error).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`).join(' | ')
        : result.error;
      setError(errMsg || 'Registration failed');
    }

    setLoading(false);
  };

  return (
    <div className="auth-bg">
      <Card
        style={{
          width: '100%',
          maxWidth: 560,
          borderRadius: 16,
          boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
          margin: '24px 0',
        }}
        bodyStyle={{ padding: '40px 40px 32px' }}
      >
        {/* Brand Header */}
        <Space direction="vertical" align="center" style={{ width: '100%', marginBottom: 28 }}>
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: 16,
              background: 'linear-gradient(135deg, #1677ff, #0050b3)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <HeartFilled style={{ fontSize: 32, color: '#fff' }} />
          </div>
          <Title level={2} style={{ margin: 0, color: '#001529' }}>
            MediLink
          </Title>
          <Text type="secondary">Enterprise Telehealth & Hospital SaaS</Text>
        </Space>

        <Title level={4} style={{ marginBottom: 20, color: '#1d2939' }}>
          Create Your Account
        </Title>

        {error && (
          <Alert
            message={error}
            type="error"
            showIcon
            style={{ marginBottom: 20, borderRadius: 8 }}
          />
        )}

        <Form
          form={form}
          name="register"
          onFinish={handleSubmit}
          layout="vertical"
          size="large"
          requiredMark={false}
          initialValues={{ 
            role: 'patient',
            specialization: 'General Medicine',
            consultation_fee: 75.00,
            experience_years: 3,
          }}
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="first_name"
                label="First Name"
                rules={[{ required: true, message: 'Required' }]}
              >
                <Input prefix={<UserOutlined style={{ color: '#bfbfbf' }} />} placeholder="First name" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="last_name"
                label="Last Name"
                rules={[{ required: true, message: 'Required' }]}
              >
                <Input prefix={<UserOutlined style={{ color: '#bfbfbf' }} />} placeholder="Last name" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="username"
            label="Username"
            rules={[{ required: true, message: 'Please enter a username' }]}
          >
            <Input prefix={<UserOutlined style={{ color: '#bfbfbf' }} />} placeholder="Choose a username" />
          </Form.Item>

          <Form.Item
            name="email"
            label="Email"
            rules={[
              { required: true, message: 'Please enter your email' },
              { type: 'email', message: 'Invalid email address' },
            ]}
          >
            <Input prefix={<MailOutlined style={{ color: '#bfbfbf' }} />} placeholder="Enter email address" />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="phone" label="Phone (optional)">
                <Input prefix={<PhoneOutlined style={{ color: '#bfbfbf' }} />} placeholder="Phone number" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="role"
                label="Register as"
                rules={[{ required: true }]}
              >
                <Select prefix={<TeamOutlined />} placeholder="Select role">
                  <Option value="patient">Patient</Option>
                  <Option value="doctor">Doctor</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>

          {/* Conditional Doctor Fields */}
          {selectedRole === 'doctor' && (
            <div style={{
              background: '#f6f9fe',
              padding: '16px 16px 4px',
              borderRadius: 8,
              border: '1px solid #d4e3fc',
              marginBottom: 16,
            }}>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name="specialization"
                    label="Specialization"
                    rules={[{ required: true, message: 'Required' }]}
                  >
                    <Select placeholder="Select specialty">
                      <Option value="General Medicine">General Medicine</Option>
                      <Option value="Cardiology">Cardiology</Option>
                      <Option value="Pediatrics">Pediatrics</Option>
                      <Option value="Dermatology">Dermatology</Option>
                      <Option value="Neurology">Neurology</Option>
                      <Option value="Orthopedics">Orthopedics</Option>
                      <Option value="Psychiatry">Psychiatry</Option>
                    </Select>
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="license_number"
                    label="Medical License #"
                    rules={[{ required: true, message: 'Required' }]}
                  >
                    <Input prefix={<IdcardOutlined style={{ color: '#bfbfbf' }} />} placeholder="e.g. MED-88219" />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name="consultation_fee"
                    label="Consultation Fee ($)"
                    rules={[{ required: true, message: 'Required' }]}
                  >
                    <InputNumber style={{ width: '100%' }} min={0} step={5} prefix={<DollarOutlined />} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="experience_years"
                    label="Experience (Years)"
                    rules={[{ required: true, message: 'Required' }]}
                  >
                    <InputNumber style={{ width: '100%' }} min={0} max={60} />
                  </Form.Item>
                </Col>
              </Row>
            </div>
          )}

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="password"
                label="Password"
                rules={[
                  { required: true, message: 'Required' },
                  { min: 8, message: 'At least 8 characters' },
                ]}
              >
                <Input.Password prefix={<LockOutlined style={{ color: '#bfbfbf' }} />} placeholder="Password" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="password2"
                label="Confirm Password"
                dependencies={['password']}
                rules={[
                  { required: true, message: 'Required' },
                  ({ getFieldValue }) => ({
                    validator(_, value) {
                      if (!value || getFieldValue('password') === value) {
                        return Promise.resolve();
                      }
                      return Promise.reject(new Error('Passwords do not match'));
                    },
                  }),
                ]}
              >
                <Input.Password prefix={<LockOutlined style={{ color: '#bfbfbf' }} />} placeholder="Confirm" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item style={{ marginBottom: 16 }}>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              style={{ height: 44, borderRadius: 8, fontWeight: 600 }}
            >
              {loading ? 'Creating account...' : 'Create Account'}
            </Button>
          </Form.Item>
        </Form>

        <div style={{ textAlign: 'center' }}>
          <Text type="secondary">
            Already have an account?{' '}
            <Link to="/login" style={{ fontWeight: 600 }}>
              Sign in here
            </Link>
          </Text>
        </div>
      </Card>
    </div>
  );
}

export default Register;
