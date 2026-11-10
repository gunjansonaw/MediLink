"""
Executes PendingActions after a human approves them.

Everything is re-validated at approval time (slots may have been taken, the
appointment may have been cancelled, permissions may have changed), so a stale
proposal fails safely instead of corrupting data.
"""
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from appointments.models import Appointment
from appointments.services import SlotUnavailable, book_appointment
from billing.models import Invoice, InvoiceItem
from users.models import User

from .models import Notification, PendingAction


class ActionError(Exception):
    pass


def can_decide(user, action: PendingAction) -> bool:
    if action.approver_role == 'admin':
        return user.role == 'admin'
    return action.requested_by_id == user.id


def _book(action):
    p = action.payload
    patient = User.objects.get(pk=p['patient_id'], role='patient')
    doctor = User.objects.get(pk=p['doctor_id'], role='doctor')
    day = datetime.strptime(p['date'], '%Y-%m-%d').date()
    slot = datetime.strptime(p['time'], '%H:%M').time()
    if timezone.make_aware(datetime.combine(day, slot)) < timezone.now():
        raise ActionError('This slot is now in the past.')
    try:
        appt = book_appointment(patient=patient, doctor=doctor, appointment_date=day,
                                appointment_time=slot, reason=p['reason'])
    except SlotUnavailable as exc:
        raise ActionError(str(exc))
    return {'appointment_id': appt.id, 'message': f'Booked for {day:%a %d %b} at {slot:%H:%M}.'}


def _cancel(action, user):
    appt = Appointment.objects.filter(pk=action.payload['appointment_id']).first()
    if appt is None:
        raise ActionError('Appointment no longer exists.')
    allowed = (user.role == 'admin' or appt.patient_id == user.id or appt.doctor_id == user.id)
    if not allowed:
        raise ActionError('You can no longer modify this appointment.')
    if appt.status not in Appointment.ACTIVE_STATUSES:
        raise ActionError(f'Appointment is already {appt.status}.')
    appt.status = 'cancelled'
    if action.payload.get('reason'):
        appt.notes = (appt.notes + '\n' if appt.notes else '') + f"Cancelled via assistant: {action.payload['reason']}"
    appt.save(update_fields=['status', 'notes', 'updated_at'])
    return {'appointment_id': appt.id, 'message': 'Appointment cancelled.'}


def _invoice(action):
    p = action.payload
    appt = Appointment.objects.select_related('patient').get(pk=p['appointment_id'])
    if Invoice.objects.filter(appointment=appt).exclude(status='cancelled').exists():
        raise ActionError('This appointment already has an invoice.')
    invoice = Invoice.objects.create(
        patient=appt.patient, appointment=appt,
        due_date=timezone.localdate() + timedelta(days=int(p.get('due_in_days', 14))),
        tax=p.get('tax', 0), subtotal=0, total=0,
        notes='Drafted by billing assistant, approved by admin.',
    )
    for item in p['items']:
        InvoiceItem.objects.create(invoice=invoice, description=item['description'],
                                   quantity=item.get('quantity', 1), unit_price=item['unit_price'])
    invoice.recalculate_from_items()
    invoice.sync_payment_status()
    return {'invoice_id': invoice.id, 'message': f'Invoice {invoice.invoice_number} created (${invoice.total}).'}


def _message(action):
    p = action.payload
    patient = User.objects.get(pk=p['patient_id'], role='patient')
    Notification.objects.create(user=patient, kind='agent', title=p['title'], body=p['body'])
    return {'message': f'Message sent to {patient.get_full_name()}.'}


def approve(action: PendingAction, user):
    if not can_decide(user, action):
        raise ActionError('You are not allowed to approve this action.')
    if action.status != 'pending':
        raise ActionError(f'Action is already {action.status}.')
    if action.created_at < timezone.now() - timedelta(days=2):
        action.status = 'expired'
        action.save(update_fields=['status'])
        raise ActionError('This proposal has expired; ask the assistant again.')

    handlers = {
        'book_appointment': lambda: _book(action),
        'cancel_appointment': lambda: _cancel(action, user),
        'draft_invoice': lambda: _invoice(action),
        'send_patient_message': lambda: _message(action),
    }
    try:
        with transaction.atomic():
            result = handlers[action.action_type]()
            action.status = 'approved'
    except (ActionError, User.DoesNotExist, Appointment.DoesNotExist, KeyError, ValueError) as exc:
        result = {'error': str(exc) or exc.__class__.__name__}
        action.status = 'failed'
    action.result = result
    action.decided_by = user
    action.decided_at = timezone.now()
    action.save(update_fields=['status', 'result', 'decided_by', 'decided_at'])
    return action


def reject(action: PendingAction, user):
    if not can_decide(user, action):
        raise ActionError('You are not allowed to reject this action.')
    if action.status != 'pending':
        raise ActionError(f'Action is already {action.status}.')
    action.status = 'rejected'
    action.decided_by = user
    action.decided_at = timezone.now()
    action.save(update_fields=['status', 'decided_by', 'decided_at'])
    return action
