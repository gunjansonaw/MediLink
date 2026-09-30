#!/usr/bin/env python
"""
Test appointment creation both at database and API level
"""
import os
import sys
import django
import json

# Setup Django
sys.path.insert(0, r'd:\medilink\backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medilink.settings')
django.setup()

from django.test.client import Client
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from appointments.models import Appointment
from datetime import date, time

User = get_user_model()

# Create test client
client = Client()

# Get test users
patient = User.objects.filter(role='patient').first()
doctor = User.objects.filter(role='doctor').first()

if not patient:
    patient = User.objects.create_user(
        username='testpatient',
        email='testpatient@medilink.com',
        password='TestPass123!',
        role='patient',
        first_name='Test',
        last_name='Patient'
    )
    print(f"Created test patient: {patient.username}")

if not doctor:
    doctor = User.objects.create_user(
        username='testdoctor',
        email='testdoctor@medilink.com',
        password='TestPass123!',
        role='doctor',
        first_name='Test',
        last_name='Doctor'
    )
    print(f"Created test doctor: {doctor.username}")

# Get JWT token for patient
refresh = RefreshToken.for_user(patient)
access_token = str(refresh.access_token)

print(f"\nTesting appointment booking...")
print(f"Patient: {patient.username} (ID: {patient.id})")
print(f"Doctor: {doctor.username} (ID: {doctor.id})")

# Test data
appointment_data = {
    'doctor': doctor.id,
    'appointment_date': '2025-11-25',
    'appointment_time': '14:00:00',
    'duration_minutes': 30,
    'reason': 'Annual checkup',
    'notes': 'First time visit'
}

# Make API request
response = client.post(
    '/api/appointments/appointments/',
    data=json.dumps(appointment_data),
    content_type='application/json',
    HTTP_AUTHORIZATION=f'Bearer {access_token}'
)

print(f"\nAPI Response:")
print(f"Status Code: {response.status_code}")
print(f"Response: {json.dumps(json.loads(response.content.decode()), indent=2)}")

if response.status_code == 201:
    print("\n✓ Appointment booking SUCCESSFUL!")
    appointment = Appointment.objects.latest('id')
    print(f"  - Appointment ID: {appointment.id}")
    print(f"  - Patient: {appointment.patient.username}")
    print(f"  - Doctor: {appointment.doctor.username}")
    print(f"  - Date: {appointment.appointment_date}")
    print(f"  - Time: {appointment.appointment_time}")
    print(f"  - Status: {appointment.status}")
else:
    print("\n✗ Appointment booking FAILED")
    print(f"  - Check the error message above")
