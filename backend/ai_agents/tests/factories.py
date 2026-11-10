from datetime import date, time, timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.utils import timezone

from appointments.models import Appointment
from medical_records.models import MedicalRecord, Prescription
from users.models import DoctorProfile, PatientProfile, User


def make_doctor(username='doc', specialization='Cardiology', **kw):
    u = User.objects.create_user(username=username, password='x-Pass-12345', role='doctor',
                                 first_name=kw.pop('first_name', 'Sarah'), last_name=kw.pop('last_name', 'Chen'))
    DoctorProfile.objects.create(user=u, specialization=specialization, license_number=f'LIC-{username}',
                                 consultation_fee=Decimal('120.00'),
                                 available_days=['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'],
                                 available_hours={'start': '09:00', 'end': '17:00'})
    return u


def make_patient(username='pat', allergies='', conditions='', dob=date(1988, 6, 14), **kw):
    u = User.objects.create_user(username=username, password='x-Pass-12345', role='patient',
                                 first_name=kw.pop('first_name', 'John'), last_name=kw.pop('last_name', 'Doe'),
                                 date_of_birth=dob)
    PatientProfile.objects.create(user=u, allergies=allergies, chronic_conditions=conditions,
                                  insurance_provider='BlueCross Healthcare', insurance_number='BC-1')
    return u


def make_admin(username='admin'):
    return User.objects.create_user(username=username, password='x-Pass-12345', role='admin')


def make_record(patient, doctor, **kw):
    return MedicalRecord.objects.create(patient=patient, doctor=doctor, diagnosis=kw.get('diagnosis', 'Dx'),
                                        symptoms='s', treatment_plan='t')


def make_rx(record, name, dosage='10mg', frequency='once daily'):
    return Prescription.objects.create(medical_record=record, medication_name=name, dosage=dosage,
                                       frequency=frequency, duration='30 days')


def make_appt(patient, doctor, days_ahead=1, at=time(10, 0), status='scheduled'):
    return Appointment.objects.create(patient=patient, doctor=doctor,
                                      appointment_date=timezone.localdate() + timedelta(days=days_ahead),
                                      appointment_time=at, status=status, reason='Checkup')


# ── Fake Anthropic client ───────────────────────────────────────────────────

class Block(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(item)

    def to_dict(self):
        return dict(self)


def text(t):
    return Block(type='text', text=t)


def tool_use(id_, name, input_):
    return Block(type='tool_use', id=id_, name=name, input=input_)


class FakeClient:
    """Replays a scripted list of (stop_reason, [blocks]) and records requests."""

    def __init__(self, script):
        self.script = list(script)
        self.requests = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **params):
        import copy
        self.requests.append(copy.deepcopy(params))
        stop_reason, content = self.script.pop(0)
        return SimpleNamespace(stop_reason=stop_reason, content=content, stop_details=None, _request_id='req_test')
