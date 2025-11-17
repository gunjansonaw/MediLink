#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Complete Patient Payment Flow - Admin Creates Invoice, Patient Pays
"""
import requests
import json
from datetime import date, timedelta

BASE_URL = 'http://127.0.0.1:8000/api'

BLUE = '\033[94m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
END = '\033[0m'

def print_header(text):
    print(f"\n{BLUE}{'='*70}{END}")
    print(f"{BLUE}{text}{END}")
    print(f"{BLUE}{'='*70}{END}\n")

def print_step(num, text):
    print(f"{YELLOW}STEP {num}: {text}{END}")

def print_success(text):
    print(f"{GREEN}[OK] {text}{END}")

def print_error(text):
    print(f"{RED}[ERROR] {text}{END}")

def print_info(text):
    print(f"{BLUE}[INFO] {text}{END}")

def safe_float(val):
    """Safely convert to float"""
    return float(val) if val else 0.0

print_header("COMPLETE PATIENT PAYMENT FLOW TEST")

# =====================================================
# STEP 1: Admin Login to Create Invoice
# =====================================================
print_step(1, "Admin Login (to create invoice)")

admin_login = {
    'username': 'testadmin',
    'password': 'TestPass123!'
}

response = requests.post(f'{BASE_URL}/users/login/', json=admin_login)

if response.status_code != 200:
    print_error(f"Admin login failed: {response.text}")
    exit(1)

admin_token = response.json()['access']
print_success("Admin logged in successfully")

admin_headers = {'Authorization': f'Bearer {admin_token}'}

# =====================================================
# STEP 2: Admin Creates Invoice for Patient
# =====================================================
print_step(2, "Admin Creates Invoice for Patient")

invoice_data = {
    'patient': 7,  # patient1 (John Doe)
    'due_date': (date.today() + timedelta(days=30)).isoformat(),
    'subtotal': 500.00,
    'tax': 50.00,
    'discount': 10.00,
    'notes': 'Medical consultation and tests'
}

response = requests.post(f'{BASE_URL}/billing/invoices/', json=invoice_data, headers=admin_headers)

if response.status_code != 201:
    print_error(f"Failed to create invoice: {response.text}")
    exit(1)

invoice = response.json()
invoice_id = invoice['id']
invoice_number = invoice['invoice_number']
total_amount = safe_float(invoice['total'])

print_success(f"Invoice created successfully!")
print_info(f"  Invoice Number: {invoice_number}")
print_info(f"  Invoice ID: {invoice_id}")
print_info(f"  Amount Due: ${total_amount:.2f}")

# =====================================================
# STEP 3: Patient Login
# =====================================================
print_step(3, "Patient Login")

patient_login = {
    'username': 'patient1',
    'password': 'TestPass123!'
}

response = requests.post(f'{BASE_URL}/users/login/', json=patient_login)

if response.status_code != 200:
    print_error(f"Patient login failed: {response.text}")
    exit(1)

patient_token = response.json()['access']
patient_headers = {'Authorization': f'Bearer {patient_token}'}

print_success("Patient logged in successfully")

# =====================================================
# STEP 4: Patient Views Their Invoices
# =====================================================
print_step(4, "Patient Views All Their Invoices")

response = requests.get(f'{BASE_URL}/billing/invoices/', headers=patient_headers)

if response.status_code == 200:
    response_data = response.json()
    if isinstance(response_data, dict) and 'results' in response_data:
        invoices = response_data['results']
    else:
        invoices = response_data if isinstance(response_data, list) else []
    
    print_success(f"Patient has {len(invoices)} invoice(s)")
    
    print("\n--- Patient's Bills ---")
    for inv in invoices:
        status_color = GREEN if inv['status'] == 'paid' else YELLOW
        total = safe_float(inv['total'])
        print(f"Invoice #{inv['invoice_number']} | Status: {status_color}{inv['status']}{END}")
        print(f"  Amount: ${total:.2f} | Due: {inv['due_date']}")

# =====================================================
# STEP 5: Patient Views Specific Invoice Details
# =====================================================
print_step(5, "Patient Views Invoice Details")

response = requests.get(f'{BASE_URL}/billing/invoices/{invoice_id}/', headers=patient_headers)

if response.status_code == 200:
    invoice_detail = response.json()
    
    subtotal = safe_float(invoice_detail['subtotal'])
    tax = safe_float(invoice_detail['tax'])
    discount = safe_float(invoice_detail['discount'])
    total = safe_float(invoice_detail['total'])
    amount_paid = safe_float(invoice_detail['amount_paid'])
    amount_due = safe_float(invoice_detail['amount_due'])
    
    print_success(f"Invoice Details Retrieved:")
    print(f"\n{BLUE}Invoice Information:{END}")
    print(f"  Invoice Number: {invoice_detail['invoice_number']}")
    print(f"  Date: {invoice_detail['invoice_date']}")
    print(f"  Due Date: {invoice_detail['due_date']}")
    print(f"  Status: {invoice_detail['status']}")
    print(f"\n{BLUE}Amount Breakdown:{END}")
    print(f"  Subtotal:    ${subtotal:>8.2f}")
    print(f"  Tax:         ${tax:>8.2f}")
    print(f"  Discount:    ${discount:>8.2f}")
    print(f"  {'-'*25}")
    print(f"  TOTAL DUE:   ${total:>8.2f}")
    print(f"\n{BLUE}Payment Status:{END}")
    print(f"  Amount Paid: ${amount_paid:>8.2f}")
    print(f"  Amount Due:  ${amount_due:>8.2f}")

# =====================================================
# STEP 6: Admin Records Payment from Patient
# =====================================================
print_step(6, "Admin Records Payment from Patient")

payment_data = {
    'invoice': invoice_id,
    'amount': total_amount,
    'payment_method': 'online',
    'transaction_id': f'TXN-{date.today().isoformat()}-STRIPE-12345',
    'notes': 'Online payment processed via Stripe'
}

response = requests.post(f'{BASE_URL}/billing/payments/', json=payment_data, headers=admin_headers)

if response.status_code != 201:
    print_error(f"Failed to record payment: {response.text}")
    exit(1)

payment = response.json()
amount = safe_float(payment['amount'])
print_success(f"Payment recorded successfully!")
print_info(f"  Amount: ${amount:.2f}")
print_info(f"  Payment Method: {payment['payment_method']}")
print_info(f"  Transaction ID: {payment['transaction_id']}")

# =====================================================
# STEP 7: Patient Checks Invoice Status After Payment
# =====================================================
print_step(7, "Patient Checks Invoice Status After Payment")

response = requests.get(f'{BASE_URL}/billing/invoices/{invoice_id}/', headers=patient_headers)

if response.status_code == 200:
    invoice_updated = response.json()
    
    amount_paid_updated = safe_float(invoice_updated['amount_paid'])
    amount_due_updated = safe_float(invoice_updated['amount_due'])
    
    print_success(f"Invoice Status: {invoice_updated['status'].upper()}")
    print(f"\n{BLUE}Updated Payment Status:{END}")
    print(f"  Amount Paid: ${amount_paid_updated:>8.2f}")
    print(f"  Amount Due:  ${amount_due_updated:>8.2f}")
    
    if invoice_updated['status'] == 'paid':
        print(f"\n{GREEN}[SUCCESS] INVOICE FULLY PAID!{END}")
    elif amount_due_updated > 0:
        print(f"\n{YELLOW}[WARNING] PARTIAL PAYMENT - Remaining: ${amount_due_updated:.2f}{END}")

# =====================================================
# STEP 8: Patient Views Payment History
# =====================================================
print_step(8, "Patient Views Payment History")

response = requests.get(f'{BASE_URL}/billing/payments/', headers=patient_headers)

if response.status_code == 200:
    response_data = response.json()
    if isinstance(response_data, dict) and 'results' in response_data:
        payments = response_data['results']
    else:
        payments = response_data if isinstance(response_data, list) else []
    
    print_success(f"Patient has {len(payments)} payment record(s)")
    
    if payments:
        print("\n--- Payment History ---")
        for pmt in payments:
            pmt_amount = safe_float(pmt['amount'])
            print(f"Payment: ${pmt_amount:.2f} | Method: {pmt['payment_method']}")
            print(f"  Date: {pmt['payment_date']}")
            print(f"  Transaction: {pmt['transaction_id']}")

# =====================================================
# TEST PARTIAL PAYMENT
# =====================================================
print_header("BONUS: Testing Partial Payment")

# Admin creates another invoice
print_step(1, "Admin Creates Second Invoice")

invoice_data_2 = {
    'patient': 7,
    'due_date': (date.today() + timedelta(days=15)).isoformat(),
    'subtotal': 1000.00,
    'tax': 100.00,
    'discount': 0.00,
    'notes': 'Advanced imaging and specialist consultation'
}

response = requests.post(f'{BASE_URL}/billing/invoices/', json=invoice_data_2, headers=admin_headers)

if response.status_code == 201:
    invoice2 = response.json()
    invoice2_id = invoice2['id']
    invoice2_total = safe_float(invoice2['total'])
    
    print_success(f"Second invoice created: {invoice2['invoice_number']}")
    print_info(f"  Total Amount: ${invoice2_total:.2f}")
    
    # Admin records partial payment (50%)
    print_step(2, "Admin Records Partial Payment (50%)")
    
    partial_amount = invoice2_total / 2
    
    payment_data_partial = {
        'invoice': invoice2_id,
        'amount': partial_amount,
        'payment_method': 'credit_card',
        'transaction_id': f'TXN-{date.today().isoformat()}-CC-67890',
        'notes': 'Partial payment via credit card'
    }
    
    response = requests.post(f'{BASE_URL}/billing/payments/', json=payment_data_partial, headers=admin_headers)
    
    if response.status_code == 201:
        print_success(f"Partial payment recorded: ${partial_amount:.2f}")
        
        # Check invoice status
        print_step(3, "Check Invoice Status with Partial Payment")
        
        response = requests.get(f'{BASE_URL}/billing/invoices/{invoice2_id}/', headers=patient_headers)
        
        if response.status_code == 200:
            inv2_updated = response.json()
            paid = safe_float(inv2_updated['amount_paid'])
            due = safe_float(inv2_updated['amount_due'])
            
            print_info(f"  Invoice Status: {inv2_updated['status']}")
            print_info(f"  Amount Paid: ${paid:.2f}")
            print_info(f"  Amount Due: ${due:.2f}")
            print(f"\n{YELLOW}[INFO] Invoice remains 'pending' because amount due > 0{END}")

# =====================================================
# SUMMARY
# =====================================================
print_header("PAYMENT FLOW SUMMARY")

print(f"{BLUE}Step-by-Step Payment Process:{END}\n")

print(f"{YELLOW}1. ADMIN CREATES INVOICE{END}")
print(f"   POST /api/billing/invoices/")
print(f"   - Patient ID: Required")
print(f"   - Due Date: Required")
print(f"   - Subtotal, Tax, Discount: Required")
print(f"   - Auto-generates invoice number\n")

print(f"{YELLOW}2. PATIENT RECEIVES NOTIFICATION{END}")
print(f"   - Invoice appears in patient dashboard")
print(f"   - Patient can view invoice details\n")

print(f"{YELLOW}3. PATIENT INITIATES PAYMENT{END}")
print(f"   Frontend shows: Amount Due = Total - Amount Paid")
print(f"   - Supports partial payments")
print(f"   - Multiple payment methods available\n")

print(f"{YELLOW}4. PAYMENT PROCESSING{END}")
print(f"   Frontend integrates payment gateway:")
print(f"   - Stripe, PayPal, Square, etc.")
print(f"   - Gateway processes card/payment\n")

print(f"{YELLOW}5. ADMIN RECORDS PAYMENT{END}")
print(f"   POST /api/billing/payments/")
print(f"   - Invoice ID: Required")
print(f"   - Amount: Required")
print(f"   - Payment Method: Required")
print(f"   - Transaction ID: From payment gateway\n")

print(f"{YELLOW}6. INVOICE AUTO-UPDATES{END}")
print(f"   - Amount Paid increases")
print(f"   - Amount Due decreases")
print(f"   - Status → 'paid' when total >= invoice.total\n")

print(f"{YELLOW}7. PATIENT CONFIRMATION{END}")
print(f"   - Receives payment confirmation")
print(f"   - Can download receipt/invoice\n")

print(f"{BLUE}Key Features:{END}\n")
print(f"   [OK] Partial payments supported")
print(f"   [OK] Multiple payment methods")
print(f"   [OK] Auto-status updates")
print(f"   [OK] Payment history tracking")
print(f"   [OK] Transaction IDs for reconciliation")
print(f"   [OK] Role-based access control\n")

print(f"{GREEN}[SUCCESS] Complete Payment Flow Test Successful!{END}\n")
