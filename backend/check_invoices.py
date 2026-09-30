import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medilink.settings')
django.setup()

from billing.models import Invoice
from users.models import PatientProfile

# Check if invoices exist
print("=== INVOICES IN DATABASE ===")
invoices = Invoice.objects.all()
print(f"Total invoices: {invoices.count()}")

for invoice in invoices:
    patient_name = f"{invoice.patient.first_name} {invoice.patient.last_name}"
    print(f"Invoice #{invoice.invoice_number}: Status={invoice.status}, Patient={patient_name}, Total=${invoice.total}")

# Check if patient Nikhil exists
print("\n=== PATIENTS ===")
patients = PatientProfile.objects.all()
print(f"Total patients: {patients.count()}")
for patient in patients:
    print(f"Patient ID {patient.id}: {patient.user.first_name} {patient.user.last_name}")
