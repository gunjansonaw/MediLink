#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API Endpoint Test using requests library (HTTP calls to live server)
Make sure Django server is running on localhost:8000
"""
import requests
import json
from datetime import date, timedelta
import sys
import io
import random

# Force UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_URL = 'http://127.0.0.1:8000/api'

# Use simple ASCII characters instead of Unicode
SUCCESS = '[OK]'
ERROR = '[ERR]'
INFO = '[INFO]'

def print_header(text):
    print(f"\n{'='*60}")
    print(f"{text}")
    print(f"{'='*60}\n")

def print_success(text):
    print(f"{SUCCESS} {text}")

def print_error(text):
    print(f"{ERROR} {text}")

def print_info(text):
    print(f"{INFO} {text}")

def test_endpoint(method, endpoint, data=None, token=None, expected_status=200, description=""):
    """Test an API endpoint via HTTP"""
    url = f"{BASE_URL}{endpoint}"
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    
    try:
        if method == 'GET':
            response = requests.get(url, headers=headers)
        elif method == 'POST':
            response = requests.post(url, json=data, headers=headers)
        elif method == 'PATCH':
            response = requests.patch(url, json=data, headers=headers)
        elif method == 'PUT':
            response = requests.put(url, json=data, headers=headers)
        
        success = response.status_code == expected_status
        
        if success:
            print_success(f"{method:6} {endpoint:40} → {response.status_code} {description}")
        else:
            print_error(f"{method:6} {endpoint:40} → {response.status_code} (expected {expected_status})")
            if response.text:
                print_info(f"  Response: {response.text[:100]}")
        
        return response.json() if response.text else None
    except Exception as e:
        print_error(f"{method:6} {endpoint:40} → Connection Error: {str(e)[:50]}")
        return None

# ===== TEST AUTHENTICATION =====
print_header("TEST 1: Authentication")

# Test login
login_resp = test_endpoint('POST', '/users/login/', 
    data={'username': 'testuser', 'password': 'TestPass123!'},
    expected_status=200, description="User login")

if login_resp and 'access' in login_resp:
    access_token = login_resp['access']
    refresh_token = login_resp['refresh']
    user_data = login_resp['user']
    print_success(f"Got tokens for user: {user_data.get('username')}")
else:
    print_error("Failed to get tokens. Make sure 'testuser' exists or create one first.")
    sys.exit(1)

# ===== TEST USERS ENDPOINTS =====
print_header("TEST 2: Users Endpoints")

test_endpoint('GET', '/users/', token=access_token, description="List all users")
test_endpoint('GET', '/users/me/', token=access_token, description="Get current user")
test_endpoint('GET', '/users/doctors/', token=access_token, description="List doctors")

# ===== TEST APPOINTMENTS ENDPOINTS =====
print_header("TEST 3: Appointments Endpoints")

# Create appointment
appt_date = (date.today() + timedelta(days=7)).isoformat()
# Use random time to avoid unique constraint conflicts
random_hour = random.randint(9, 16)
appointment_time = f"{random_hour:02d}:00:00"
appointment_data = {
    'doctor': 2,  # Adjust ID as needed
    'appointment_date': appt_date,
    'appointment_time': appointment_time,
    'duration_minutes': 30,
    'reason': 'Annual Checkup'
}

appt_resp = test_endpoint('POST', '/appointments/appointments/',
    data=appointment_data, token=access_token, expected_status=201, 
    description="Create appointment")

if appt_resp and 'id' in appt_resp:
    appt_id = appt_resp['id']
    print_success(f"Created appointment ID: {appt_id}")
    
    test_endpoint('GET', '/appointments/appointments/', token=access_token, 
                 description="List appointments")
    test_endpoint('GET', f'/appointments/appointments/{appt_id}/', token=access_token,
                 description="Get appointment details")
    test_endpoint('GET', '/appointments/appointments/upcoming/', token=access_token,
                 description="Get upcoming appointments")
else:
    print_error("Failed to create appointment")
    appt_id = None

# ===== TEST BILLING ENDPOINTS =====
print_header("TEST 4: Billing Endpoints")

# Need admin token for creating invoices
admin_resp = test_endpoint('POST', '/users/login/',
    data={'username': 'testadmin', 'password': 'TestPass123!'},
    expected_status=200, description="Admin login")

if admin_resp and 'access' in admin_resp:
    admin_token = admin_resp['access']
    
    invoice_data = {
        'patient': 1,
        'due_date': (date.today() + timedelta(days=30)).isoformat(),
        'subtotal': 150.00,
        'tax': 15.00,
        'discount': 0.00
    }
    
    inv_resp = test_endpoint('POST', '/billing/invoices/',
        data=invoice_data, token=admin_token, expected_status=201,
        description="Create invoice")
    
    if inv_resp and 'id' in inv_resp:
        inv_id = inv_resp['id']
        print_success(f"Created invoice ID: {inv_id}")
        
        test_endpoint('GET', '/billing/invoices/', token=admin_token,
                     description="List invoices")
        test_endpoint('GET', f'/billing/invoices/{inv_id}/', token=admin_token,
                     description="Get invoice details")
        
        # Record payment
        payment_data = {
            'invoice': inv_id,
            'amount': 165.00,
            'payment_method': 'credit_card',
            'transaction_id': 'TEST-001'
        }
        
        pay_resp = test_endpoint('POST', '/billing/payments/',
            data=payment_data, token=admin_token, expected_status=201,
            description="Record payment")
        
        if pay_resp:
            print_success("Payment recorded successfully")
    
    # Get billing statistics
    test_endpoint('GET', '/billing/invoices/statistics/', token=admin_token,
                 description="Get billing statistics")
else:
    print_error("Admin login failed - skipping billing tests")

# ===== TEST MEDICAL RECORDS ENDPOINTS =====
print_header("TEST 5: Medical Records Endpoints")

# Need doctor token
doctor_resp = test_endpoint('POST', '/users/login/',
    data={'username': 'testdoctor', 'password': 'TestPass123!'},
    expected_status=200, description="Doctor login")

if doctor_resp and 'access' in doctor_resp:
    doctor_token = doctor_resp['access']
    
    record_data = {
        'patient': 1,
        'doctor': 2,
        'diagnosis': 'Hypertension',
        'symptoms': 'High blood pressure, headaches',
        'treatment_plan': 'Prescribed medication, lifestyle changes',
        'notes': 'Follow up after 30 days'
    }
    
    rec_resp = test_endpoint('POST', '/medical-records/records/',
        data=record_data, token=doctor_token, expected_status=201,
        description="Create medical record")
    
    if rec_resp and 'id' in rec_resp:
        rec_id = rec_resp['id']
        print_success(f"Created medical record ID: {rec_id}")
        
        test_endpoint('GET', '/medical-records/records/', token=access_token,
                     description="List medical records")
        test_endpoint('GET', '/medical-records/records/my_records/', token=access_token,
                     description="Get my medical records")
else:
    print_error("Doctor login failed - skipping medical records tests")

# ===== SUMMARY =====
print_header("TEST SUMMARY")
print_success("API endpoint testing completed!")
print_info("Review results above to check for any failures")
print(f"\nServer Status: {BASE_URL}")
