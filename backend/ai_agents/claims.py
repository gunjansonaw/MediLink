"""Insurance claim pre-check: catch likely rejection reasons before submission."""
import json
import logging

from django.utils import timezone

from medical_records.models import MedicalRecord
from .llm import LLMRefusal, LLMUnavailable, create_message, llm_enabled, response_text

logger = logging.getLogger(__name__)

WEIGHTS = {'high': 40, 'medium': 20, 'low': 5}


def _norm(s):
    return ''.join(ch for ch in (s or '').lower() if ch.isalnum())


def precheck_claim(claim, use_llm=True) -> dict:
    issues = []
    invoice = claim.invoice
    profile = getattr(claim.patient, 'patient_profile', None)

    def add(severity, code, message):
        issues.append({'severity': severity, 'code': code, 'message': message})

    if invoice.patient_id != claim.patient_id:
        add('high', 'patient_mismatch', 'Claim patient differs from the invoice patient.')
    if profile:
        if profile.insurance_number and _norm(profile.insurance_number) != _norm(claim.insurance_policy_number):
            add('high', 'policy_mismatch', 'Policy number does not match the patient profile.')
        if profile.insurance_provider and _norm(profile.insurance_provider)[:6] != _norm(claim.insurance_provider)[:6]:
            add('medium', 'provider_mismatch', 'Insurance provider differs from the patient profile.')
        if not profile.insurance_number:
            add('medium', 'no_policy_on_file', 'Patient profile has no insurance number on file to verify against.')
    if claim.claim_amount > invoice.total:
        add('high', 'amount_exceeds_invoice', 'Claim amount exceeds the invoice total.')
    if invoice.status == 'cancelled':
        add('high', 'invoice_cancelled', 'Invoice is cancelled.')
    if not invoice.items.exists():
        add('medium', 'no_line_items', 'Invoice has no itemised services; payers usually require itemisation.')

    appointment = invoice.appointment
    if appointment is None:
        add('medium', 'no_encounter', 'Invoice is not linked to an appointment (no documented encounter).')
    else:
        if appointment.status != 'completed':
            add('high', 'encounter_not_completed', f'Linked appointment is {appointment.status}, not completed.')
        has_dx = MedicalRecord.objects.filter(patient=claim.patient).filter(
            appointment=appointment).exists() or MedicalRecord.objects.filter(
            patient=claim.patient, doctor=appointment.doctor,
            created_at__date__gte=appointment.appointment_date).exists()
        if not has_dx:
            add('high', 'no_diagnosis', 'No medical record/diagnosis documented for the encounter (medical necessity).')

    duplicates = claim.__class__.objects.filter(invoice=invoice).exclude(pk=claim.pk).exclude(status='rejected')
    if duplicates.exists():
        add('high', 'duplicate', f'{duplicates.count()} other active claim(s) exist for this invoice.')
    if (claim.submitted_date - invoice.invoice_date).days > 90:
        add('medium', 'late_filing', 'Submitted more than 90 days after the invoice date.')

    score = min(100, sum(WEIGHTS[i['severity']] for i in issues))
    risk = 'high' if score >= 40 else 'medium' if score >= 20 else 'low'
    result = {'claim_id': claim.id, 'claim_number': claim.claim_number, 'risk': risk, 'score': score,
              'issues': issues, 'checked_at': timezone.now().isoformat(), 'summary': None}

    if use_llm and llm_enabled() and issues:
        try:
            response = create_message(
                system='You are a medical billing specialist. Given claim pre-check findings as JSON, write 2-4 '
                       'sentences for the billing admin: the most likely rejection reason first and the concrete '
                       'fix for each issue. No preamble.',
                messages=[{'role': 'user', 'content': json.dumps(result, default=str)}],
                max_tokens=1500, effort='low',
            )
            result['summary'] = response_text(response)
        except (LLMUnavailable, LLMRefusal):
            pass
        except Exception:
            logger.exception('LLM claim summary failed for claim %s', claim.pk)
    if not result['summary']:
        result['summary'] = ('No problems found — claim looks ready.' if not issues else
                             'Fix before submitting: ' + ' '.join(i['message'] for i in issues))
    return result
