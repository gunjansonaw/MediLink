"""
Builds the structured clinical context that agents read, and centralises the
"who may see which patient" rule so every tool enforces the same RBAC.
"""
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from appointments.models import Appointment
from medical_records.models import LabTest, MedicalRecord, Prescription, VitalSigns
from users.models import User


class AccessDenied(Exception):
    pass


def can_view_patient(user, patient) -> bool:
    if user.role == 'admin':
        return True
    if user.role == 'patient':
        return user.pk == patient.pk
    if user.role == 'doctor':
        # A doctor may see patients they have a care relationship with
        return (
            Appointment.objects.filter(doctor=user, patient=patient).exists()
            or MedicalRecord.objects.filter(doctor=user, patient=patient).exists()
        )
    return False


def get_patient_for(user, patient_id) -> User:
    try:
        patient = User.objects.select_related('patient_profile').get(pk=patient_id, role='patient')
    except (User.DoesNotExist, ValueError, TypeError):
        raise AccessDenied(f'Patient {patient_id} not found.')
    if not can_view_patient(user, patient):
        raise AccessDenied('You do not have a care relationship with this patient.')
    return patient


def visible_patients(user):
    qs = User.objects.filter(role='patient').select_related('patient_profile')
    if user.role == 'admin':
        return qs
    if user.role == 'doctor':
        return qs.filter(
            Q(patient_appointments__doctor=user) | Q(medical_records__doctor=user)
        ).distinct()
    if user.role == 'patient':
        return qs.filter(pk=user.pk)
    return qs.none()


def _age(dob):
    if not dob:
        return None
    today = timezone.localdate()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _vitals_dict(v):
    bmi = None
    if v.weight and v.height:
        h = float(v.height) / 100
        bmi = round(float(v.weight) / (h * h), 1) if h else None
    return {
        'recorded_at': v.recorded_at.date().isoformat(),
        'bp': f'{v.blood_pressure_systolic}/{v.blood_pressure_diastolic}'
        if v.blood_pressure_systolic and v.blood_pressure_diastolic else None,
        'bp_systolic': v.blood_pressure_systolic,
        'bp_diastolic': v.blood_pressure_diastolic,
        'heart_rate': v.heart_rate,
        'temperature_c': float(v.temperature) if v.temperature is not None else None,
        'respiratory_rate': v.respiratory_rate,
        'spo2': v.oxygen_saturation,
        'weight_kg': float(v.weight) if v.weight is not None else None,
        'bmi': bmi,
    }


def patient_context(patient, *, record_limit=10, include_billing=False) -> dict:
    """Everything an agent needs to reason about one patient (no free-form PII beyond name/age)."""
    profile = getattr(patient, 'patient_profile', None)
    records = (
        MedicalRecord.objects.filter(patient=patient)
        .select_related('doctor')
        .prefetch_related('prescriptions__safety_alerts', 'lab_tests')
        .order_by('-created_at')[:record_limit]
    )
    since = timezone.now() - timedelta(days=90)
    active_rx = Prescription.objects.filter(medical_record__patient=patient, created_at__gte=since).order_by('-created_at')
    vitals = VitalSigns.objects.filter(patient=patient).order_by('-recorded_at')[:6]
    labs = LabTest.objects.filter(medical_record__patient=patient).order_by('-ordered_date')[:15]
    appts = Appointment.objects.filter(patient=patient).select_related('doctor', 'doctor__doctor_profile')

    ctx = {
        'patient_id': patient.id,
        'name': patient.get_full_name() or patient.username,
        'age': _age(patient.date_of_birth),
        'blood_group': getattr(profile, 'blood_group', '') or None,
        'allergies': getattr(profile, 'allergies', '') or 'None recorded',
        'chronic_conditions': getattr(profile, 'chronic_conditions', '') or 'None recorded',
        'active_medications': [
            {'id': rx.id, 'medication': rx.medication_name, 'dosage': rx.dosage, 'frequency': rx.frequency,
             'duration': rx.duration, 'prescribed': rx.created_at.date().isoformat(),
             'open_safety_alerts': [a.message for a in rx.safety_alerts.all() if a.acknowledged_at is None]}
            for rx in active_rx.prefetch_related('safety_alerts')
        ],
        'recent_records': [
            {'id': r.id, 'date': r.created_at.date().isoformat(), 'doctor': f'Dr. {r.doctor.get_full_name()}',
             'diagnosis': r.diagnosis, 'symptoms': r.symptoms, 'treatment_plan': r.treatment_plan}
            for r in records
        ],
        'vitals_recent_first': [_vitals_dict(v) for v in vitals],
        'lab_tests': [
            {'id': t.id, 'test': t.test_name, 'type': t.test_type, 'status': t.status,
             'ordered': t.ordered_date.date().isoformat(), 'result': t.result or None,
             'completed': t.completed_date.date().isoformat() if t.completed_date else None}
            for t in labs
        ],
        'appointment_history': {
            'completed': appts.filter(status='completed').count(),
            'no_shows': appts.filter(status='no_show').count(),
            'cancelled': appts.filter(status='cancelled').count(),
            'upcoming': [
                {'id': a.id, 'date': a.appointment_date.isoformat(), 'time': a.appointment_time.strftime('%H:%M'),
                 'doctor': f'Dr. {a.doctor.get_full_name()}', 'reason': a.reason, 'status': a.status}
                for a in appts.filter(appointment_date__gte=timezone.localdate(),
                                      status__in=Appointment.ACTIVE_STATUSES).order_by('appointment_date')[:5]
            ],
        },
    }
    if include_billing:
        from billing.models import Invoice
        open_invoices = Invoice.objects.filter(patient=patient, status__in=['pending', 'partially_paid', 'overdue'])
        ctx['open_balance'] = float(sum((i.remaining_balance for i in open_invoices), 0))
    return ctx
