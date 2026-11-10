import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def generate_brief_task(appointment_id, force=False):
    from appointments.models import Appointment
    from .briefs import generate_brief
    appt = Appointment.objects.select_related('patient').filter(pk=appointment_id).first()
    if appt is None:
        return 'missing'
    generate_brief(appt, force=force)
    return 'ok'


@shared_task
def generate_upcoming_briefs(hours=36):
    """Pre-compute briefs for visits in the next `hours` so doctors never wait."""
    from appointments.models import Appointment
    from .briefs import generate_brief
    today = timezone.localdate()
    horizon = timezone.localtime(timezone.now() + timedelta(hours=hours)).date()
    appts = Appointment.objects.filter(
        appointment_date__range=(today, horizon),
        status__in=Appointment.ACTIVE_STATUSES, clinical_brief__isnull=True,
    ).select_related('patient')
    n = 0
    for appt in appts:
        try:
            generate_brief(appt)
            n += 1
        except Exception:
            logger.exception('Brief generation failed for appointment %s', appt.pk)
    return f'generated {n} briefs'


@shared_task
def explain_lab_task(lab_test_id):
    from medical_records.models import LabTest
    from .labs import explain_lab
    lab = LabTest.objects.select_related('medical_record__patient', 'medical_record__doctor').filter(pk=lab_test_id).first()
    if lab is None or lab.status != 'completed':
        return 'skipped'
    explain_lab(lab)
    return 'ok'


@shared_task
def run_collections_agent():
    from .proactive import run_collections
    return run_collections()


@shared_task
def run_care_followup_agent():
    from .proactive import run_care_followups
    return run_care_followups()


def safe_delay(task, *args):
    """Queue a task; if the broker is unreachable, run it inline instead of failing the request."""
    try:
        task.apply_async(args=args, retry=False)
    except Exception:
        logger.warning('Broker unavailable; running %s inline', task.name)
        try:
            task.apply(args=args)
        except Exception:
            logger.exception('Inline execution of %s failed', task.name)
