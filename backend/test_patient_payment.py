#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Patient Payment Flow Test
This script demonstrates how a patient views and pays their bills
"""
import requests
import json
from datetime import date, timedelta

BASE_URL = 'http://127.0.0.1:8000/api'

# ANSI color codes
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
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

print_header("PATIENT PAYMENT FLOW TEST")

# =====================================================
# STEP 1: Patient Login
# =====================================================
print_step(1, "Patient Login")

login_data = {
    'username': 'patient1',
    'password': 'TestPass123!'
}

response = requests.post(f'{BASE_URL}/users/login/', json=login_data)

if response.status_code != 200:
    print_error(f"Login failed: {response.text}")
    exit(1)

login_response = response.json()
patient_token = login_response['access']
patient_id = login_response['user']['id']

print_success(f"Patient logged in as: {login_response['user']['first_name']} {login_response['user']['last_name']}")
print_success(f"Patient ID: {patient_id}")
print_info(f"Access Token: {patient_token[:20]}...")

headers = {'Authorization': f'Bearer {patient_token}'}

# =====================================================
# STEP 2: View Current User Profile
# =====================================================
print_step(2, "View Current User Profile")

response = requests.get(f'{BASE_URL}/users/me/', headers=headers)

if response.status_code == 200:
    user = response.json()
    print_success(f"User Profile Retrieved:")
    print(f"  Name: {user['first_name']} {user['last_name']}")
    print(f"  Email: {user['email']}")
    print(f"  Role: {user['role']}")
else:
    print_error(f"Failed to get user profile: {response.text}")

# =====================================================
# STEP 3: View All My Invoices (Bills)
# =====================================================
print_step(3, "View All My Invoices (Bills)")

response = requests.get(f'{BASE_URL}/billing/invoices/', headers=headers)

if response.status_code != 200:
    print_error(f"Failed to get invoices: {response.text}")
    exit(1)

response_data = response.json()
# Handle both paginated and non-paginated responses
if isinstance(response_data, dict) and 'results' in response_data:
    invoices = response_data['results']
else:
    invoices = response_data if isinstance(response_data, list) else []

print_success(f"Retrieved {len(invoices)} invoices")

if not invoices:
    print_info("No invoices found for this patient")
else:
    print("\nBill Summary:")
    print("-" * 70)
    for invoice in invoices:
        status_color = GREEN if invoice['status'] == 'paid' else YELLOW
        print(f"Invoice #: {invoice['invoice_number']} | Status: {status_color}{invoice['status']}{END}")
        print(f"  Amount: ${invoice['total']:.2f} | Due Date: {invoice['due_date']}")
        print(f"  Subtotal: ${invoice['subtotal']:.2f} | Tax: ${invoice['tax']:.2f} | Discount: ${invoice['discount']:.2f}")
        print()

# =====================================================
# STEP 4: Select an Invoice and View Details
# =====================================================
print_step(4, "Select an Invoice and View Details")

if not invoices:
    print_info("No invoices available to pay")
    pending_invoices = []
else:
    # Find pending invoices
    pending_invoices = [inv for inv in invoices if inv['status'] == 'pending']
    
    if pending_invoices:
        selected_invoice = pending_invoices[0]
        invoice_id = selected_invoice['id']
        print_success(f"Selected Invoice: {selected_invoice['invoice_number']}")
        
        # Get detailed view
        response = requests.get(f'{BASE_URL}/billing/invoices/{invoice_id}/', headers=headers)
        
        if response.status_code == 200:
            invoice_detail = response.json()
            print_info(f"Invoice Number: {invoice_detail['invoice_number']}")
            print_info(f"Invoice Date: {invoice_detail['invoice_date']}")
            print_info(f"Due Date: {invoice_detail['due_date']}")
            print_info(f"Status: {invoice_detail['status']}")
            print_info(f"\nAmount Breakdown:")
            print_info(f"  Subtotal: ${invoice_detail['subtotal']:.2f}")
            print_info(f"  Tax: ${invoice_detail['tax']:.2f}")
            print_info(f"  Discount: ${invoice_detail['discount']:.2f}")
            print_info(f"  TOTAL DUE: ${invoice_detail['total']:.2f}")
            
            if invoice_detail.get('notes'):
                print_info(f"Notes: {invoice_detail['notes']}")
        else:
            print_error(f"Failed to get invoice details: {response.text}")
    else:
        print_info("No pending invoices to pay")

# =====================================================
# STEP 5: View Payment History
# =====================================================
print_step(5, "View Payment History")

response = requests.get(f'{BASE_URL}/billing/payments/', headers=headers)

if response.status_code == 200:
    response_data = response.json()
    # Handle both paginated and non-paginated responses
    if isinstance(response_data, dict) and 'results' in response_data:
        payments = response_data['results']
    else:
        payments = response_data if isinstance(response_data, list) else []
    
    print_success(f"Retrieved {len(payments)} payment records")
    
    if payments:
        print("\nPayment History:")
        print("-" * 70)
        for payment in payments:
            print(f"Payment Amount: ${payment['amount']:.2f} | Method: {payment['payment_method']}")
            print(f"  Date: {payment['payment_date']} | Transaction ID: {payment['transaction_id']}")
            print()
    else:
        print_info("No payment history yet")
else:
    print_error(f"Failed to get payments: {response.text}")

# =====================================================
# STEP 6: Make a Payment
# =====================================================
print_step(6, "Make a Payment on Pending Invoice")

if pending_invoices:
    selected_invoice = pending_invoices[0]
    invoice_id = selected_invoice['id']
    invoice_total = selected_invoice['total']
    
    print_info(f"Processing payment for Invoice: {selected_invoice['invoice_number']}")
    print_info(f"Amount to Pay: ${invoice_total:.2f}")
    
    # Admin needs to create the payment (in real system, this could be automated)
    # For now, let's show what the payment data would be
    
    payment_data = {
        'invoice': invoice_id,
        'amount': invoice_total,
        'payment_method': 'online',
        'transaction_id': f'TXN-{date.today().isoformat()}-ONLINE-PAYMENT',
        'notes': 'Online payment for medical services'
    }
    
    print_info(f"\nPayment Details to be submitted:")
    print(json.dumps(payment_data, indent=2))
    
    # Note: In the current system, only admins can create payments
    # A patient would initiate the payment, and admin would confirm it
    
    print_info("\n[Note: In production, patient initiates payment -> gateway processes -> admin confirms in system]")
    
else:
    print_info("No pending invoices to pay")

# =====================================================
# STEP 7: Check Invoice Status After Payment
# =====================================================
print_step(7, "Check Invoice Status After Payment")

if pending_invoices:
    # Get updated invoice list
    response = requests.get(f'{BASE_URL}/billing/invoices/', headers=headers)
    
    if response.status_code == 200:
        response_data = response.json()
        # Handle both paginated and non-paginated responses
        if isinstance(response_data, dict) and 'results' in response_data:
            updated_invoices = response_data['results']
        else:
            updated_invoices = response_data if isinstance(response_data, list) else []
        
        print_success("Updated invoice list retrieved")
        
        print("\nUpdated Bill Status:")
        print("-" * 70)
        for invoice in updated_invoices:
            status_color = GREEN if invoice['status'] == 'paid' else YELLOW
            print(f"Invoice #: {invoice['invoice_number']} | Status: {status_color}{invoice['status']}{END}")
            print(f"  Amount: ${invoice['total']:.2f}")
            print()

# =====================================================
# SUMMARY
# =====================================================
print_header("PAYMENT FLOW SUMMARY")

print(f"{BLUE}How a Patient Pays a Bill:{END}\n")

print(f"{YELLOW}1. PATIENT LOGIN{END}")
print(f"   - Patient logs in with username/password")
print(f"   - Receives JWT access token\n")

print(f"{YELLOW}2. VIEW INVOICES{END}")
print(f"   - GET /api/billing/invoices/")
print(f"   - Patients see only their own invoices")
print(f"   - Can filter by status (pending, paid, overdue)\n")

print(f"{YELLOW}3. SELECT INVOICE{END}")
print(f"   - GET /api/billing/invoices/{{id}}/")
print(f"   - View detailed breakdown of charges\n")

print(f"{YELLOW}4. PAYMENT METHODS SUPPORTED{END}")
print(f"   - Cash")
print(f"   - Credit Card")
print(f"   - Debit Card")
print(f"   - Insurance (for claims)")
print(f"   - Bank Transfer")
print(f"   - Online Payment\n")

print(f"{YELLOW}5. MAKE PAYMENT{END}")
print(f"   - Frontend integrates payment gateway (Stripe, PayPal, etc.)")
print(f"   - Patient completes payment in gateway")
print(f"   - Admin records payment: POST /api/billing/payments/")
print(f"   - Invoice status auto-updates to 'paid' when fully paid\n")

print(f"{YELLOW}6. PAYMENT CONFIRMATION{END}")
print(f"   - Payment record created with transaction ID")
print(f"   - Patient receives receipt/confirmation")
print(f"   - Invoice marked as 'paid' in system\n")

print(f"{BLUE}Database Relationships:{END}\n")
print(f"   Invoice → Patient (ForeignKey)")
print(f"   Invoice → Appointment (ForeignKey, optional)")
print(f"   Payment → Invoice (ForeignKey)")
print(f"   Each invoice can have multiple payments (partial payments supported)\n")

print(f"{BLUE}Permission Rules:{END}\n")
print(f"   - Patients: View only their own invoices/payments")
print(f"   - Doctors: View invoices for their appointments")
print(f"   - Admin: View/Create/Update all invoices and payments\n")

print(f"{GREEN}✓ Test Complete!{END}\n")
