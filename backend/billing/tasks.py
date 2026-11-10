from datetime import timedelta

from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task
def check_overdue_invoices():
    """Periodic task to flag past-due unpaid invoices as overdue."""
    from .models import Invoice
    today = timezone.localdate()
    updated_count = Invoice.objects.filter(
        due_date__lt=today,
        status__in=['pending', 'partially_paid']
    ).update(status='overdue')
    logger.info(f"Updated {updated_count} overdue invoices.")
    return f"Updated {updated_count} overdue invoices."


@shared_task
def send_appointment_reminder_email(appointment_id):
    """Create an in-app reminder for an appointment (idempotent)."""
    from appointments.models import Appointment
    from ai_agents.models import Notification
    try:
        appointment = Appointment.objects.select_related('patient', 'doctor').get(id=appointment_id)
    except Appointment.DoesNotExist:
        logger.warning(f"Appointment {appointment_id} not found for reminder.")
        return False
    if appointment.status not in Appointment.ACTIVE_STATUSES:
        return False
    Notification.objects.get_or_create(
        dedupe_key=f'appt-reminder-{appointment.id}-{appointment.appointment_date}-{appointment.appointment_time}',
        defaults={
            'user': appointment.patient,
            'kind': 'appointment_reminder',
            'title': f'Appointment with Dr. {appointment.doctor.get_full_name()}',
            'body': f'Your appointment is on {appointment.appointment_date:%A %d %B} at '
                    f'{appointment.appointment_time:%H:%M}. Need to change it? Visit the Appointments page.',
            'link': '/patient/appointments',
        },
    )
    logger.info(f"Reminder created for appointment {appointment_id}")
    return True


@shared_task
def send_upcoming_appointment_reminders():
    """Hourly: make sure everyone with a visit in the next 24h has a reminder."""
    from appointments.models import Appointment
    today = timezone.localdate()
    upcoming = Appointment.objects.filter(
        appointment_date__range=(today, today + timedelta(days=1)),
        status__in=Appointment.ACTIVE_STATUSES,
    ).values_list('id', flat=True)
    for appointment_id in upcoming:
        send_appointment_reminder_email(appointment_id)
    return f'checked {len(upcoming)} appointments'
