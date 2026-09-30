import React, { useState, useEffect } from 'react';
import {
  List, Card, Descriptions, Table, Tag, Typography, Space, Spin,
  Empty, Row, Col, Button, Modal, message, InputNumber, Radio,
} from 'antd';
import { DollarOutlined, PrinterOutlined } from '@ant-design/icons';
import api from '../../services/api';

const { Title, Text } = Typography;

const statusColor = (status) => {
  switch (status) {
    case 'paid': return 'green';
    case 'partially_paid': return 'blue';
    case 'pending': return 'orange';
    case 'overdue': return 'red';
    default: return 'default';
  }
};

function Billing() {
  const [invoices, setInvoices] = useState([]);
  const [selectedInvoice, setSelectedInvoice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [paying, setPaying] = useState(false);
  
  // Payment Modal State
  const [isPaymentModalVisible, setIsPaymentModalVisible] = useState(false);
  const [paymentType, setPaymentType] = useState('full');
  const [customAmount, setCustomAmount] = useState(0);

  useEffect(() => {
    fetchInvoices();
  }, []);

  const fetchInvoices = async () => {
    try {
      const response = await api.get('/billing/invoices/');
      const data = response.data.results || response.data;
      setInvoices(data);
      if (data.length > 0 && !selectedInvoice) {
        setSelectedInvoice(data[0]);
      }
    } catch (error) {
      message.error('Failed to load invoices');
    } finally {
      setLoading(false);
    }
  };

  const openPaymentModal = (invoice) => {
    const due = parseFloat(invoice.remaining_balance ?? invoice.amount_due ?? invoice.total);
    setPaymentType('full');
    setCustomAmount(due);
    setIsPaymentModalVisible(true);
  };

  const executePayment = async () => {
    if (!selectedInvoice) return;
    const due = parseFloat(selectedInvoice.remaining_balance ?? selectedInvoice.amount_due ?? selectedInvoice.total);
    const amountToPay = paymentType === 'full' ? due : parseFloat(customAmount);

    if (isNaN(amountToPay) || amountToPay <= 0) {
      message.error('Please enter a valid payment amount greater than $0');
      return;
    }

    if (amountToPay > due) {
      message.error(`Payment amount cannot exceed the balance due of $${due.toFixed(2)}`);
      return;
    }

    setPaying(true);
    try {
      await api.post('/billing/payments/', {
        invoice: selectedInvoice.id,
        amount: amountToPay,
        payment_method: 'online',
        transaction_id: `TXN-${Date.now()}`,
      });
      message.success(`Payment of $${amountToPay.toFixed(2)} processed successfully`);
      setIsPaymentModalVisible(false);
      
      // Refresh list & current item
      await fetchInvoices();
      const resp = await api.get(`/billing/invoices/${selectedInvoice.id}/`);
      setSelectedInvoice(resp.data);
    } catch (error) {
      const err = error.response?.data?.detail || 'Payment failed. Please try again.';
      message.error(err);
    } finally {
      setPaying(false);
    }
  };

  const handleDownloadPdf = (invoiceId) => {
    const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';
    window.open(`${apiUrl}/billing/invoices/${invoiceId}/download_pdf/`, '_blank');
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 80 }}>
        <Spin size="large" tip="Loading billing information..." />
      </div>
    );
  }

  const itemColumns = [
    { title: 'Description', dataIndex: 'description', key: 'description' },
    { title: 'Quantity', dataIndex: 'quantity', key: 'quantity' },
    {
      title: 'Unit Price',
      dataIndex: 'unit_price',
      key: 'unit_price',
      render: (v) => `$${parseFloat(v).toFixed(2)}`,
    },
    {
      title: 'Total',
      dataIndex: 'total',
      key: 'total',
      render: (v) => `$${parseFloat(v).toFixed(2)}`,
    },
  ];

  const paymentColumns = [
    {
      title: 'Date',
      dataIndex: 'payment_date',
      key: 'payment_date',
      render: (d) => new Date(d).toLocaleDateString(),
    },
    {
      title: 'Method',
      dataIndex: 'payment_method',
      key: 'payment_method',
      render: (m) => <Tag>{m.replace('_', ' ').toUpperCase()}</Tag>,
    },
    {
      title: 'Transaction ID',
      dataIndex: 'transaction_id',
      key: 'transaction_id',
    },
    {
      title: 'Amount',
      dataIndex: 'amount',
      key: 'amount',
      render: (v) => `$${parseFloat(v).toFixed(2)}`,
    },
  ];

  const amountDue = selectedInvoice ? parseFloat(selectedInvoice.remaining_balance ?? selectedInvoice.amount_due ?? selectedInvoice.total) : 0;

  return (
    <div>
      <Title level={3} style={{ marginBottom: 24 }}>
        <Space><DollarOutlined />Billing & Invoices</Space>
      </Title>

      <Row gutter={[16, 16]}>
        {/* Invoices List */}
        <Col xs={24} lg={selectedInvoice ? 8 : 24}>
          {invoices.length === 0 ? (
            <Card bordered={false} style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
              <Empty description="No invoices found" />
            </Card>
          ) : (
            <List
              dataSource={invoices}
              renderItem={(invoice) => (
                <Card
                  key={invoice.id}
                  bordered={false}
                  className={`stat-card-hover ${selectedInvoice?.id === invoice.id ? 'record-card-active' : ''}`}
                  style={{
                    marginBottom: 12,
                    cursor: 'pointer',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
                    border: selectedInvoice?.id === invoice.id ? '1px solid #1677ff' : '1px solid transparent',
                    transition: 'all 0.2s',
                  }}
                  onClick={() => setSelectedInvoice(invoice)}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <Text strong>Invoice #{invoice.invoice_number}</Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: 12 }}>{invoice.invoice_date}</Text>
                    </div>
                    <Space direction="vertical" align="end" size={4}>
                      <Tag color={statusColor(invoice.status)}>
                        {invoice.status.replace('_', ' ').toUpperCase()}
                      </Tag>
                      <Text strong>${parseFloat(invoice.total).toFixed(2)}</Text>
                    </Space>
                  </div>
                </Card>
              )}
            />
          )}
        </Col>

        {/* Invoice Details */}
        {selectedInvoice && (
          <Col xs={24} lg={16}>
            <Card
              bordered={false}
              title={`Invoice #${selectedInvoice.invoice_number}`}
              extra={
                <Space>
                  {selectedInvoice.status !== 'paid' && (
                    <Button
                      type="primary"
                      loading={paying}
                      onClick={() => openPaymentModal(selectedInvoice)}
                    >
                      Pay Now
                    </Button>
                  )}
                  <Button 
                    icon={<PrinterOutlined />}
                    onClick={() => handleDownloadPdf(selectedInvoice.id)}
                  >
                    Print / PDF
                  </Button>
                </Space>
              }
              style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}
            >
              <Descriptions bordered column={2} size="small" style={{ marginBottom: 20 }}>
                <Descriptions.Item label="Invoice Date">{selectedInvoice.invoice_date}</Descriptions.Item>
                <Descriptions.Item label="Due Date">{selectedInvoice.due_date}</Descriptions.Item>
                <Descriptions.Item label="Status">
                  <Tag color={statusColor(selectedInvoice.status)}>
                    {selectedInvoice.status.replace('_', ' ').toUpperCase()}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="Patient">
                  {selectedInvoice.patient_details?.first_name} {selectedInvoice.patient_details?.last_name}
                </Descriptions.Item>
              </Descriptions>

              {selectedInvoice.items?.length > 0 && (
                <>
                  <Title level={5}>Items</Title>
                  <Table
                    dataSource={selectedInvoice.items}
                    columns={itemColumns}
                    rowKey="id"
                    size="small"
                    pagination={false}
                    style={{ marginBottom: 20 }}
                  />
                </>
              )}

              {/* Summary */}
              <Card
                size="small"
                style={{ background: '#fafafa', marginBottom: selectedInvoice.payments?.length > 0 ? 20 : 0 }}
              >
                {[
                  ['Subtotal', selectedInvoice.subtotal],
                  ['Tax', selectedInvoice.tax],
                  ['Discount', selectedInvoice.discount],
                ].map(([label, val]) => (
                  <div key={label} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
                    <Text type="secondary">{label}:</Text>
                    <Text>${parseFloat(val || 0).toFixed(2)}</Text>
                  </div>
                ))}
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  padding: '8px 0 4px',
                  borderTop: '1px solid #f0f0f0',
                  marginTop: 4,
                }}>
                  <Text strong>Total:</Text>
                  <Text strong>${parseFloat(selectedInvoice.total || 0).toFixed(2)}</Text>
                </div>
                {parseFloat(selectedInvoice.amount_paid || 0) > 0 && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
                    <Text type="secondary">Amount Paid:</Text>
                    <Text style={{ color: '#52c41a', fontWeight: 600 }}>
                      ${parseFloat(selectedInvoice.amount_paid).toFixed(2)}
                    </Text>
                  </div>
                )}
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
                  <Text strong>Balance Due:</Text>
                  <Text strong style={{ color: amountDue > 0 ? '#ff4d4f' : '#52c41a', fontSize: 16 }}>
                    ${amountDue.toFixed(2)}
                  </Text>
                </div>
              </Card>

              {selectedInvoice.payments?.length > 0 && (
                <>
                  <Title level={5} style={{ marginTop: 20 }}>Payment History</Title>
                  <Table
                    dataSource={selectedInvoice.payments}
                    columns={paymentColumns}
                    rowKey="id"
                    size="small"
                    pagination={false}
                  />
                </>
              )}
            </Card>
          </Col>
        )}
      </Row>

      {/* Partial / Full Payment Modal */}
      <Modal
        title={`Process Payment - Invoice #${selectedInvoice?.invoice_number}`}
        open={isPaymentModalVisible}
        onOk={executePayment}
        confirmLoading={paying}
        onCancel={() => setIsPaymentModalVisible(false)}
        okText="Confirm & Pay"
      >
        <div style={{ marginBottom: 16 }}>
          <Text type="secondary">Total Outstanding Balance:</Text>
          <div style={{ fontSize: 24, fontWeight: 'bold', color: '#1677ff' }}>
            ${amountDue.toFixed(2)}
          </div>
        </div>

        <div style={{ marginBottom: 16 }}>
          <Text strong>Select Payment Amount:</Text>
          <div style={{ marginTop: 8 }}>
            <Radio.Group 
              value={paymentType} 
              onChange={(e) => {
                setPaymentType(e.target.value);
                if (e.target.value === 'full') {
                  setCustomAmount(amountDue);
                }
              }}
            >
              <Radio value="full">Pay Full Balance (${amountDue.toFixed(2)})</Radio>
              <Radio value="partial">Pay Partial Amount</Radio>
            </Radio.Group>
          </div>
        </div>

        {paymentType === 'partial' && (
          <div style={{ marginBottom: 16 }}>
            <Text>Enter Partial Amount ($):</Text>
            <div style={{ marginTop: 6 }}>
              <InputNumber
                style={{ width: '100%' }}
                min={1}
                max={amountDue}
                step={10}
                value={customAmount}
                onChange={(val) => setCustomAmount(val)}
                prefix={<DollarOutlined />}
              />
            </div>
            <Text type="secondary" style={{ fontSize: 12 }}>
              Remaining balance after payment: ${(Math.max(0, amountDue - (customAmount || 0))).toFixed(2)}
            </Text>
          </div>
        )}
      </Modal>
    </div>
  );
}

export default Billing;
