#!/usr/bin/env python
"""
Comprehensive API endpoint testing for MediLink
Tests all major endpoints across users, appointments, billing, and medical records
"""
import os
import sys
import django
import json
from datetime import date, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medilink.settings')
django.setup()

from django.test.client import Client
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from appointments.models import Appointment
from billing.models import Invoice, InvoiceItem, Payment
from medical_records.models import MedicalRecord

User = get_user_model()
client = Client()

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
END = '\033[0m'

def print_header(text):
    print(f"\n{BLUE}{'='*60}{END}")
    print(f"{BLUE}{text}{END}")
    print(f"{BLUE}{'='*60}{END}\n")

def print_success(text):
    print(f"{GREEN}✓ {text}{END}")

def print_error(text):
    print(f"{RED}✗ {text}{END}")

def print_info(text):
    print(f"{YELLOW}ℹ {text}{END}")

def test_endpoint(method, endpoint, data=None, token=None, expected_status=200):
    """Test an API endpoint"""
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['HTTP_AUTHORIZATION'] = f'Bearer {token}'
    
    if method == 'GET':
        response = client.get(endpoint, **headers)
    elif method == 'POST':
        response = client.post(endpoint, data=json.dumps(data) if data else None, 
                             content_type='application/json', **headers)
    elif method == 'PATCH':
        response = client.patch(endpoint, data=json.dumps(data) if data else None,
                              content_type='application/json', **headers)
    elif method == 'PUT':
        response = client.put(endpoint, data=json.dumps(data) if data else None,
                            content_type='application/json', **headers)
    
    success = response.status_code == expected_status
    status_str = f"{response.status_code}"
    
    if success:
        print_success(f"{method} {endpoint} → {status_str}")
    else:
        print_error(f"{method} {endpoint} → {status_str} (expected {expected_status})")
        try:
            print_info(f"Response: {json.loads(response.content.decode())}")
        except:
            pass
    
    try:
        return json.loads(response.content.decode()) if response.content else None
    except:
        return None

# ===== SETUP TEST DATA =====
print_header("SETUP: Creating Test Users")

# Create users
patient_user = User.objects.filter(username='testpatient').first()
if not patient_user:
    patient_user = User.objects.create_user(
        username='testpatient',
        email='testpatient@medilink.com',
        password='TestPass123!',
        role='patient',
        first_name='John',
        last_name='Doe'
    )
    print_success(f"Created patient: {patient_user.username}")
else:
    print_info(f"Using existing patient: {patient_user.username}")

doctor_user = User.objects.filter(username='testdoctor').first()
if not doctor_user:
    doctor_user = User.objects.create_user(
        username='testdoctor',
        email='testdoctor@medilink.com',
        password='TestPass123!',
        role='doctor',
        first_name='Dr.',
        last_name='Smith'
    )
    print_success(f"Created doctor: {doctor_user.username}")
else:
    print_info(f"Using existing doctor: {doctor_user.username}")

admin_user = User.objects.filter(username='testadmin').first()
if not admin_user:
    admin_user = User.objects.create_user(
        username='testadmin',
        email='testadmin@medilink.com',
        password='TestPass123!',
        role='admin',
        first_name='Admin',
        last_name='User'
    )
    print_success(f"Created admin: {admin_user.username}")
else:
    print_info(f"Using existing admin: {admin_user.username}")

# Get JWT tokens
patient_token = str(RefreshToken.for_user(patient_user).access_token)
doctor_token = str(RefreshToken.for_user(doctor_user).access_token)
admin_token = str(RefreshToken.for_user(admin_user).access_token)

print_info(f"Patient token: {patient_token[:30]}...")
print_info(f"Doctor token: {doctor_token[:30]}...")
print_info(f"Admin token: {admin_token[:30]}...")

# ===== TEST USERS ENDPOINTS =====
print_header("TEST: Users Endpoints")

test_endpoint('GET', '/api/users/', token=admin_token)
test_endpoint('GET', f'/api/users/{patient_user.id}/', token=patient_token)
test_endpoint('GET', '/api/users/me/', token=patient_token)
test_endpoint('GET', '/api/users/doctors/', token=patient_token)
test_endpoint('POST', '/api/users/login/', {
    'username': 'testpatient',
    'password': 'TestPass123!'
}, expected_status=200)

# ===== TEST APPOINTMENTS ENDPOINTS =====
print_header("TEST: Appointments Endpoints")

