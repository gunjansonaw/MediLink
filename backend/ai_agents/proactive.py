"""
Background agents that act without being asked (run by Celery beat):

* Collections agent – decides the next step for each overdue invoice:
  gentle reminder → payment-plan offer → escalation to an admin.
* Care follow-up agent – nudges patients with chronic conditions or abnormal
  labs who have no visit booked.

Decisions are deterministic policies (auditable, cheap); every message is
de-duplicated with Notification.dedupe_key so re-runs are idempotent.
"""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Max, Q
from django.utils import timezone

from appointments.models import Appointment
from billing.models import Invoice
from users.models import User

from .models import AgentToolCall, LabInsight, Notification


def _audit(agent, tool, payload, summary):
    AgentToolCall.objects.create(user=None, agent=agent, tool_name=tool, tool_input=payload,
                                 result_summary=summary, status='ok')


def collections_stage(days_overdue: int) -> str | None:
    if days_overdue <= 0:
        return None
    if days_overdue <= 14:
        return 'reminder'
    if days_overdue <= 45:
        return 'payment_plan'
    return 'escalate'


def run_collections(today=None) -> dict:
    today = today or timezone.localdate()
    counts = {'reminder': 0, 'payment_plan': 0, 'escalate': 0}
    admins = list(User.objects.filter(role='admin', is_active=True))
    qs = Invoice.objects.filter(status__in=['pending', 'partially_paid', 'overdue'], due_date__lt=today) \
        .select_related('patient').prefetch_related('payments')
    for inv in qs:
        balance = inv.remaining_balance
        if balance <= 0:
            continue
        days = (today - inv.due_date).days
        stage = collections_stage(days)
        if stage is None:
            continue
        if stage == 'reminder':
            _, created = Notification.objects.get_or_create(
                dedupe_key=f'collect-{inv.id}-reminder',
                defaults={'user': inv.patient, 'kind': 'payment_reminder',
                          'title': f'Friendly reminder: invoice {inv.invoice_number}',
                          'body': f'Your balance of ${balance:.2f} was due on {inv.due_date:%d %b %Y}. '
                                  'You can pay in full or in part from the Billing page. If you have already paid, '
                                  'please ignore this message.',
                          'link': '/patient/billing'})
        elif stage == 'payment_plan':
            instalment = (balance / 3).quantize(Decimal('0.01'))
            _, created = Notification.objects.get_or_create(
                dedupe_key=f'collect-{inv.id}-plan',
                defaults={'user': inv.patient, 'kind': 'payment_reminder',
                          'title': f'Payment plan available for invoice {inv.invoice_number}',
                          'body': f'Your balance of ${balance:.2f} is {days} days past due. We can split it into '
                                  f'three payments of about ${instalment:.2f}. Use "Pay Partial Amount" on the '
                                  'Billing page, or contact billing if you need help.',
                          'link': '/patient/billing'})
        else:
            created = False
            for admin in admins:
                _, c = Notification.objects.get_or_create(
                    dedupe_key=f'collect-{inv.id}-escalate-{admin.id}',
                    defaults={'user': admin, 'kind': 'payment_reminder',
                              'title': f'Escalation: {inv.invoice_number} is {days} days overdue',
                              'body': f'{inv.patient.get_full_name()} owes ${balance:.2f}. Automated reminders and a '
                                      'payment-plan offer were sent. Please follow up personally.',
                              'link': '/admin/billing'})
                created = created or c
        if created:
            counts[stage] += 1
            _audit('collections_agent', f'collections_{stage}',
                   {'invoice_id': inv.id, 'days_overdue': days}, f'{stage} for {inv.invoice_number}')
    return counts


def run_care_followups(today=None, inactivity_days=180) -> dict:
    today = today or timezone.localdate()
    month_key = today.strftime('%Y-%m')
    counts = {'chronic': 0, 'abnormal_lab': 0}

    def has_upcoming(patient_id):
        return Appointment.objects.filter(patient_id=patient_id, appointment_date__gte=today,
                                           status__in=Appointment.ACTIVE_STATUSES).exists()

    # 1) Chronic conditions with no recent completed visit
    chronic = User.objects.filter(role='patient', is_active=True) \
        .exclude(Q(patient_profile__chronic_conditions='') | Q(patient_profile__chronic_conditions__isnull=True)) \
        .annotate(last_visit=Max('patient_appointments__appointment_date',
                                 filter=Q(patient_appointments__status='completed')))
    for p in chronic:
        if p.last_visit and (today - p.last_visit).days < inactivity_days:
            continue
        if has_upcoming(p.id):
            continue
        _, created = Notification.objects.get_or_create(
            dedupe_key=f'followup-chronic-{p.id}-{month_key}',
            defaults={'user': p, 'kind': 'care_followup', 'title': 'Time for a check-up',
                      'body': f'Regular reviews help keep {p.patient_profile.chronic_conditions.lower()} well '
                              'controlled. It has been a while since your last visit — you can book one from the '
                              'Appointments page or ask the assistant.',
                      'link': '/patient/appointments'})
        if created:
            counts['chronic'] += 1
            _audit('care_followup_agent', 'followup_chronic', {'patient_id': p.id}, 'check-up nudge')

    # 2) Abnormal lab results without a follow-up booked
    recent = today - timedelta(days=60)
    for insight in LabInsight.objects.filter(needs_doctor_review=True, generated_at__date__gte=recent) \
            .select_related('lab_test__medical_record__patient'):
        patient = insight.lab_test.medical_record.patient
        if has_upcoming(patient.id):
            continue
        _, created = Notification.objects.get_or_create(
            dedupe_key=f'followup-lab-{insight.lab_test_id}',
            defaults={'user': patient, 'kind': 'care_followup',
                      'title': f'Follow-up recommended for your {insight.lab_test.test_name}',
                      'body': 'Some values in a recent lab result were outside the typical range. Please book a '
                              'follow-up visit so your doctor can go through it with you.',
                      'link': '/patient/appointments'})
        if created:
            counts['abnormal_lab'] += 1
            _audit('care_followup_agent', 'followup_abnormal_lab', {'lab_test_id': insight.lab_test_id}, 'lab nudge')
    return counts
