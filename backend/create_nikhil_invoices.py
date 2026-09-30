import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medilink.settings')
django.setup()

from billing.models import Invoice
from users.models import User
from datetime import date, timedelta

# Get Nikhil's user (ID 8)
try:
    nikhil = User.objects.get(id=8, role='patient')
    print(f"Found user: {nikhil.first_name} {nikhil.last_name} (ID {nikhil.id})")
    
    # Create multiple invoices for Nikhil
    invoices_created = []
    
    # Invoice 1: Pending (this will show Pay button)
    inv1 = Invoice.objects.create(
        patient=nikhil,
        due_date=date.today() + timedelta(days=30),
        subtotal=500.00,
        tax=50.00,
        discount=10.00,
        notes='Doctor Consultation - Test Invoice'
    )
    invoices_created.append(inv1)
    
    # Invoice 2: Paid (this won't show Pay button)
    inv2 = Invoice.objects.create(
        patient=nikhil,
        due_date=date.today() - timedelta(days=10),
        subtotal=300.00,
        tax=30.00,
        discount=5.00,
        status='paid',
        notes='Lab Tests - Paid'
    )
    invoices_created.append(inv2)
    
    # Invoice 3: Pending 
    inv3 = Invoice.objects.create(
        patient=nikhil,
        due_date=date.today() + timedelta(days=15),
        subtotal=250.00,
        tax=25.00,
        discount=0,
        notes='Medication Charges - Test Invoice 2'
    )
    invoices_created.append(inv3)
    
    print(f"\n✓ Created {len(invoices_created)} invoices for Nikhil:\n")
    for inv in invoices_created:
        print(f"  Invoice #{inv.invoice_number}")
        print(f"    Status: {inv.status}")
        print(f"    Total: ${inv.total}")
        print()
    
    print("Now refresh your browser and go to Billing → All invoices should appear!")
    print("Click any PENDING invoice and you'll see the 'Pay Now' button")
    
except User.DoesNotExist:
    print("Error: Could not find Nikhil (patient, ID 8)")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
