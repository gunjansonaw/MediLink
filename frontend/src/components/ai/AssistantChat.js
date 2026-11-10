import React, { useEffect, useRef, useState } from 'react';
import {
  Card, Input, Button, Space, Typography, Tag, List, Empty, Spin, Alert, Row, Col, Tooltip, message,
} from 'antd';
import {
  SendOutlined, RobotOutlined, UserOutlined, PlusOutlined, DeleteOutlined, ThunderboltOutlined,
} from '@ant-design/icons';
import api from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import PendingActionCard from './PendingActionCard';
import ToolResultCard from './ToolResultCard';

const { Title, Text, Paragraph } = Typography;

const SUGGESTIONS = {
  patient: [
    "I've had chest discomfort when climbing stairs — can I see a cardiologist next week, mornings only?",
    'What do my latest lab results mean?',
    'How much do I owe, and when is it due?',
    'Cancel my next appointment',
  ],
  doctor: [
    "Who am I seeing today?",
    'Summarise John Doe\'s history before his visit',
    'Is ibuprofen 400mg three times daily safe for John Doe?',
  ],
  admin: [
    'What was our revenue by month over the last 6 months?',
    'Which doctors have the highest no-show rate this quarter?',
    'Show the most overdue invoices and draft a payment-plan message for the worst one',
    'Pre-check insurance claim 1',
  ],
};

