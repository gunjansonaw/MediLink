import React from 'react';
import { Card, Tag, Typography, Space, List, Alert } from 'antd';
import {
  ResponsiveContainer, BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
} from 'recharts';

const { Text } = Typography;

const SEVERITY_COLOR = { critical: 'red', warning: 'orange', info: 'blue' };

const TOOL_LABELS = {
  search_doctors: 'Doctors found',
  get_available_slots: 'Available slots',
  list_appointments: 'Appointments',
  list_my_invoices: 'Invoices',
  check_prescription_safety: 'Prescription safety check',
  appointment_analytics: 'Appointment analytics',
  revenue_analytics: 'Revenue analytics',
  no_show_report: 'No-show report',
  outstanding_balances: 'Outstanding balances',
  insurance_claim_precheck: 'Claim pre-check',
};

function Chart({ data }) {
  const rows = data.rows || [];
  if (!rows.length) return <Text type="secondary">No data in this range.</Text>;
  const isLine = data.chart?.type === 'line';
  const money = (data.metric || '').includes('revenue');
  const fmt = (v) => (money ? `$${Number(v).toLocaleString()}` : v);
  return (
    <ResponsiveContainer width="100%" height={220}>
      {isLine ? (
        <LineChart data={rows}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip formatter={fmt} />
          <Line type="monotone" dataKey="value" stroke="#1677ff" strokeWidth={2} dot={{ r: 3 }} />
        </LineChart>
      ) : (
        <BarChart data={rows}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} interval={0} />
          <YAxis tick={{ fontSize: 11 }} allowDecimals={!!money} />
          <Tooltip formatter={fmt} />
          <Bar dataKey="value" fill="#1677ff" radius={[4, 4, 0, 0]} />
        </BarChart>
      )}
    </ResponsiveContainer>
  );
}

export function SafetyFindings({ findings }) {
  if (!findings?.length) {
    return <Alert type="success" showIcon message="No issues found by the safety engine." />;
  }
  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      {findings.map((f, i) => (
        <Alert
          key={i}
          type={f.severity === 'critical' ? 'error' : f.severity === 'warning' ? 'warning' : 'info'}
          showIcon
          message={<><Tag color={SEVERITY_COLOR[f.severity]}>{f.category}</Tag>{f.message}</>}
        />
      ))}
    </Space>
  );
}

function Body({ result }) {
  if (result.rows) return <Chart data={result} />;
  if (result.doctors) {
    return (
      <List size="small" dataSource={result.doctors} locale={{ emptyText: result.note || 'None' }}
        renderItem={(d) => (
          <List.Item>
            <Space wrap><Text strong>{d.name}</Text><Tag>{d.specialization}</Tag>
              {d.consultation_fee != null && <Text type="secondary">${d.consultation_fee}</Text>}</Space>
          </List.Item>
        )} />
    );
  }
  if (result.slots) {
    return (
      <Space wrap size={[4, 4]}>
        {result.slots.slice(0, 16).map((s) => <Tag key={`${s.date}-${s.time}`}>{s.date} {s.time}</Tag>)}
        {!result.slots.length && <Text type="secondary">No free slots in this range.</Text>}
      </Space>
    );
  }
  if (result.findings) return <SafetyFindings findings={result.findings} />;
  if (result.issues) {
    return (
      <Space direction="vertical" style={{ width: '100%' }}>
        <Text>Risk: <Tag color={{ high: 'red', medium: 'orange', low: 'green' }[result.risk]}>{result.risk}</Tag></Text>
        {result.issues.map((i) => <Text key={i.code}>• {i.message}</Text>)}
      </Space>
    );
  }
  const list = result.appointments || result.invoices;
  if (list) {
    return (
      <List size="small" dataSource={list} locale={{ emptyText: 'None' }}
        renderItem={(r) => (
          <List.Item>
            {r.appointment_id
              ? `${r.date} ${r.time} · ${r.doctor} · ${r.patient} · ${r.status}`
              : `#${r.number} · ${r.patient ? `${r.patient} · ` : ''}$${r.balance} due ${r.due_date}${r.days_overdue ? ` (${r.days_overdue}d overdue)` : ''}`}
          </List.Item>
        )} />
    );
  }
  return null;
}

function ToolResultCard({ call }) {
  if (!call.result) return null;
  const body = Body({ result: call.result });
  if (!body) return null;
  return (
    <Card size="small" title={<Text type="secondary" style={{ fontSize: 12 }}>{TOOL_LABELS[call.tool] || call.tool}</Text>}
      style={{ marginTop: 8 }} bodyStyle={{ padding: 12 }}>
      {body}
    </Card>
  );
}

export default ToolResultCard;
