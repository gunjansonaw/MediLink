"""
Pre-visit brief: a one-screen summary a doctor reads before an appointment.

Highlights are computed deterministically (so they're reliable and testable);
Claude, when available, writes the narrative summary from the same context.
"""
import json
import logging
from datetime import date

from django.utils import timezone

from .context import patient_context
from .llm import LLMRefusal, LLMUnavailable, create_message, llm_enabled, response_text
from .models import ClinicalBrief

logger = logging.getLogger(__name__)

BRIEF_SYSTEM = """You write pre-visit briefs for physicians. Input is JSON describing one patient and the
upcoming visit. Write at most ~170 words in this exact markdown structure:

**Reason for visit:** one line
**Key history:** 2-4 bullets (diagnoses with dates, chronic conditions)
**Meds & allergies:** 1-3 bullets (flag any open safety alerts)
**Trends & pending:** 1-3 bullets (vitals trends with numbers, pending/abnormal labs)
**Suggested focus:** 1-2 bullets

Rules: use only facts in the JSON, include dates and values, say "not recorded" when data is missing,
no diagnosis or treatment decisions — this is a briefing, not advice."""


def compute_highlights(ctx: dict) -> list:
    """Deterministic red flags: [{level, text}]"""
    out = []
    allergies = ctx.get('allergies', '')
    if allergies and allergies.lower() not in ('none', 'none recorded', 'nka', 'nkda'):
        out.append({'level': 'warning', 'text': f'Allergies: {allergies}'})
    conditions = ctx.get('chronic_conditions', '')
    if conditions and conditions != 'None recorded':
        out.append({'level': 'info', 'text': f'Chronic: {conditions}'})

    vitals = ctx.get('vitals_recent_first') or []
    if vitals:
        v = vitals[0]
        if (v.get('bp_systolic') or 0) >= 140 or (v.get('bp_diastolic') or 0) >= 90:
            out.append({'level': 'warning', 'text': f"Elevated BP {v['bp']} on {v['recorded_at']}"})
        sys_series = [x['bp_systolic'] for x in vitals[:3] if x.get('bp_systolic')]
        if len(sys_series) == 3 and sys_series[0] > sys_series[1] > sys_series[2]:
            out.append({'level': 'warning', 'text': f'Systolic BP rising over last 3 readings: {list(reversed(sys_series))}'})
        if v.get('spo2') is not None and v['spo2'] < 94:
            out.append({'level': 'critical', 'text': f"Low SpO₂ {v['spo2']}% on {v['recorded_at']}"})
        if v.get('heart_rate') and v['heart_rate'] > 100:
            out.append({'level': 'warning', 'text': f"Tachycardia {v['heart_rate']} bpm on {v['recorded_at']}"})
        if v.get('temperature_c') and v['temperature_c'] >= 38:
            out.append({'level': 'warning', 'text': f"Fever {v['temperature_c']}°C on {v['recorded_at']}"})
        if v.get('bmi') and v['bmi'] >= 30:
            out.append({'level': 'info', 'text': f"BMI {v['bmi']}"})

    for rx in ctx.get('active_medications', []):
        for alert in rx.get('open_safety_alerts', []):
            out.append({'level': 'critical', 'text': f"Unacknowledged safety alert on {rx['medication']}: {alert}"})

    today = timezone.localdate()
    for lab in ctx.get('lab_tests', []):
        if lab['status'] in ('ordered', 'in_progress'):
            age = (today - date.fromisoformat(lab['ordered'])).days
            if age > 7:
                out.append({'level': 'warning', 'text': f"{lab['test']} pending for {age} days"})

    history = ctx.get('appointment_history', {})
    if history.get('no_shows', 0) >= 2:
        out.append({'level': 'info', 'text': f"{history['no_shows']} previous no-shows"})
    return out


def rules_brief(ctx: dict, appointment) -> str:
    lines = [f'**Reason for visit:** {appointment.reason}']
    recs = ctx.get('recent_records', [])[:3]
    lines.append('**Key history:** ' + ('; '.join(f"{r['diagnosis']} ({r['date']})" for r in recs) or 'no prior records'))
    meds = ctx.get('active_medications', [])
    lines.append('**Meds & allergies:** ' + (', '.join(f"{m['medication']} {m['dosage']}" for m in meds) or 'no active medications')
                 + f" · Allergies: {ctx.get('allergies')}")
    v = (ctx.get('vitals_recent_first') or [None])[0]
    lines.append('**Latest vitals:** ' + (f"BP {v['bp'] or '—'}, HR {v['heart_rate'] or '—'}, SpO₂ {v['spo2'] or '—'}% ({v['recorded_at']})"
                                          if v else 'not recorded'))
    pending = [l['test'] for l in ctx.get('lab_tests', []) if l['status'] in ('ordered', 'in_progress')]
    if pending:
        lines.append('**Pending labs:** ' + ', '.join(pending))
    return '\n\n'.join(lines)


def generate_brief(appointment, force=False) -> ClinicalBrief:
    existing = ClinicalBrief.objects.filter(appointment=appointment).first()
    if existing and not force:
        return existing

    ctx = patient_context(appointment.patient)
    highlights = compute_highlights(ctx)
    content, source = None, 'rules'
    if llm_enabled():
        payload = {
            'visit': {'date': appointment.appointment_date.isoformat(),
                      'time': appointment.appointment_time.strftime('%H:%M'), 'reason': appointment.reason},
            'patient': ctx,
            'computed_red_flags': highlights,
        }
        try:
            response = create_message(
                system=BRIEF_SYSTEM,
                messages=[{'role': 'user', 'content': json.dumps(payload, default=str)}],
                max_tokens=4000,
                effort='low',  # summarisation of structured data; low effort keeps it fast + cheap
            )
            content, source = response_text(response), 'llm'
        except (LLMUnavailable, LLMRefusal):
            pass
        except Exception:
            logger.exception('LLM brief failed for appointment %s; using rules brief', appointment.pk)

    if not content:
        content = rules_brief(ctx, appointment)

    brief, _ = ClinicalBrief.objects.update_or_create(
        appointment=appointment,
        defaults={'content': content, 'highlights': highlights, 'source': source},
    )
    return brief
