"""Regression tests for bugs fixed across the core apps."""
from datetime import time, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from appointments.models import Appointment
from billing.models import Invoice, InvoiceItem, Payment
from medical_records.models import MedicalRecord

from .factories import make_admin, make_appt, make_doctor, make_patient, make_record


class BugfixTests(TestCase):
    def setUp(self):
        self.doctor = make_doctor()
        self.patient = make_patient()
        self.other_patient = make_patient(username='emma', first_name='Emma')
        self.admin = make_admin()
        self.client = APIClient()

    def as_(self, user):
        self.client.force_authenticate(user)
        return self.client

    # users
    def test_patient_cannot_list_other_patients(self):
        resp = self.as_(self.patient).get('/api/users/?page_size=100')
        ids = {u['id'] for u in resp.data['results']}
        self.assertNotIn(self.other_patient.id, ids)
        self.assertIn(self.doctor.id, ids)

    def test_patient_cannot_delete_self_or_others(self):
        self.assertEqual(self.as_(self.patient).delete(f'/api/users/{self.other_patient.id}/').status_code, 403)

    # appointments
    def test_cancelled_slot_can_be_rebooked(self):
        day = (timezone.localdate() + timedelta(days=3)).isoformat()
        c = self.as_(self.patient)
        r1 = c.post('/api/appointments/appointments/', {'doctor': self.doctor.id, 'appointment_date': day,
                                                         'appointment_time': '10:00', 'reason': 'x'})
        self.assertEqual(r1.status_code, 201, r1.data)
        c.post(f"/api/appointments/appointments/{r1.data['id']}/cancel/")
        r2 = c.post('/api/appointments/appointments/', {'doctor': self.doctor.id, 'appointment_date': day,
                                                         'appointment_time': '10:00', 'reason': 'y'})
        self.assertEqual(r2.status_code, 201, r2.data)
        r3 = self.as_(self.other_patient).post('/api/appointments/appointments/', {
            'doctor': self.doctor.id, 'appointment_date': day, 'appointment_time': '10:00', 'reason': 'z'})
        self.assertEqual(r3.status_code, 400)

    def test_cannot_book_in_past_or_with_non_doctor(self):
        c = self.as_(self.patient)
        past = (timezone.localdate() - timedelta(days=1)).isoformat()
        self.assertEqual(c.post('/api/appointments/appointments/', {
            'doctor': self.doctor.id, 'appointment_date': past, 'appointment_time': '10:00', 'reason': 'x'}).status_code, 400)
        future = (timezone.localdate() + timedelta(days=1)).isoformat()
        self.assertEqual(c.post('/api/appointments/appointments/', {
            'doctor': self.other_patient.id, 'appointment_date': future, 'appointment_time': '10:00', 'reason': 'x'}).status_code, 400)

    def test_patient_cannot_mark_completed_or_reassign(self):
        appt = make_appt(self.patient, self.doctor)
        c = self.as_(self.patient)
        self.assertEqual(c.post(f'/api/appointments/appointments/{appt.id}/complete/').status_code, 403)
        c.patch(f'/api/appointments/appointments/{appt.id}/', {'status': 'completed', 'patient': self.other_patient.id})
        appt.refresh_from_db()
        self.assertEqual((appt.status, appt.patient_id), ('scheduled', self.patient.id))

    def test_admin_can_book_for_patient(self):
        day = (timezone.localdate() + timedelta(days=2)).isoformat()
        r = self.as_(self.admin).post('/api/appointments/appointments/', {
            'doctor': self.doctor.id, 'patient': self.patient.id, 'appointment_date': day,
            'appointment_time': '11:00', 'reason': 'x'})
        self.assertEqual(r.status_code, 201, r.data)

    def test_available_slots_excludes_booked(self):
        appt = make_appt(self.patient, self.doctor, days_ahead=2, at=time(9, 0))
        r = self.as_(self.patient).get('/api/appointments/appointments/available_slots/',
                                       {'doctor': self.doctor.id, 'start': appt.appointment_date.isoformat(),
                                        'end': appt.appointment_date.isoformat()})
        times = [s['time'] for s in r.data['slots']]
        self.assertNotIn('09:00', times)
        self.assertIn('09:30', times)

    # medical records
    def test_doctor_can_create_record_without_doctor_field(self):
        r = self.as_(self.doctor).post('/api/medical-records/records/', {
            'patient': self.patient.id, 'diagnosis': 'Flu', 'symptoms': 'fever', 'treatment_plan': 'rest'})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['doctor'], self.doctor.id)

    def test_doctor_cannot_prescribe_on_other_doctors_record(self):
        other_doc = make_doctor(username='doc2')
        record = make_record(self.patient, other_doc)
        r = self.as_(self.doctor).post('/api/medical-records/prescriptions/', {
            'medical_record': record.id, 'medication_name': 'X', 'dosage': '1', 'frequency': '1', 'duration': '1'})
        self.assertEqual(r.status_code, 400)

    def test_prescription_response_includes_safety_alerts(self):
        patient = make_patient(username='allergic', allergies='Penicillin')
        record = make_record(patient, self.doctor)
        r = self.as_(self.doctor).post('/api/medical-records/prescriptions/', {
            'medical_record': record.id, 'medication_name': 'Amoxicillin', 'dosage': '500mg',
            'frequency': 'three times daily', 'duration': '7 days'})
        self.assertEqual(r.status_code, 201)
        detail = self.client.get(f"/api/medical-records/prescriptions/{r.data['id']}/")
        self.assertEqual(detail.data['safety_alerts'][0]['severity'], 'critical')

    # billing
    def _invoice(self, total='100.00', patient=None):
        return Invoice.objects.create(patient=patient or self.patient, due_date=timezone.localdate() + timedelta(days=7),
                                      subtotal=Decimal(total), total=Decimal(total))

    def test_patient_cannot_create_invoice(self):
        r = self.as_(self.patient).post('/api/billing/invoices/', {
            'patient': self.patient.id, 'due_date': timezone.localdate().isoformat(), 'subtotal': '1'})
        self.assertEqual(r.status_code, 403)

    def test_overpayment_and_ledger_tampering_blocked(self):
        inv = self._invoice()
        c = self.as_(self.patient)
        self.assertEqual(c.post('/api/billing/payments/', {'invoice': inv.id, 'amount': '150', 'payment_method': 'online'}).status_code, 400)
        self.assertEqual(c.post('/api/billing/payments/', {'invoice': inv.id, 'amount': '-5', 'payment_method': 'online'}).status_code, 400)
        r = c.post('/api/billing/payments/', {'invoice': inv.id, 'amount': '40', 'payment_method': 'online'})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(c.patch(f"/api/billing/payments/{r.data['id']}/", {'amount': '100'}).status_code, 403)
        self.assertEqual(c.delete(f"/api/billing/payments/{r.data['id']}/").status_code, 403)
        inv.refresh_from_db()
        self.assertEqual(inv.status, 'partially_paid')

    def test_patient_cannot_pay_others_invoice(self):
        inv = self._invoice(patient=self.other_patient)
        r = self.as_(self.patient).post('/api/billing/payments/', {'invoice': inv.id, 'amount': '10', 'payment_method': 'online'})
        self.assertEqual(r.status_code, 403)

    def test_invoice_items_are_scoped_and_update_totals(self):
        inv = self._invoice(patient=self.other_patient)
        InvoiceItem.objects.create(invoice=inv, description='Secret', quantity=1, unit_price=Decimal('5'))
        r = self.as_(self.patient).get('/api/billing/invoice-items/')
        self.assertEqual(r.data['count'], 0)
        self.as_(self.admin).post('/api/billing/invoice-items/', {'invoice': inv.id, 'description': 'ECG', 'quantity': 2, 'unit_price': '30'})
        inv.refresh_from_db()
        self.assertEqual(inv.subtotal, Decimal('65.00'))

    def test_claims_cannot_be_self_approved_or_filed_for_others(self):
        own, other = self._invoice(), self._invoice(patient=self.other_patient)
        c = self.as_(self.patient)
        r = c.post('/api/billing/insurance-claims/', {'invoice': other.id, 'insurance_provider': 'A',
                                                      'insurance_policy_number': '1', 'claim_amount': '10'})
        self.assertEqual(r.status_code, 403)
        r = c.post('/api/billing/insurance-claims/', {'invoice': own.id, 'insurance_provider': 'A',
                                                      'insurance_policy_number': '1', 'claim_amount': '10',
                                                      'status': 'approved', 'approved_amount': '10'})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['status'], 'submitted')
        self.assertEqual(c.patch(f"/api/billing/insurance-claims/{r.data['id']}/", {'notes': 'x'}).status_code, 403)

    def test_invoice_pdf_escapes_html(self):
        inv = self._invoice()
        InvoiceItem.objects.create(invoice=inv, description='<script>alert(1)</script>', quantity=1, unit_price=Decimal('1'))
        r = self.as_(self.patient).get(f'/api/billing/invoices/{inv.id}/download_pdf/')
        self.assertNotIn(b'<script>alert(1)</script>', r.content)
        self.assertIn(b'&lt;script&gt;', r.content)

    def test_mark_paid_records_payment(self):
        inv = self._invoice()
        self.as_(self.admin).post(f'/api/billing/invoices/{inv.id}/mark_paid/')
        inv.refresh_from_db()
        self.assertEqual(inv.status, 'paid')
        self.assertEqual(inv.remaining_balance, Decimal('0'))

    def test_statistics_months_are_distinct(self):
        r = self.as_(self.admin).get('/api/billing/invoices/statistics/')
        months = [m['month'] for m in r.data['monthly_revenue']]
        self.assertEqual(len(months), len(set(months)))


