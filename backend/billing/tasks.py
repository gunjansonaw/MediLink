from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task
def check_overdue_invoices():
    """Periodic task to flag past-due pending invoices as overdue."""
    from .models import Invoice
    today = timezone.now().date()
    updated_count = Invoice.objects.filter(
        due_date__lt=today,
        status__in=['pending', 'partially_paid']
    ).update(status='overdue')
    logger.info(f"Updated {updated_count} overdue invoices.")
    return f"Updated {updated_count} overdue invoices."


@shared_task
def send_appointment_reminder_email(appointment_id):
    """Background task to simulate sending appointment reminder to patient."""
    from appointments.models import Appointment
    try:
        appointment = Appointment.objects.select_related('patient', 'doctor').get(id=appointment_id)
        logger.info(
            f"Reminder sent to {appointment.patient.email} for appointment with "
            f"Dr. {appointment.doctor.get_full_name()} on {appointment.appointment_date}"
        )
        return True
    except Appointment.DoesNotExist:
        logger.warning(f"Appointment {appointment_id} not found for reminder.")
        return False
