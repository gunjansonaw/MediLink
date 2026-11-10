import React, { useState } from 'react';
import { Card, Button, Space, Tag, Typography, message } from 'antd';
import { CheckOutlined, CloseOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import api from '../../services/api';

const { Text } = Typography;

const STATUS_COLOR = {
  pending: 'gold', approved: 'green', rejected: 'default', failed: 'red', expired: 'default',
};

/**
 * Human-in-the-loop approval card. Agents can only *propose* changes;
 * nothing is written until a person clicks Approve here.
 */
function PendingActionCard({ action, onDecided, canDecide = true }) {
  const [busy, setBusy] = useState(null);
  const [state, setState] = useState(action);

  const decide = async (verb) => {
    setBusy(verb);
    try {
      const resp = await api.post(`/ai/pending-actions/${state.id}/${verb}/`);
      setState(resp.data);
      if (resp.data.status === 'failed') {
        message.error(resp.data.result?.error || 'Action failed');
      } else if (verb === 'approve') {
        message.success(resp.data.result?.message || 'Done');
      }
      onDecided?.(resp.data);
    } catch (err) {
      message.error(err.response?.data?.error || 'Could not update action');
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card
      size="small"
      style={{ borderColor: state.status === 'pending' ? '#faad14' : '#f0f0f0', marginTop: 8 }}
      bodyStyle={{ padding: 12 }}
    >
      <Space direction="vertical" style={{ width: '100%' }} size={6}>
        <Space wrap>
          <SafetyCertificateOutlined style={{ color: '#faad14' }} />
          <Text strong>Needs approval</Text>
          <Tag color={STATUS_COLOR[state.status]}>{state.status}</Tag>
          {state.approver_role === 'admin' && <Tag color="purple">admin</Tag>}
        </Space>
        <Text>{state.summary}</Text>
        {state.result?.message && <Text type="success">{state.result.message}</Text>}
        {state.result?.error && <Text type="danger">{state.result.error}</Text>}
        {state.status === 'pending' && canDecide && (
          <Space>
            <Button type="primary" size="small" icon={<CheckOutlined />} loading={busy === 'approve'}
              onClick={() => decide('approve')}>
              Approve
            </Button>
            <Button size="small" icon={<CloseOutlined />} loading={busy === 'reject'} onClick={() => decide('reject')}>
              Reject
            </Button>
          </Space>
        )}
      </Space>
    </Card>
  );
}

export default PendingActionCard;
