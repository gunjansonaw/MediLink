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

  useEffect(() => {
    fetchInvoices();
  }, []);

  const fetchInvoices = async () => {
    try {
      const response = await api.get('/billing/invoices/');
      setInvoices(response.data.results || response.data);
    } catch (error) {
      console.error('Error fetching invoices:', error);
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

  if (loading) {
    return <div className="loading">Loading billing information...</div>;
  }

  return (
    <div className="billing-page">
      <div className="page-header">
        <h1>Billing & Invoices</h1>
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
              <button className="btn btn-primary">
                <Download size={16} />
                Download PDF
              </button>
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
