import React, { useEffect, useState } from 'react';
import { Modal, Spin, Tag, Space, Typography, Button, Alert, message } from 'antd';
import { ReloadOutlined, FileSearchOutlined } from '@ant-design/icons';
import api from '../../services/api';

const { Text } = Typography;

const LEVEL_COLOR = { critical: 'red', warning: 'orange', info: 'blue' };

/** Renders "**Label:** text" lines from the brief without using innerHTML. */
function BriefText({ content }) {
  return (
    <div style={{ lineHeight: 1.7 }}>
      {(content || '').split('\n').map((line, i) => {
        if (!line.trim()) return <div key={i} style={{ height: 6 }} />;
        const bullet = line.match(/^\s*[-*•]\s+(.*)/);
        const body = bullet ? bullet[1] : line;
        const parts = body.split(/(\*\*[^*]+\*\*)/g).map((p, j) =>
          p.startsWith('**') ? <strong key={j}>{p.slice(2, -2)}</strong> : <React.Fragment key={j}>{p}</React.Fragment>);
        return <div key={i} style={bullet ? { paddingLeft: 14 } : undefined}>{bullet ? '• ' : ''}{parts}</div>;
      })}
    </div>
  );
}

function BriefModal({ appointment, open, onClose }) {
  const [brief, setBrief] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = async (refresh = false) => {
    setLoading(true);
    try {
      const r = refresh
        ? await api.post(`/ai/briefs/${appointment.id}/`)
        : await api.get(`/ai/briefs/${appointment.id}/`);
      setBrief(r.data);
    } catch (err) {
      message.error(err.response?.data?.error || 'Could not load brief');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open && appointment) {
      setBrief(null);
      load();
    }
  }, [open, appointment?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Modal
      open={open}
      onCancel={onClose}
      width={680}
      title={<Space><FileSearchOutlined />Pre-visit brief
        {appointment && <Text type="secondary" style={{ fontWeight: 400 }}>
          · {appointment.patient_details?.first_name} {appointment.patient_details?.last_name} · {appointment.appointment_date} {appointment.appointment_time?.slice(0, 5)}
        </Text>}
      </Space>}
      footer={[
        <Button key="r" icon={<ReloadOutlined />} onClick={() => load(true)} loading={loading}>Regenerate</Button>,
        <Button key="c" type="primary" onClick={onClose}>Close</Button>,
      ]}
    >
      {loading && !brief ? <Spin /> : brief && (
        <Space direction="vertical" style={{ width: '100%' }}>
          {brief.highlights?.length > 0 && (
            <Space wrap size={[4, 6]}>
              {brief.highlights.map((h, i) => <Tag key={i} color={LEVEL_COLOR[h.level]}>{h.text}</Tag>)}
            </Space>
          )}
          <BriefText content={brief.content} />
          <Alert type="info" showIcon style={{ marginTop: 8 }}
            message={`${brief.source === 'llm' ? 'AI-generated' : 'Rule-based'} summary · ${new Date(brief.generated_at).toLocaleString()} · verify against the chart.`} />
        </Space>
      )}
    </Modal>
  );
}

export default BriefModal;