/** Minimal, XSS-safe renderer for the assistant's markdown (bold + bullets + paragraphs). */
function RichText({ text }) {
  const renderInline = (line, key) => {
    const parts = line.split(/(\*\*[^*]+\*\*|_[^_]+_)/g);
    return parts.map((p, i) => {
      if (p.startsWith('**') && p.endsWith('**')) return <strong key={`${key}-${i}`}>{p.slice(2, -2)}</strong>;
      if (p.startsWith('_') && p.endsWith('_') && p.length > 2) return <em key={`${key}-${i}`}>{p.slice(1, -1)}</em>;
      return <React.Fragment key={`${key}-${i}`}>{p}</React.Fragment>;
    });
  };
  const lines = (text || '').split('\n');
  return (
    <div style={{ lineHeight: 1.6 }}>
      {lines.map((line, i) => {
        const bullet = line.match(/^\s*[-*•]\s+(.*)/);
        if (bullet) return <div key={i} style={{ paddingLeft: 14 }}>• {renderInline(bullet[1], i)}</div>;
        if (!line.trim()) return <div key={i} style={{ height: 8 }} />;
        return <div key={i}>{renderInline(line.replace(/^#+\s*/, ''), i)}</div>;
      })}
    </div>
  );
}

function Bubble({ role, children }) {
  const mine = role === 'user';
  return (
    <div style={{ display: 'flex', justifyContent: mine ? 'flex-end' : 'flex-start', marginBottom: 12 }}>
      {!mine && <RobotOutlined style={{ fontSize: 20, color: '#1677ff', marginRight: 8, marginTop: 6 }} />}
      <div style={{
        maxWidth: '82%',
        background: mine ? '#1677ff' : '#fff',
        color: mine ? '#fff' : 'inherit',
        border: mine ? 'none' : '1px solid #f0f0f0',
        borderRadius: 12,
        padding: '10px 14px',
        boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
        overflowWrap: 'anywhere',
      }}>
        {children}
      </div>
      {mine && <UserOutlined style={{ fontSize: 18, color: '#8c8c8c', marginLeft: 8, marginTop: 8 }} />}
    </div>
  );
}

function AssistantChat() {
  const { user } = useAuth();
  const [status, setStatus] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [turns, setTurns] = useState([]); // [{role, text, toolCalls?, pendingActions?}]
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [loadingConv, setLoadingConv] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    api.get('/ai/status/').then((r) => setStatus(r.data)).catch(() => {});
    loadConversations();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [turns, sending]);

  const loadConversations = async () => {
    try {
      const r = await api.get('/ai/conversations/');
      setConversations(r.data.results || r.data);
    } catch {
      /* non-critical */
    }
  };

  const openConversation = async (id) => {
    setLoadingConv(true);
    try {
      const [conv, actions] = await Promise.all([
        api.get(`/ai/conversations/${id}/`),
        api.get(`/ai/pending-actions/?conversation=${id}`),
      ]);
      setConversationId(id);
      const restored = conv.data.messages.map((m) => ({ role: m.role, text: m.text }));
      const acts = actions.data.results || actions.data;
      if (acts.length && restored.length) {
        restored[restored.length - 1].pendingActions = acts;
      }
      setTurns(restored);
    } catch {
      message.error('Could not load conversation');
    } finally {
      setLoadingConv(false);
    }
  };

  const newConversation = () => {
    setConversationId(null);
    setTurns([]);
  };

  const deleteConversation = async (id, e) => {
    e.stopPropagation();
    await api.delete(`/ai/conversations/${id}/`).catch(() => {});
    if (id === conversationId) newConversation();
    loadConversations();
  };

  const send = async (textArg) => {
    const text = (textArg ?? input).trim();
    if (!text || sending) return;
    setInput('');
    setTurns((t) => [...t, { role: 'user', text }]);
    setSending(true);
    try {
      const r = await api.post('/ai/chat/', { message: text, conversation_id: conversationId });
      setConversationId(r.data.conversation_id);
      setTurns((t) => [...t, {
        role: 'assistant',
        text: r.data.reply,
        mode: r.data.mode,
        toolCalls: r.data.tool_calls || [],
        pendingActions: r.data.pending_actions || [],
      }]);
      if (!conversationId) loadConversations();
    } catch (err) {
      const msg = err.response?.status === 429
        ? 'You have reached the assistant usage limit. Please try again later.'
        : err.response?.data?.error || 'The assistant is unavailable right now.';
      setTurns((t) => [...t, { role: 'assistant', text: msg, error: true }]);
    } finally {
      setSending(false);
    }
  };

  const title = { patient: 'Health Assistant', doctor: 'Clinical Copilot', admin: 'Operations Analyst' }[user.role];

  return (
    <div>
      <Space align="center" style={{ marginBottom: 16 }} wrap>
        <Title level={3} style={{ margin: 0 }}><Space><RobotOutlined />{title}</Space></Title>
        {status && (
          status.llm_enabled
            ? <Tag color="blue" icon={<ThunderboltOutlined />}>Claude · {status.model}</Tag>
            : <Tooltip title="Set ANTHROPIC_API_KEY on the backend to enable the full AI agent.">
                <Tag color="orange">Limited mode</Tag>
              </Tooltip>
        )}
      </Space>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={6}>
          <Card size="small" bordered={false} style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}
            title="Conversations"
            extra={<Button size="small" icon={<PlusOutlined />} onClick={newConversation}>New</Button>}>
            <List
              size="small"
              dataSource={conversations}
              locale={{ emptyText: 'No conversations yet' }}
              renderItem={(c) => (
                <List.Item
                  onClick={() => openConversation(c.id)}
                  style={{ cursor: 'pointer', background: c.id === conversationId ? '#e6f4ff' : undefined, borderRadius: 6, paddingLeft: 8 }}
                  actions={[<DeleteOutlined key="d" onClick={(e) => deleteConversation(c.id, e)} />]}
                >
                  <Text ellipsis style={{ maxWidth: 170 }}>{c.title || `Conversation ${c.id}`}</Text>
                </List.Item>
              )}
            />
          </Card>
        </Col>

        <Col xs={24} lg={18}>
          <Card bordered={false} style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }} bodyStyle={{ padding: 0 }}>
            <div style={{ height: 'calc(100vh - 300px)', minHeight: 360, overflowY: 'auto', padding: 16, background: '#fafbfc' }}>
              {loadingConv && <Spin />}
              {!turns.length && !loadingConv && (
                <div style={{ paddingTop: 24 }}>
                  <Empty image={<RobotOutlined style={{ fontSize: 48, color: '#1677ff' }} />}
                    description={<Text type="secondary">Ask me anything. I can look things up and prepare actions — you approve before anything changes.</Text>} />
                  <Space direction="vertical" style={{ width: '100%', marginTop: 16 }}>
                    {(SUGGESTIONS[user.role] || []).map((s) => (
                      <Button key={s} block style={{ textAlign: 'left', whiteSpace: 'normal', height: 'auto', padding: '8px 12px' }}
                        onClick={() => send(s)}>{s}</Button>
                    ))}
                  </Space>
                </div>
              )}
              {turns.map((t, i) => (
                <div key={i}>
                  <Bubble role={t.role}>
                    {t.role === 'user' ? <Paragraph style={{ color: '#fff', margin: 0, whiteSpace: 'pre-wrap' }}>{t.text}</Paragraph>
                      : t.error ? <Text type="danger">{t.text}</Text> : <RichText text={t.text} />}
                    {t.mode === 'guardrail' && <Alert type="error" showIcon style={{ marginTop: 8 }} message="Emergency guidance" />}
                  </Bubble>
                  {(t.toolCalls || []).map((c, j) => (
                    <div key={`c${j}`} style={{ marginLeft: 28, maxWidth: '82%' }}><ToolResultCard call={c} /></div>
                  ))}
                  {(t.pendingActions || []).map((a) => (
                    <div key={`a${a.id}`} style={{ marginLeft: 28, maxWidth: '82%' }}>
                      <PendingActionCard action={a} canDecide={a.approver_role === 'self' || user.role === 'admin'} />
                    </div>
                  ))}
                </div>
              ))}
              {sending && (
                <Bubble role="assistant"><Space><Spin size="small" /><Text type="secondary">Working on it…</Text></Space></Bubble>
              )}
              <div ref={bottomRef} />
            </div>
            <div style={{ padding: 12, borderTop: '1px solid #f0f0f0' }}>
              <Space.Compact style={{ width: '100%' }}>
                <Input.TextArea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onPressEnter={(e) => { if (!e.shiftKey) { e.preventDefault(); send(); } }}
                  autoSize={{ minRows: 1, maxRows: 5 }}
                  maxLength={4000}
                  placeholder="Type a message… (Shift+Enter for a new line)"
                  disabled={sending}
                />
                <Button type="primary" icon={<SendOutlined />} onClick={() => send()} loading={sending}>Send</Button>
              </Space.Compact>
              {user.role === 'patient' && (
                <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 6 }}>
                  The assistant does not give medical diagnoses. In an emergency call your local emergency number.
                </Text>
              )}
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
}

export default AssistantChat;
