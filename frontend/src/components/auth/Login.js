import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Form, Input, Button, Card, Alert, Typography, Space } from 'antd';
import { UserOutlined, LockOutlined, HeartFilled } from '@ant-design/icons';
import { useAuth } from '../../context/AuthContext';

const { Title, Text } = Typography;

function Login() {
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { login } = useAuth();

  const handleSubmit = async (values) => {
    setError('');
    setLoading(true);

    const result = await login(values.username, values.password);

    if (result.success) {
      navigate('/');
    } else {
      setError(result.error);
    }

    setLoading(false);
  };

  return (
    <div className="auth-bg">
      <Card
        style={{
          width: '100%',
          maxWidth: 440,
          borderRadius: 16,
          boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
        }}
        bodyStyle={{ padding: '40px 40px 32px' }}
      >
        {/* Brand Header */}
        <Space direction="vertical" align="center" style={{ width: '100%', marginBottom: 32 }}>
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
          <Text type="secondary">Hospital Management System</Text>
        </Space>

        <Title level={4} style={{ marginBottom: 24, color: '#1d2939' }}>
          Sign In
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
          name="login"
          onFinish={handleSubmit}
          layout="vertical"
          size="large"
          requiredMark={false}
        >
          <Form.Item
            name="username"
            label="Username or Email"
            rules={[{ required: true, message: 'Please enter your username or email' }]}
          >
            <Input
              prefix={<UserOutlined style={{ color: '#bfbfbf' }} />}
              placeholder="Enter username or email"
              autoFocus
            />
          </Form.Item>

          <Form.Item
            name="password"
            label="Password"
            rules={[{ required: true, message: 'Please enter your password' }]}
          >
            <Input.Password
              prefix={<LockOutlined style={{ color: '#bfbfbf' }} />}
              placeholder="Enter password"
            />
          </Form.Item>

          <Form.Item style={{ marginBottom: 16 }}>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              style={{ height: 44, borderRadius: 8, fontWeight: 600 }}
            >
              {loading ? 'Signing in...' : 'Sign In'}
            </Button>
          </Form.Item>
        </Form>

        <div style={{ textAlign: 'center' }}>
          <Text type="secondary">
            Don&apos;t have an account?{' '}
            <Link to="/register" style={{ fontWeight: 600 }}>
              Register here
            </Link>
          </Text>
        </div>
      </Card>
    </div>
  );
}

export default Login;
