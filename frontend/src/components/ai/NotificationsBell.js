import React, { useCallback, useEffect, useState } from 'react';
import { Badge, Button, Dropdown, Empty, List, Typography, Space, Tag } from 'antd';
import { BellOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import api from '../../services/api';

const { Text } = Typography;

const KIND_COLOR = {
  appointment_reminder: 'blue', payment_reminder: 'gold', care_followup: 'green',
  lab_result: 'purple', safety_alert: 'red', agent: 'cyan',
};

function NotificationsBell() {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  const load = useCallback(async () => {
    try {
      const r = await api.get('/ai/notifications/');
      setItems(r.data.results || r.data);
    } catch {
      /* non-critical */
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 60000);
    return () => clearInterval(id);
  }, [load]);

  const unread = items.filter((n) => !n.read_at).length;

  const openItem = async (n) => {
    if (!n.read_at) {
      await api.post(`/ai/notifications/${n.id}/read/`).catch(() => {});
      load();
    }
    setOpen(false);
    if (n.link) navigate(n.link);
  };

  const markAll = async () => {
    await api.post('/ai/notifications/read_all/').catch(() => {});
    load();
  };

  const panel = (
    <div style={{ width: 360, maxWidth: '90vw', background: '#fff', borderRadius: 8, boxShadow: '0 6px 16px rgba(0,0,0,0.12)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 14px', borderBottom: '1px solid #f0f0f0' }}>
        <Text strong>Notifications</Text>
        {unread > 0 && <Button type="link" size="small" onClick={markAll}>Mark all read</Button>}
      </div>
      <div style={{ maxHeight: 420, overflowY: 'auto' }}>
        {items.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="You're all caught up" style={{ padding: 24 }} />
        ) : (
          <List
            dataSource={items}
            renderItem={(n) => (
              <List.Item onClick={() => openItem(n)}
                style={{ padding: '10px 14px', cursor: 'pointer', background: n.read_at ? '#fff' : '#f0f7ff' }}>
                <Space direction="vertical" size={2} style={{ width: '100%' }}>
                  <Space>
                    <Tag color={KIND_COLOR[n.kind]} style={{ marginRight: 0 }}>{n.kind.replace('_', ' ')}</Tag>
                    <Text type="secondary" style={{ fontSize: 11 }}>{new Date(n.created_at).toLocaleString()}</Text>
                  </Space>
                  <Text strong>{n.title}</Text>
                  <Text type="secondary" style={{ fontSize: 12 }} ellipsis={{ rows: 3 }}>{n.body}</Text>
                </Space>
              </List.Item>
            )}
          />
        )}
      </div>
    </div>
  );

  return (
    <Dropdown dropdownRender={() => panel} trigger={['click']} open={open} onOpenChange={setOpen} placement="bottomRight">
      <Badge count={unread} size="small" offset={[-4, 4]}>
        <Button type="text" shape="circle" icon={<BellOutlined style={{ fontSize: 18 }} />} aria-label="Notifications" />
      </Badge>
    </Dropdown>
  );
}

export default NotificationsBell;
