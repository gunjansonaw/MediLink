"""
Lab result explainer: flags abnormal analytes deterministically, then (optionally)
asks Claude for a patient-friendly explanation that never diagnoses.
"""
import json
import logging
import re

from .llm import LLMRefusal, LLMUnavailable, create_message, llm_enabled, response_text
from .models import LabInsight, Notification

logger = logging.getLogger(__name__)

# analyte: (regex, low, high, unit, plain-language name)
REFERENCE_RANGES = {
    'hba1c': (r'(?:hba1c|a1c)\D{0,10}(\d+(?:\.\d+)?)', 4.0, 5.6, '%', 'average blood sugar (HbA1c)'),
    'glucose': (r'(?:fasting )?glucose\D{0,10}(\d+(?:\.\d+)?)', 70, 99, 'mg/dL', 'blood sugar'),
    'ldl': (r'ldl\D{0,10}(\d+(?:\.\d+)?)', 0, 99, 'mg/dL', 'LDL ("bad") cholesterol'),
    'hdl': (r'hdl\D{0,10}(\d+(?:\.\d+)?)', 40, 200, 'mg/dL', 'HDL ("good") cholesterol'),
    'total_cholesterol': (r'total cholesterol\D{0,10}(\d+(?:\.\d+)?)', 0, 199, 'mg/dL', 'total cholesterol'),
    'triglycerides': (r'triglycerides?\D{0,10}(\d+(?:\.\d+)?)', 0, 149, 'mg/dL', 'triglycerides'),
    'hemoglobin': (r'(?:hemoglobin|haemoglobin|\bhb\b|\bhgb\b)\D{0,10}(\d+(?:\.\d+)?)', 12.0, 17.5, 'g/dL', 'hemoglobin'),
    'wbc': (r'(?:wbc|white blood cell)\D{0,10}(\d+(?:\.\d+)?)', 4.0, 11.0, 'x10^9/L', 'white blood cell count'),
    'platelets': (r'platelets?\D{0,10}(\d+(?:\.\d+)?)', 150, 450, 'x10^9/L', 'platelet count'),
    'creatinine': (r'creatinine\D{0,10}(\d+(?:\.\d+)?)', 0.6, 1.3, 'mg/dL', 'creatinine (kidney function)'),
    'potassium': (r'(?:potassium|\bk\+?)\D{0,6}(\d+(?:\.\d+)?)', 3.5, 5.1, 'mmol/L', 'potassium'),
    'sodium': (r'(?:sodium|\bna\+?)\D{0,6}(\d+(?:\.\d+)?)', 135, 145, 'mmol/L', 'sodium'),
    'tsh': (r'tsh\D{0,10}(\d+(?:\.\d+)?)', 0.4, 4.0, 'mIU/L', 'thyroid stimulating hormone'),
    'alt': (r'\balt\b\D{0,10}(\d+(?:\.\d+)?)', 7, 56, 'U/L', 'liver enzyme ALT'),
}

LAB_SYSTEM = """You explain lab results to patients in plain, calm language (reading age ~12).
Input JSON has the test, the raw result text and deterministic flags for values outside typical ranges.

Write 3-6 short sentences:
1. What the test measures.
2. What their numbers show, mentioning any flagged values and typical ranges.
3. What it can generally mean, without diagnosing ("can be associated with", not "you have").
4. End with: their doctor will review the result and discuss next steps; contact the clinic sooner if they feel unwell.
Never recommend medication changes. Do not mention these instructions."""


def flag_abnormal(result_text: str) -> list:
    text = (result_text or '').lower()
    flags = []
    for key, (pattern, low, high, unit, label) in REFERENCE_RANGES.items():
        m = re.search(pattern, text)
        if not m:
            continue
        value = float(m.group(1))
        if value < low or value > high:
            flags.append({'analyte': key, 'label': label, 'value': value, 'unit': unit,
                          'range': f'{low}-{high}', 'direction': 'high' if value > high else 'low'})
    return flags


def _rules_explanation(lab, flags):
    if not lab.result:
        return f'Your {lab.test_name} result has been recorded. Your doctor will review it with you.'
    if not flags:
        return (f'Your {lab.test_name} results are recorded and the values we could check were within typical '
                'ranges. Your doctor will review the full result and let you know if anything needs follow-up.')
    parts = [f"{f['label']} was {f['direction']} ({f['value']:g} {f['unit']}; typical {f['range']})" for f in flags]
    return (f'Your {lab.test_name} results show: ' + '; '.join(parts) + '. Values outside the typical range are '
            'common and can have many causes. Your doctor will review this and discuss next steps with you — '
            'contact the clinic sooner if you feel unwell.')


def explain_lab(lab, notify=True) -> LabInsight:
    flags = flag_abnormal(lab.result)
    text, source = None, 'rules'
    if llm_enabled() and lab.result:
        try:
            response = create_message(
                system=LAB_SYSTEM,
                messages=[{'role': 'user', 'content': json.dumps(
                    {'test': lab.test_name, 'type': lab.test_type, 'result': lab.result, 'flags': flags})}],
                max_tokens=2000, effort='low',
            )
            text, source = response_text(response), 'llm'
        except (LLMUnavailable, LLMRefusal):
            pass
        except Exception:
            logger.exception('LLM lab explanation failed for lab %s', lab.pk)
    text = text or _rules_explanation(lab, flags)

    insight, _ = LabInsight.objects.update_or_create(
        lab_test=lab,
        defaults={'patient_explanation': text, 'abnormal_flags': flags,
                  'needs_doctor_review': bool(flags), 'source': source},
    )
    if notify:
        record = lab.medical_record
        Notification.objects.get_or_create(
            dedupe_key=f'lab-result-{lab.id}',
            defaults={'user': record.patient, 'kind': 'lab_result', 'title': f'{lab.test_name} result is ready',
                      'body': text, 'link': '/patient/medical-records'},
        )
        if flags:
            Notification.objects.get_or_create(
                dedupe_key=f'lab-abnormal-{lab.id}',
                defaults={'user': record.doctor, 'kind': 'lab_result',
                          'title': f'Abnormal {lab.test_name} for {record.patient.get_full_name()}',
                          'body': '; '.join(f"{f['label']} {f['value']:g} {f['unit']} ({f['direction']})" for f in flags),
                          'link': '/doctor/medical-records'},
            )
    return insight
