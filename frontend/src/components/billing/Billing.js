import React, { useState, useEffect } from 'react';
import { DollarSign, Download } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import api from '../../services/api';
import './Billing.css';

function Billing() {
  const { user } = useAuth();
  const [invoices, setInvoices] = useState([]);
  const [selectedInvoice, setSelectedInvoice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [forceShowPay, setForceShowPay] = useState(false);

  useEffect(() => {
    fetchInvoices();
  }, []);

  const fetchInvoices = async () => {
    try {
      console.log('Fetching invoices from API...');
      const response = await api.get('/billing/invoices/');
      console.log('Invoices response:', response.data);
      const invoiceData = response.data.results || response.data;
      console.log('Setting invoices:', invoiceData);
      setInvoices(invoiceData);
    } catch (error) {
      console.error('Error fetching invoices:', error);
      console.error('Error response:', error.response?.data);
      alert('Failed to load invoices. Check console for details.');
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'paid':
        return 'success';
      case 'pending':
        return 'warning';
      case 'overdue':
        return 'danger';
      default:
        return 'info';
    }
  };

  const handlePay = async (invoice) => {
    try {
      const amountDue = parseFloat(invoice.amount_due ?? invoice.total);
      if (!window.confirm(`Pay $${amountDue.toFixed(2)} for invoice ${invoice.invoice_number}?`)) return;

      const payload = {
        invoice: invoice.id,
        amount: amountDue,
        payment_method: 'online',
        transaction_id: `WEB-${Date.now()}`,
      };

      await api.post('/billing/payments/', payload);
      // Refresh invoices and selected invoice
      const resp = await api.get(`/billing/invoices/${invoice.id}/`);
      // update invoice list
      fetchInvoices();
      setSelectedInvoice(resp.data);
      alert('Payment recorded successfully');
    } catch (error) {
      console.error('Payment error:', error);
      alert('Payment failed. See console for details.');
    }
  };

  if (loading) {
    return <div className="loading">Loading billing information...</div>;
  }

  return (
    <div className="billing-page">
      <div className="page-header">
        <h1>Billing & Invoices</h1>
        <div className="debug-controls">
          <label style={{fontSize:12, marginLeft:10}}>
            <input type="checkbox" checked={forceShowPay} onChange={(e) => setForceShowPay(e.target.checked)} />
            {' '}Force show Pay (debug)
          </label>
        </div>
      </div>

      <div style={{ backgroundColor: '#f0f0f0', padding: '10px', margin: '10px', fontSize: '12px', border: '1px solid #ccc' }}>
        <strong>DEBUG INFO:</strong>
        <div>User: {user ? `${user.first_name} ${user.last_name} (role: ${user.role})` : 'NOT LOGGED IN'}</div>
        {selectedInvoice && (
          <div>
            Selected Invoice: #{selectedInvoice.invoice_number} | Status: <strong>{selectedInvoice.status}</strong> | Amount Due: ${selectedInvoice.amount_due ?? selectedInvoice.total}
          </div>
        )}
        <div>Pay Button Should Show: {selectedInvoice && selectedInvoice.status !== 'paid' ? '✓ YES' : '✗ NO'}</div>
      </div>

      <div className="billing-container">
        <div className="invoices-list">
          {invoices.length === 0 ? (
            <div className="card">
              <p className="no-data">No invoices found</p>
            </div>
          ) : (
            invoices.map((invoice) => (
              <div
                key={invoice.id}
                className={`invoice-card ${selectedInvoice?.id === invoice.id ? 'active' : ''}`}
                onClick={() => setSelectedInvoice(invoice)}
              >
                <div className="invoice-header">
                  <div>
                    <h3>Invoice #{invoice.invoice_number}</h3>
                    <p className="invoice-date">{invoice.invoice_date}</p>
                  </div>
                  <span className={`badge badge-${getStatusColor(invoice.status)}`}>
                    {invoice.status}
                  </span>
                </div>
                <div className="invoice-amount">
                  <span>Total:</span>
                  <strong>${parseFloat(invoice.total).toFixed(2)}</strong>
                </div>
              </div>
            ))
          )}
        </div>

        {selectedInvoice && (
          <div className="invoice-details card">
            <div className="invoice-details-header">
              <h2>Invoice #{selectedInvoice.invoice_number}</h2>
              <div className="invoice-actions">
                {(forceShowPay || selectedInvoice.status !== 'paid') && (
                  <button className="btn btn-success" onClick={() => handlePay(selectedInvoice)}>
                    Pay Now
                  </button>
                )}
                <button className="btn btn-primary">
                  <Download size={16} />
                  Download PDF
                </button>
              </div>
            </div>

            <div className="invoice-info-grid">
              <div>
                <p className="label">Invoice Date</p>
                <p className="value">{selectedInvoice.invoice_date}</p>
              </div>
              <div>
                <p className="label">Due Date</p>
                <p className="value">{selectedInvoice.due_date}</p>
              </div>
              <div>
                <p className="label">Status</p>
                <span className={`badge badge-${getStatusColor(selectedInvoice.status)}`}>
                  {selectedInvoice.status}
                </span>
              </div>
              <div>
                <p className="label">Patient</p>
                <p className="value">
                  {selectedInvoice.patient_details?.first_name} {selectedInvoice.patient_details?.last_name}
                </p>
              </div>
            </div>

            {selectedInvoice.items && selectedInvoice.items.length > 0 && (
              <div className="invoice-items">
                <h3>Items</h3>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Description</th>
                      <th>Quantity</th>
                      <th>Unit Price</th>
                      <th>Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedInvoice.items.map((item) => (
                      <tr key={item.id}>
                        <td>{item.description}</td>
                        <td>{item.quantity}</td>
                        <td>${parseFloat(item.unit_price).toFixed(2)}</td>
                        <td>${parseFloat(item.total).toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <div className="invoice-summary">
              <div className="summary-row">
                <span>Subtotal:</span>
                <span>${parseFloat(selectedInvoice.subtotal).toFixed(2)}</span>
              </div>
              <div className="summary-row">
                <span>Tax:</span>
                <span>${parseFloat(selectedInvoice.tax).toFixed(2)}</span>
              </div>
              <div className="summary-row">
                <span>Discount:</span>
                <span>-${parseFloat(selectedInvoice.discount).toFixed(2)}</span>
              </div>
              <div className="summary-row total">
                <span>Total:</span>
                <span>${parseFloat(selectedInvoice.total).toFixed(2)}</span>
              </div>
              {selectedInvoice.amount_paid > 0 && (
                <>
                  <div className="summary-row">
                    <span>Amount Paid:</span>
                    <span>${parseFloat(selectedInvoice.amount_paid).toFixed(2)}</span>
                  </div>
                  <div className="summary-row total">
                    <span>Amount Due:</span>
                    <span>${parseFloat(selectedInvoice.amount_due).toFixed(2)}</span>
                  </div>
                </>
              )}
            </div>

            {selectedInvoice.payments && selectedInvoice.payments.length > 0 && (
              <div className="payment-history">
                <h3>Payment History</h3>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Amount</th>
                      <th>Method</th>
                      <th>Transaction ID</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedInvoice.payments.map((payment) => (
                      <tr key={payment.id}>
                        <td>{new Date(payment.payment_date).toLocaleDateString()}</td>
                        <td>${parseFloat(payment.amount).toFixed(2)}</td>
                        <td>{payment.payment_method}</td>
                        <td>{payment.transaction_id || 'N/A'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default Billing;
