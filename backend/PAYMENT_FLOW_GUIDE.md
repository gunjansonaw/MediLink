# Patient Payment Flow - Quick Reference

## Overview
Patients can pay their medical bills through the MediLink system. The system supports full and partial payments with multiple payment methods.

---

## Payment Flow Steps

### 1. **Admin Creates Invoice**
```
POST /api/billing/invoices/
Headers: Authorization: Bearer {admin_token}

Request Body:
{
  "patient": 7,
  "due_date": "2025-12-16",
  "subtotal": 500.00,
  "tax": 50.00,
  "discount": 10.00,
  "notes": "Medical consultation and tests"
}

Response (201):
{
  "id": 6,
  "invoice_number": "INV-E7A9FEDB",
  "patient": 7,
  "due_date": "2025-12-16",
  "status": "pending",
  "subtotal": "500.00",
  "tax": "50.00",
  "discount": "10.00",
  "total": "540.00",
  "amount_paid": "0.00",
  "amount_due": "540.00"
}
```

### 2. **Patient Logs In**
```
POST /api/users/login/

Request Body:
{
  "username": "patient1",
  "password": "TestPass123!"
}

Response (200):
{
  "access": "eyJhbGciOiJIUzI1NiIs...",
  "user": {
    "id": 7,
    "username": "patient1",
    "email": "patient1@medilink.com",
    "first_name": "John",
    "last_name": "Doe",
    "role": "patient"
  }
}
```

### 3. **Patient Views Invoices**
```
GET /api/billing/invoices/
Headers: Authorization: Bearer {patient_token}

Response (200):
{
  "results": [
    {
      "id": 6,
      "invoice_number": "INV-E7A9FEDB",
      "status": "pending",
      "total": "540.00",
      "amount_paid": "0.00",
      "amount_due": "540.00",
      "due_date": "2025-12-16",
      "invoice_date": "2025-11-16"
    }
  ]
}
```

### 4. **Patient Views Invoice Details**
```
GET /api/billing/invoices/{id}/
Headers: Authorization: Bearer {patient_token}

Response (200):
{
  "id": 6,
  "invoice_number": "INV-E7A9FEDB",
  "invoice_date": "2025-11-16",
  "due_date": "2025-12-16",
  "status": "pending",
  "subtotal": "500.00",
  "tax": "50.00",
  "discount": "10.00",
  "total": "540.00",
  "amount_paid": "0.00",
  "amount_due": "540.00",
  "notes": "Medical consultation and tests",
  "payments": [],
  "items": []
}
```

### 5. **Patient Initiates Payment**
Frontend:
- Displays amount due: $540.00
- Integrates with payment gateway (Stripe, PayPal, Square)
- Patient enters card/payment information
- Payment gateway processes and returns transaction ID

### 6. **Admin Records Payment**
```
POST /api/billing/payments/
Headers: Authorization: Bearer {admin_token}

Request Body:
{
  "invoice": 6,
  "amount": 540.00,
  "payment_method": "online",
  "transaction_id": "TXN-2025-11-16-STRIPE-12345",
  "notes": "Online payment processed via Stripe"
}

Response (201):
{
  "id": 1,
  "invoice": 6,
  "payment_date": "2025-11-16T18:19:26.921754Z",
  "amount": "540.00",
  "payment_method": "online",
  "transaction_id": "TXN-2025-11-16-STRIPE-12345",
  "notes": "Online payment processed via Stripe"
}
```

### 7. **Invoice Auto-Updates**
When payment is recorded:
- `amount_paid` increases
- `amount_due` decreases (= total - amount_paid)
- `status` changes to "paid" when `amount_due` <= 0

### 8. **Patient Checks Payment**
```
GET /api/billing/invoices/{id}/
Headers: Authorization: Bearer {patient_token}

Response (200):
{
  "status": "paid",           <-- Changed from "pending"
  "amount_paid": "540.00",    <-- Updated
  "amount_due": "0.00",       <-- Updated
  "payments": [
    {
      "id": 1,
      "amount": "540.00",
      "payment_method": "online",
      "transaction_id": "TXN-2025-11-16-STRIPE-12345",
      "payment_date": "2025-11-16T18:19:26.921754Z"
    }
  ]
}
```

### 9. **Patient Views Payment History**
```
GET /api/billing/payments/
Headers: Authorization: Bearer {patient_token}

Response (200):
{
  "results": [
    {
      "id": 1,
      "invoice": 6,
      "amount": "540.00",
      "payment_method": "online",
      "transaction_id": "TXN-2025-11-16-STRIPE-12345",
      "payment_date": "2025-11-16T18:19:26.921754Z"
    }
  ]
}
```