appointment_data = {
    'doctor': doctor_user.id,
    'appointment_date': (date.today() + timedelta(days=5)).isoformat(),
    'appointment_time': '14:00:00',
    'duration_minutes': 30,
    'reason': 'General Checkup',
    'notes': 'Test appointment'
}

response = test_endpoint('POST', '/api/appointments/appointments/', 
                        data=appointment_data, token=patient_token, expected_status=201)
appointment_id = response.get('id') if response else None

if appointment_id:
    print_info(f"Created appointment ID: {appointment_id}")
    test_endpoint('GET', '/api/appointments/appointments/', token=patient_token)
    test_endpoint('GET', f'/api/appointments/appointments/{appointment_id}/', token=patient_token)
    test_endpoint('GET', '/api/appointments/appointments/upcoming/', token=patient_token)
    test_endpoint('POST', f'/api/appointments/appointments/{appointment_id}/confirm/', 
                 token=doctor_token, expected_status=200)
    test_endpoint('GET', '/api/appointments/appointments/statistics/', token=doctor_token)

# ===== TEST BILLING ENDPOINTS =====
print_header("TEST: Billing Endpoints")

# Create invoice
invoice_data = {
    'patient': patient_user.id,
    'appointment': appointment_id,
    'due_date': (date.today() + timedelta(days=30)).isoformat(),
    'subtotal': 150.00,
    'tax': 15.00,
    'discount': 0.00,
    'notes': 'Test invoice'
}

response = test_endpoint('POST', '/api/billing/invoices/', 
                        data=invoice_data, token=admin_token, expected_status=201)
invoice_id = response.get('id') if response else None

if invoice_id:
    print_info(f"Created invoice ID: {invoice_id}")
    test_endpoint('GET', '/api/billing/invoices/', token=patient_token)
    test_endpoint('GET', f'/api/billing/invoices/{invoice_id}/', token=patient_token)
    
    # Create invoice item
    item_data = {
        'invoice': invoice_id,
        'description': 'Consultation Fee',
        'quantity': 1,
        'unit_price': 150.00
    }
    test_endpoint('POST', '/api/billing/invoices-items/', 
                 data=item_data, token=admin_token, expected_status=201)
    
    # Record payment
    payment_data = {
        'invoice': invoice_id,
        'amount': 165.00,
        'payment_method': 'credit_card',
        'transaction_id': 'TXN-TEST-001'
    }
    response = test_endpoint('POST', '/api/billing/payments/', 
                           data=payment_data, token=admin_token, expected_status=201)
    
    # Mark as paid
    test_endpoint('POST', f'/api/billing/invoices/{invoice_id}/mark_paid/', 
                 token=admin_token, expected_status=200)
    
    # Get statistics
    test_endpoint('GET', '/api/billing/invoices/statistics/', token=admin_token)

# ===== TEST MEDICAL RECORDS ENDPOINTS =====
print_header("TEST: Medical Records Endpoints")

record_data = {
    'patient': patient_user.id,
    'doctor': doctor_user.id,
    'appointment': appointment_id,
    'diagnosis': 'Common Cold',
    'treatment': 'Rest, fluids, over-the-counter medication',
    'medicines': 'Aspirin 500mg',
    'follow_up_date': (date.today() + timedelta(days=7)).isoformat(),
    'notes': 'Patient advised to get adequate rest'
}

response = test_endpoint('POST', '/api/medical-records/records/', 
                        data=record_data, token=doctor_token, expected_status=201)
record_id = response.get('id') if response else None

if record_id:
    print_info(f"Created medical record ID: {record_id}")
    test_endpoint('GET', '/api/medical-records/records/', token=patient_token)
    test_endpoint('GET', f'/api/medical-records/records/{record_id}/', token=patient_token)
    test_endpoint('GET', '/api/medical-records/records/my_records/', token=patient_token)

# ===== SUMMARY =====
print_header("TEST SUMMARY")
print_success("All endpoint tests completed!")
print_info("Check results above for any failures")
print(f"\nTest Data Created:")
print(f"  • Patient: {patient_user.username} (ID: {patient_user.id})")
print(f"  • Doctor: {doctor_user.username} (ID: {doctor_user.id})")
print(f"  • Admin: {admin_user.username} (ID: {admin_user.id})")
print(f"  • Appointment: ID {appointment_id}")
print(f"  • Invoice: ID {invoice_id}")
print(f"  • Medical Record: ID {record_id}")
