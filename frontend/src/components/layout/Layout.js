import React, { useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import {
  Layout as AntLayout, Menu, Avatar, Dropdown, Typography, Space, Button,
} from 'antd';
import {
  DashboardOutlined, CalendarOutlined, FileTextOutlined,
  DollarOutlined, LogoutOutlined, UserOutlined, MenuFoldOutlined,
  MenuUnfoldOutlined, HeartFilled,
} from '@ant-design/icons';
import { useAuth } from '../../context/AuthContext';

const { Sider, Header, Content } = AntLayout;
const { Text } = Typography;

function Layout({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const baseUrl = `/${user.role}`;

  const navItems = [
    {
      key: `${baseUrl}/dashboard`,
      icon: <DashboardOutlined />,
      label: <Link to={`${baseUrl}/dashboard`}>Dashboard</Link>,
    },
    {
      key: `${baseUrl}/appointments`,
      icon: <CalendarOutlined />,
      label: <Link to={`${baseUrl}/appointments`}>Appointments</Link>,
    },
    {
      key: `${baseUrl}/medical-records`,
      icon: <FileTextOutlined />,
      label: <Link to={`${baseUrl}/medical-records`}>Medical Records</Link>,
    },
  ];

  if (user.role === 'admin' || user.role === 'patient') {
    navItems.push({
      key: `${baseUrl}/billing`,
      icon: <DollarOutlined />,
      label: <Link to={`${baseUrl}/billing`}>Billing</Link>,
    });
  }

  const userMenuItems = [
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: 'Logout',
      danger: true,
      onClick: handleLogout,
    },
  ];

  const selectedKey = navItems.find((item) => location.pathname.startsWith(item.key))?.key || '';

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        trigger={null}
        width={220}
        style={{
          position: 'fixed',
          height: '100vh',
          left: 0,
          top: 0,
          bottom: 0,
          zIndex: 100,
        }}
      >
        {/* Logo */}
        <div style={{
          height: 64,
          display: 'flex',
          alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'flex-start',
          padding: collapsed ? '0 20px' : '0 20px',
          borderBottom: '1px solid rgba(255,255,255,0.08)',
        }}>
          <HeartFilled style={{ fontSize: 22, color: '#1677ff' }} />
          {!collapsed && (
            <Text strong style={{ color: '#fff', fontSize: 18, marginLeft: 10 }}>
              MediLink
            </Text>
          )}
        </div>

        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={navItems}
          style={{ marginTop: 8, borderRight: 0 }}
        />
      </Sider>

      <AntLayout style={{ marginLeft: collapsed ? 80 : 220, transition: 'all 0.2s' }}>
        <Header style={{
          position: 'sticky',
          top: 0,
          zIndex: 99,
          background: '#fff',
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          boxShadow: '0 1px 4px rgba(0,21,41,0.08)',
          height: 64,
        }}>
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
            style={{ fontSize: 16, width: 40, height: 40 }}
          />

          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
            <Space style={{ cursor: 'pointer' }}>
              <Avatar
                style={{ backgroundColor: '#1677ff' }}
                icon={<UserOutlined />}
              />
              <Space direction="vertical" size={0}>
                <Text strong style={{ lineHeight: '1.2', fontSize: 14 }}>
                  {user.first_name} {user.last_name}
                </Text>
                <Text
                  type="secondary"
                  style={{ lineHeight: '1.2', fontSize: 12, textTransform: 'capitalize' }}
                >
                  {user.role}
                </Text>
              </Space>
            </Space>
          </Dropdown>
        </Header>

        <Content className="page-content">
          {children}
        </Content>
      </AntLayout>
    </AntLayout>
  );
}

export default Layout;