---

## Supported Payment Methods

| Method | Code | Description |
|--------|------|-------------|
| Cash | `cash` | Physical payment at clinic |
| Credit Card | `credit_card` | Visa, Mastercard, Amex |
| Debit Card | `debit_card` | Bank debit card |
| Insurance | `insurance` | Insurance claim coverage |
| Bank Transfer | `bank_transfer` | Direct bank deposit |
| Online | `online` | Payment gateway (Stripe, PayPal) |

---

## Special Features

### Partial Payments
- Patients can make multiple partial payments
- Invoice stays "pending" while `amount_due > 0`
- Invoice auto-marks "paid" when fully settled
- Perfect for installment plans

**Example:**
- Invoice total: $1100.00
- First payment: $550.00 (50%) → Status: pending, Amount Due: $550.00
- Second payment: $550.00 (50%) → Status: paid, Amount Due: $0.00

### Permission Rules
```
PATIENT (Role: "patient")
  - View only their own invoices
  - View only their own payment records
  - Cannot create or modify invoices
  - Cannot record payments

DOCTOR (Role: "doctor")
  - View invoices for their appointments
  - Cannot create or modify invoices
  - Cannot record payments

ADMIN (Role: "admin")
  - View all invoices
  - Create invoices
  - Update invoice status
  - Record all payments
  - View all payment history
```

### Invoice Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Unique invoice ID |
| `invoice_number` | String | Auto-generated (INV-XXXXXXXX) |
| `patient` | FK | Reference to patient (User) |
| `due_date` | Date | When payment is due |
| `status` | Choice | pending, paid, overdue, cancelled |
| `subtotal` | Decimal | Amount before tax/discount |
| `tax` | Decimal | Tax amount |
| `discount` | Decimal | Discount amount |
| `total` | Decimal | Final amount due (calculated) |
| `amount_paid` | Decimal | Total paid so far (calculated) |
| `amount_due` | Decimal | Remaining balance (calculated) |
| `notes` | Text | Additional notes |

---

## Testing

Run the complete payment flow test:
```bash
cd d:\medilink\backend
python test_complete_payment_flow.py
```

This test demonstrates:
✓ Admin creates invoice
✓ Patient views invoices
✓ Admin records payment
✓ Invoice auto-updates to paid
✓ Partial payment scenario
✓ Payment history tracking

---

## Frontend Integration

### React Component Flow
```javascript
1. PatientDashboard
   └─ Display invoices (GET /api/billing/invoices/)
   └─ Show Amount Due
   └─ "Pay Bill" button

2. Payment Gateway Integration
   └─ Use Stripe/PayPal SDK
   └─ Process payment on frontend
   └─ Get transaction ID

3. Record Payment
   └─ POST /api/billing/payments/ (Admin only)
   └─ Include transaction ID from gateway

4. Confirm Payment
   └─ GET /api/billing/invoices/{id}/
   └─ Check status = "paid"
   └─ Show receipt/confirmation
```

### Sample React Code
```javascript
// View invoices
const getInvoices = async (token) => {
  const response = await api.get('/billing/invoices/', {
    headers: { Authorization: `Bearer ${token}` }
  });
  return response.data.results;
};

// Check payment status
const getInvoiceDetails = async (invoiceId, token) => {
  const response = await api.get(`/billing/invoices/${invoiceId}/`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  return response.data;
};

// Get payment history
const getPaymentHistory = async (token) => {
  const response = await api.get('/billing/payments/', {
    headers: { Authorization: `Bearer ${token}` }
  });
  return response.data.results;
};
```

---

## Summary

| Step | Actor | Endpoint | Method | Status |
|------|-------|----------|--------|--------|
| 1 | Admin | `/billing/invoices/` | POST | 201 |
| 2 | Patient | `/users/login/` | POST | 200 |
| 3 | Patient | `/billing/invoices/` | GET | 200 |
| 4 | Patient | `/billing/invoices/{id}/` | GET | 200 |
| 5 | Patient | Payment Gateway | External | - |
| 6 | Admin | `/billing/payments/` | POST | 201 |
| 7 | System | Auto-update | - | - |
| 8 | Patient | `/billing/invoices/{id}/` | GET | 200 |
| 9 | Patient | `/billing/payments/` | GET | 200 |

**Result:** Invoice marked as "paid" ✓
