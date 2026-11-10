from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, date, time
from decimal import Decimal
from users.models import User, DoctorProfile, PatientProfile
from appointments.models import Appointment, Schedule
from medical_records.models import MedicalRecord, Prescription, LabTest, VitalSigns
from billing.models import Invoice, InvoiceItem, Payment, InsuranceClaim


class Command(BaseCommand):
    help = 'Seeds realistic SaaS demo data for interviews and presentations'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Starting MediLink SaaS database seeding...'))

        # 1. Admin User
        admin, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@medilink.health',
                'first_name': 'Alexander',
                'last_name': 'Vance',
                'role': 'admin',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if created:
            admin.set_password('AdminPassword123!')
            admin.save()
            self.stdout.write(self.style.SUCCESS('Created Admin: admin / AdminPassword123!'))
        else:
            self.stdout.write('Admin already exists.')

        # 2. Doctor Users
        dr_sarah, created = User.objects.get_or_create(
            username='doctor_sarah',
            defaults={
                'email': 'sarah.chen@medilink.health',
                'first_name': 'Sarah',
                'last_name': 'Chen',
                'role': 'doctor',
                'phone': '+15552345678',
            }
        )
        if created:
            dr_sarah.set_password('DoctorPassword123!')
            dr_sarah.save()
            DoctorProfile.objects.create(
                user=dr_sarah,
                specialization='Cardiology',
                license_number='MED-CA-99214',
                experience_years=12,
                consultation_fee=Decimal('120.00'),
                available_days=['Monday', 'Tuesday', 'Thursday', 'Friday'],
                available_hours={'start': '09:00', 'end': '17:00'},
                bio='Board-certified cardiologist specializing in preventive cardiovascular medicine and diagnostic imaging.'
            )
            self.stdout.write(self.style.SUCCESS('Created Doctor: doctor_sarah / DoctorPassword123!'))

        dr_james, created = User.objects.get_or_create(
            username='doctor_james',
            defaults={
                'email': 'james.wilson@medilink.health',
                'first_name': 'James',
                'last_name': 'Wilson',
                'role': 'doctor',
                'phone': '+15553456789',
            }
        )
        if created:
            dr_james.set_password('DoctorPassword123!')
            dr_james.save()
            DoctorProfile.objects.create(
                user=dr_james,
                specialization='Pediatrics & Family Care',
                license_number='MED-NY-84192',
                experience_years=8,
                consultation_fee=Decimal('85.00'),
                available_days=['Monday', 'Wednesday', 'Friday'],
                available_hours={'start': '08:30', 'end': '16:30'},
                bio='Compassionate pediatrician committed to family health, wellness screenings, and holistic pediatric care.'
            )
            self.stdout.write(self.style.SUCCESS('Created Doctor: doctor_james / DoctorPassword123!'))

        # 3. Patient Users
        patient_john, created = User.objects.get_or_create(
            username='patient_john',
            defaults={
                'email': 'john.doe@gmail.com',
                'first_name': 'John',
                'last_name': 'Doe',
                'role': 'patient',
                'phone': '+15559876543',
                'date_of_birth': date(1988, 6, 14),
                'address': '742 Evergreen Terrace, Springfield',
            }
        )
        if created:
            patient_john.set_password('PatientPassword123!')
            patient_john.save()
            PatientProfile.objects.create(
                user=patient_john,
                blood_group='O+',
                emergency_contact='+15559870000',
                emergency_contact_name='Jane Doe',
                allergies='Penicillin',
                chronic_conditions='Mild Hypertension',
                insurance_provider='BlueCross Healthcare',
                insurance_number='BC-77291-884'
            )
            self.stdout.write(self.style.SUCCESS('Created Patient: patient_john / PatientPassword123!'))

        patient_emma, created = User.objects.get_or_create(
            username='patient_emma',
            defaults={
                'email': 'emma.stone@gmail.com',
                'first_name': 'Emma',
                'last_name': 'Watson',
                'role': 'patient',
                'phone': '+15558765432',
                'date_of_birth': date(1994, 3, 22),
            }
        )
        if created:
            patient_emma.set_password('PatientPassword123!')
            patient_emma.save()
            PatientProfile.objects.create(
                user=patient_emma,
                blood_group='A-',
                emergency_contact='+15558760000',
                emergency_contact_name='Robert Watson',
                allergies='None',
                insurance_provider='Aetna Global Health',
                insurance_number='AET-49219'
            )
            self.stdout.write(self.style.SUCCESS('Created Patient: patient_emma / PatientPassword123!'))

        # 4. Appointments
        today = timezone.now().date()
        apt1, _ = Appointment.objects.get_or_create(
            doctor=dr_sarah,
            appointment_date=today + timedelta(days=1),
            appointment_time=time(10, 0),
            defaults={
                'patient': patient_john,
                'duration_minutes': 45,
                'status': 'confirmed',
                'reason': 'Routine cardiovascular checkup and ECG follow-up review.',
            }
        )

        apt2, _ = Appointment.objects.get_or_create(
            doctor=dr_james,
            appointment_date=today + timedelta(days=2),
            appointment_time=time(14, 30),
            defaults={
                'patient': patient_emma,
                'duration_minutes': 30,
                'status': 'scheduled',
                'reason': 'Seasonal allergy consultation and immune booster prescription.',
            }
        )

        # 5. Medical Records
        rec1, _ = MedicalRecord.objects.get_or_create(
            patient=patient_john,
            doctor=dr_sarah,
            diagnosis='Essential Hypertension (Stage 1)',
            defaults={
                'symptoms': 'Occasional morning headaches, elevated resting blood pressure (138/88 mmHg).',
                'treatment_plan': 'Dietary modification (low sodium), daily 30-min walking, lisinopril 10mg once daily.',
                'notes': 'Patient is responsive to lifestyle changes. Re-check vitals in 4 weeks.',
            }
        )
        Prescription.objects.get_or_create(
            medical_record=rec1,
            medication_name='Lisinopril',
            defaults={
                'dosage': '10mg',
                'frequency': 'Once daily in the morning',
                'duration': '30 days',
                'instructions': 'Take with full glass of water, monitor blood pressure weekly.',
            }
        )

        # 6. Invoices & Payments
        inv1, _ = Invoice.objects.get_or_create(
            invoice_number='INV-2026-001',
            defaults={
                'patient': patient_john,
                'appointment': apt1,
                'due_date': today + timedelta(days=14),
                'status': 'partially_paid',
                'subtotal': Decimal('150.00'),
                'tax': Decimal('12.00'),
                'discount': Decimal('10.00'),
                'total': Decimal('152.00'),
                'notes': 'Cardiology consultation & resting ECG analysis.',
            }
        )
        InvoiceItem.objects.get_or_create(
            invoice=inv1,
            description='Specialist Cardiology Consultation',
            defaults={'quantity': 1, 'unit_price': Decimal('120.00'), 'total': Decimal('120.00')}
        )
        InvoiceItem.objects.get_or_create(
            invoice=inv1,
            description='In-Clinic Resting 12-Lead ECG',
            defaults={'quantity': 1, 'unit_price': Decimal('30.00'), 'total': Decimal('30.00')}
        )
        # Partial payment of $76
        Payment.objects.get_or_create(
            invoice=inv1,
            transaction_id='TXN-INIT-001',
            defaults={
                'amount': Decimal('76.00'),
                'payment_method': 'credit_card',
                'notes': '50% initial co-pay processed online.',
            }
        )
        inv1.sync_payment_status()

        # Fully Paid Invoice
        inv2, _ = Invoice.objects.get_or_create(
            invoice_number='INV-2026-002',
            defaults={
                'patient': patient_emma,
                'appointment': apt2,
                'due_date': today + timedelta(days=7),
                'status': 'paid',
                'subtotal': Decimal('85.00'),
                'tax': Decimal('6.80'),
                'discount': Decimal('0.00'),
                'total': Decimal('91.80'),
                'notes': 'Pediatric & allergy consultation.',
            }
        )
        InvoiceItem.objects.get_or_create(
            invoice=inv2,
            description='General Consultation Fee',
            defaults={'quantity': 1, 'unit_price': Decimal('85.00'), 'total': Decimal('85.00')}
        )
        Payment.objects.get_or_create(
            invoice=inv2,
            transaction_id='TXN-INIT-002',
            defaults={
                'amount': Decimal('91.80'),
                'payment_method': 'online',
                'notes': 'Full balance cleared via portal.',
            }
        )
        inv2.sync_payment_status()

        # 7. AI-agent demo data: history, vitals, labs, an overdue bill, a claim
        past = today - timedelta(days=21)
        apt_past, _ = Appointment.objects.get_or_create(
            doctor=dr_sarah, appointment_date=past, appointment_time=time(11, 0),
            defaults={'patient': patient_john, 'status': 'completed', 'duration_minutes': 30,
                      'reason': 'Blood pressure review and lipid panel.'},
        )
        Appointment.objects.get_or_create(
            doctor=dr_james, appointment_date=today - timedelta(days=10), appointment_time=time(9, 0),
            defaults={'patient': patient_emma, 'status': 'no_show', 'reason': 'Allergy follow-up.'},
        )
        rec_past, _ = MedicalRecord.objects.get_or_create(
            patient=patient_john, doctor=dr_sarah, appointment=apt_past,
            defaults={'diagnosis': 'Hypertension follow-up; borderline hyperlipidemia',
                      'symptoms': 'Occasional headaches, no chest pain.',
                      'treatment_plan': 'Continue lisinopril, lipid panel ordered, recheck in 4 weeks.'},
        )
        if not VitalSigns.objects.filter(patient=patient_john).exists():
            for days_ago, sys_bp, dia_bp in [(60, 132, 84), (35, 136, 86), (21, 142, 91)]:
                v = VitalSigns.objects.create(
                    patient=patient_john, recorded_by=dr_sarah, blood_pressure_systolic=sys_bp,
                    blood_pressure_diastolic=dia_bp, heart_rate=78, temperature=Decimal('36.8'),
                    oxygen_saturation=98, weight=Decimal('88.5'), height=Decimal('178'),
                )
                VitalSigns.objects.filter(pk=v.pk).update(recorded_at=timezone.now() - timedelta(days=days_ago))
        LabTest.objects.get_or_create(
            medical_record=rec_past, test_name='Lipid Panel',
            defaults={'test_type': 'Blood', 'status': 'completed', 'completed_date': timezone.now() - timedelta(days=19),
                      'result': 'Total cholesterol 228 mg/dL, LDL 162 mg/dL, HDL 41 mg/dL, Triglycerides 175 mg/dL'},
        )
        LabTest.objects.get_or_create(
            medical_record=rec_past, test_name='HbA1c',
            defaults={'test_type': 'Blood', 'status': 'ordered'},
        )
        inv_old, created_old = Invoice.objects.get_or_create(
            invoice_number='INV-2026-003',
            defaults={'patient': patient_john, 'appointment': apt_past, 'due_date': past + timedelta(days=7) - timedelta(days=20),
                      'subtotal': Decimal('160.00'), 'tax': Decimal('12.80'), 'discount': Decimal('0.00'),
                      'total': Decimal('172.80'), 'notes': 'BP review and lipid panel.'},
        )
        if created_old:
            InvoiceItem.objects.create(invoice=inv_old, description='Cardiology follow-up consultation',
                                       quantity=1, unit_price=Decimal('120.00'))
            InvoiceItem.objects.create(invoice=inv_old, description='Lipid panel', quantity=1, unit_price=Decimal('40.00'))
            inv_old.sync_payment_status()
            InsuranceClaim.objects.create(
                patient=patient_john, invoice=inv_old, insurance_provider='BlueCross Healthcare',
                insurance_policy_number='BC-77291-884', claim_amount=Decimal('150.00'),
            )
        for doc, days in [(dr_sarah, ['monday', 'tuesday', 'thursday', 'friday']),
                          (dr_james, ['monday', 'wednesday', 'friday'])]:
            for day in days:
                Schedule.objects.get_or_create(doctor=doc, day_of_week=day, start_time=time(9, 0),
                                               defaults={'end_time': time(17, 0)})

        self.stdout.write(self.style.SUCCESS('\n========================================='))
        self.stdout.write(self.style.SUCCESS('  MediLink SaaS Demo Data Ready!'))
        self.stdout.write(self.style.SUCCESS('========================================='))
        self.stdout.write('  Admin:   admin         / AdminPassword123!')
        self.stdout.write('  Doctor:  doctor_sarah  / DoctorPassword123!')
        self.stdout.write('  Doctor:  doctor_james  / DoctorPassword123!')
        self.stdout.write('  Patient: patient_john  / PatientPassword123!')
        self.stdout.write('  Patient: patient_emma  / PatientPassword123!')
        self.stdout.write(self.style.SUCCESS('=========================================\n'))
