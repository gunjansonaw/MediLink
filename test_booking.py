#!/usr/bin/env python
import os
import sys
import django

# Setup Django
sys.path.insert(0, r'd:\medilink\backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medilink.settings')
django.setup()

from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from appointments.models import Appointment
from users.models import User
from datetime import date, time

# Get a patient user
patient = User.objects.filter(role='patient').first()
doctor = User.objects.filter(role='doctor').first()

if not patient or not doctor:
    print("Need both patient and doctor users")
    sys.exit(1)

# Try to create an appointment
try:
    appointment = Appointment.objects.create(
        patient=patient,
        doctor=doctor,
        appointment_date=date(2025, 11, 20),
        appointment_time=time(10, 0),
        duration_minutes=30,
        reason="Consultation",
        status="scheduled"
    )
    print(f"✓ Appointment created successfully!")
    print(f"  ID: {appointment.id}")
    print(f"  Patient: {patient.username}")
    print(f"  Doctor: {doctor.username}")
    print(f"  Date: {appointment.appointment_date}")
    print(f"  Time: {appointment.appointment_time}")
except Exception as e:
    print(f"✗ Error creating appointment: {e}")