class AuthCookieTests(TestCase):
    def setUp(self):
        self.patient = make_patient()

    def _login(self, client):
        client.get('/api/csrf/')
        r = client.post('/api/users/login/', {'username': 'pat', 'password': 'x-Pass-12345'}, format='json',
                        HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        self.assertEqual(r.status_code, 200)
        return r

    def test_refresh_rotates_and_logout_blacklists(self):
        client = APIClient(enforce_csrf_checks=True)
        r = self._login(client)
        self.assertEqual(r.cookies['medilink_refresh']['path'], '/api/users/')
        csrf = client.cookies['csrftoken'].value
        old_refresh = client.cookies['medilink_refresh'].value
        r = client.post('/api/users/token/refresh/', HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(r.status_code, 200)
        self.assertNotEqual(client.cookies['medilink_refresh'].value, old_refresh)
        # the rotated-out token is blacklisted
        replay = APIClient()
        replay.cookies['medilink_refresh'] = old_refresh
        self.assertEqual(replay.post('/api/users/token/refresh/').status_code, 401)
        # logout receives the refresh cookie and blacklists it
        current = client.cookies['medilink_refresh'].value
        self.assertEqual(client.post('/api/users/logout/', HTTP_X_CSRFTOKEN=csrf).status_code, 200)
        replay.cookies['medilink_refresh'] = current
        self.assertEqual(replay.post('/api/users/token/refresh/').status_code, 401)

    def test_cookie_auth_requires_csrf_token(self):
        client = APIClient(enforce_csrf_checks=True)
        self._login(client)
        r = client.post('/api/ai/chat/', {'message': 'hi'}, format='json')
        self.assertEqual(r.status_code, 403)
        self.assertIn('CSRF', str(r.data))

    def test_health_endpoints(self):
        c = APIClient()
        self.assertEqual(c.get('/api/health/').status_code, 200)
        self.assertEqual(c.get('/api/ready/').status_code, 200)
