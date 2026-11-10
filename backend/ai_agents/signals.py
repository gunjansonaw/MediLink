"""
Event-driven agent triggers.

* New/changed prescription  -> safety engine runs synchronously (fast, deterministic)
* Lab test completed        -> lab explainer runs in the background
* Appointment booked soon   -> pre-visit brief is generated in the background
"""
from datetime import timedelta

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from appointments.models import Appointment
from medical_records.models import LabTest, Prescription


@receiver(post_save, sender=Prescription)
def prescription_safety_check(sender, instance, created, update_fields=None, **kwargs):
    from .safety import record_alerts
    record_alerts(instance)


@receiver(post_save, sender=LabTest)
def lab_completed(sender, instance, created, **kwargs):
    if instance.status != 'completed':
        return
    from .tasks import explain_lab_task, safe_delay
    transaction.on_commit(lambda: safe_delay(explain_lab_task, instance.pk))


@receiver(post_save, sender=Appointment)
def appointment_brief(sender, instance, created, **kwargs):
    if not created or instance.status not in Appointment.ACTIVE_STATUSES:
        return
    if instance.appointment_date > timezone.localdate() + timedelta(days=2):
        return  # the hourly beat task will pick it up closer to the date
    from .tasks import generate_brief_task, safe_delay
    transaction.on_commit(lambda: safe_delay(generate_brief_task, instance.pk))
