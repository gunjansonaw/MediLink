import React, { useEffect, useState } from 'react';
import {
  Card, Table, Tag, Typography, Space, Button, Row, Col, Tabs, message, Tooltip,
} from 'antd';
import { RobotOutlined, PlayCircleOutlined, AuditOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import api from '../../services/api';
import PendingActionCard from './PendingActionCard';

const { Title, Text } = Typography;

const STATUS_COLOR = { ok: 'green', error: 'red', denied: 'volcano', proposed: 'gold' };

const AGENTS = [
  { key: 'collections', title: 'Collections agent', desc: 'Reminds, offers payment plans, escalates overdue invoices.' },
  { key: 'care-followups', title: 'Care follow-up agent', desc: 'Nudges chronic-care patients and abnormal labs without a visit.' },
  { key: 'briefs', title: 'Pre-visit brief agent', desc: 'Prepares briefs for visits in the next 36 hours.' },
];

function AIOps() {
  const [pending, setPending] = useState([]);
  const [audit, setAudit] = useState([]);
  const [auditTotal, setAuditTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [claims, setClaims] = useState([]);
  const [prechecks, setPrechecks] = useState({});
  const [running, setRunning] = useState(null);

  const loadPending = () => api.get('/ai/pending-actions/?status=pending')
    .then((r) => setPending(r.data.results || r.data)).catch(() => {});
  const loadAudit = (p = 1) => api.get(`/ai/audit-log/?page=${p}`)
    .then((r) => { setAudit(r.data.results || r.data); setAuditTotal(r.data.count || 0); setPage(p); }).catch(() => {});
  const loadClaims = () => api.get('/billing/insurance-claims/')
    .then((r) => setClaims(r.data.results || r.data)).catch(() => {});

  useEffect(() => { loadPending(); loadAudit(); loadClaims(); }, []);

  const runAgent = async (key) => {
    setRunning(key);
    try {
      const r = await api.post(`/ai/agents/${key}/run/`);
      message.success(`${key}: ${JSON.stringify(r.data.result)}`);
      loadAudit();
    } catch {
      message.error('Agent run failed');
    } finally {
      setRunning(null);
    }
  };

  const precheck = async (claim) => {
    setPrechecks((p) => ({ ...p, [claim.id]: { loading: true } }));
    try {
      const r = await api.post(`/ai/claims/${claim.id}/precheck/`);
      setPrechecks((p) => ({ ...p, [claim.id]: r.data }));
    } catch {
      setPrechecks((p) => ({ ...p, [claim.id]: null }));
      message.error('Pre-check failed');
    }
  };

  const decide = async (claim, verb) => {
    try {
      const body = verb === 'approve' ? { approved_amount: claim.claim_amount } : {};
      await api.post(`/billing/insurance-claims/${claim.id}/${verb}/`, body);
      message.success(`Claim ${verb}d`);
      loadClaims();
    } catch (err) {
      message.error(err.response?.data?.error || 'Failed');
    }
  };

  const auditColumns = [
    { title: 'When', dataIndex: 'created_at', render: (d) => new Date(d).toLocaleString(), width: 170 },
    { title: 'Agent', dataIndex: 'agent', render: (a) => <Tag>{a}</Tag> },
    { title: 'User', dataIndex: 'username', render: (u) => u || <Text type="secondary">system</Text> },
    { title: 'Tool', dataIndex: 'tool_name', render: (t) => <Text code>{t}</Text> },
    { title: 'Status', dataIndex: 'status', render: (s) => <Tag color={STATUS_COLOR[s]}>{s}</Tag> },
    { title: 'Input', dataIndex: 'tool_input', ellipsis: true, render: (i) => <Text type="secondary" style={{ fontSize: 12 }}>{JSON.stringify(i)}</Text> },
    { title: 'ms', dataIndex: 'duration_ms', width: 60 },
  ];

  const claimColumns = [
    { title: 'Claim', dataIndex: 'claim_number' },
    { title: 'Patient', render: (_, c) => `${c.patient_details?.first_name || ''} ${c.patient_details?.last_name || ''}` },
    { title: 'Provider', dataIndex: 'insurance_provider' },
    { title: 'Amount', dataIndex: 'claim_amount', render: (v) => `$${v}` },
    { title: 'Status', dataIndex: 'status', render: (s) => <Tag>{s}</Tag> },
    {
      title: 'AI pre-check',
      render: (_, c) => {
        const r = prechecks[c.id];
        if (!r) return <Button size="small" onClick={() => precheck(c)}>Run</Button>;
        if (r.loading) return <Text type="secondary">Checking…</Text>;
        return (
          <Tooltip title={r.summary}>
            <Tag color={{ high: 'red', medium: 'orange', low: 'green' }[r.risk]}>{r.risk} risk · {r.issues.length} issues</Tag>
          </Tooltip>
        );
      },
    },
    {
      title: 'Decision',
      render: (_, c) => (['submitted', 'under_review'].includes(c.status) ? (
        <Space>
          <Button size="small" type="primary" onClick={() => decide(c, 'approve')}>Approve</Button>
          <Button size="small" danger onClick={() => decide(c, 'reject')}>Reject</Button>
        </Space>
      ) : null),
    },
  ];

  return (
    <div>
      <Title level={3} style={{ marginBottom: 24 }}><Space><RobotOutlined />AI Operations</Space></Title>
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        {AGENTS.map((a) => (
          <Col xs={24} md={8} key={a.key}>
            <Card size="small" bordered={false} style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)', height: '100%' }}>
              <Space direction="vertical">
                <Text strong>{a.title}</Text>
                <Text type="secondary" style={{ fontSize: 12 }}>{a.desc}</Text>
                <Button size="small" icon={<PlayCircleOutlined />} loading={running === a.key} onClick={() => runAgent(a.key)}>
                  Run now
                </Button>
              </Space>
            </Card>
          </Col>
        ))}
      </Row>
      <Card bordered={false} style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
        <Tabs items={[
          {
            key: 'pending',
            label: <Space><SafetyCertificateOutlined />Approvals ({pending.length})</Space>,
            children: pending.length === 0 ? <Text type="secondary">No actions waiting for approval.</Text>
              : pending.map((a) => <PendingActionCard key={a.id} action={a} onDecided={loadPending} />),
          },
          {
            key: 'claims',
            label: 'Insurance claims',
            children: <Table rowKey="id" size="small" columns={claimColumns} dataSource={claims} scroll={{ x: 800 }} pagination={false} />,
          },
          {
            key: 'audit',
            label: <Space><AuditOutlined />Audit log</Space>,
            children: (
              <Table rowKey="id" size="small" columns={auditColumns} dataSource={audit} scroll={{ x: 900 }}
                pagination={{ current: page, total: auditTotal, pageSize: 10, onChange: loadAudit, showSizeChanger: false }} />
            ),
          },
        ]} />
      </Card>
    </div>
  );
}

export default AIOps;
