"""
Prescription safety engine (clinical decision support).

The *detection* is deterministic and auditable: a curated knowledge base of
drug classes, allergy cross-reactivity, drug–drug interactions, condition
contraindications and dose ceilings. The LLM is only used (optionally) to
explain findings in plain language — it never decides whether something is safe.

This knowledge base is intentionally small and is NOT a substitute for a
licensed drug-interaction database (e.g. First Databank, Medi-Span) or for
clinical judgement. Every alert must be reviewed by the prescriber.
"""
import re
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta

from django.utils import timezone

# ── Knowledge base ──────────────────────────────────────────────────────────

BRAND_NAMES = {
    'augmentin': 'amoxicillin', 'amoxil': 'amoxicillin', 'advil': 'ibuprofen', 'motrin': 'ibuprofen',
    'tylenol': 'acetaminophen', 'paracetamol': 'acetaminophen', 'panadol': 'acetaminophen',
    'coumadin': 'warfarin', 'jantoven': 'warfarin', 'zoloft': 'sertraline', 'prozac': 'fluoxetine',
    'lexapro': 'escitalopram', 'celexa': 'citalopram', 'paxil': 'paroxetine', 'effexor': 'venlafaxine',
    'cymbalta': 'duloxetine', 'lipitor': 'atorvastatin', 'zocor': 'simvastatin', 'crestor': 'rosuvastatin',
    'viagra': 'sildenafil', 'cialis': 'tadalafil', 'bactrim': 'sulfamethoxazole', 'septra': 'sulfamethoxazole',
    'aleve': 'naproxen', 'glucophage': 'metformin', 'ultram': 'tramadol', 'xanax': 'alprazolam',
    'valium': 'diazepam', 'ativan': 'lorazepam', 'klonopin': 'clonazepam', 'eliquis': 'apixaban',
    'xarelto': 'rivaroxaban', 'pradaxa': 'dabigatran', 'cipro': 'ciprofloxacin', 'levaquin': 'levofloxacin',
    'sudafed': 'pseudoephedrine', 'keflex': 'cephalexin', 'zithromax': 'azithromycin', 'zpack': 'azithromycin',
    'biaxin': 'clarithromycin', 'prinivil': 'lisinopril', 'zestril': 'lisinopril', 'cozaar': 'losartan',
    'diovan': 'valsartan', 'aldactone': 'spironolactone', 'lopressor': 'metoprolol', 'toprol': 'metoprolol',
    'tenormin': 'atenolol', 'inderal': 'propranolol', 'deltasone': 'prednisone', 'nitrostat': 'nitroglycerin',
    'celebrex': 'celecoxib', 'voltaren': 'diclofenac', 'toradol': 'ketorolac', 'oxycontin': 'oxycodone',
    'imitrex': 'sumatriptan', 'nardil': 'phenelzine', 'parnate': 'tranylcypromine',
}

DRUG_CLASSES = {
    'penicillin': {'amoxicillin', 'ampicillin', 'penicillin', 'piperacillin', 'dicloxacillin', 'nafcillin', 'oxacillin'},
    'cephalosporin': {'cephalexin', 'cefuroxime', 'ceftriaxone', 'cefdinir', 'cefazolin', 'cefixime', 'cefpodoxime'},
    'sulfonamide_antibiotic': {'sulfamethoxazole', 'sulfadiazine'},
    'macrolide': {'clarithromycin', 'erythromycin', 'azithromycin'},
    'fluoroquinolone': {'ciprofloxacin', 'levofloxacin', 'moxifloxacin'},
    'nsaid': {'ibuprofen', 'naproxen', 'diclofenac', 'aspirin', 'celecoxib', 'ketorolac', 'indomethacin', 'meloxicam'},
    'ace_inhibitor': {'lisinopril', 'enalapril', 'ramipril', 'captopril', 'benazepril', 'perindopril'},
    'arb': {'losartan', 'valsartan', 'irbesartan', 'candesartan', 'telmisartan', 'olmesartan'},
    'potassium_sparing_diuretic': {'spironolactone', 'eplerenone', 'amiloride', 'triamterene'},
    'potassium_supplement': {'potassium'},
    'anticoagulant': {'warfarin', 'apixaban', 'rivaroxaban', 'dabigatran', 'heparin', 'enoxaparin'},
    'ssri': {'fluoxetine', 'sertraline', 'citalopram', 'escitalopram', 'paroxetine'},
    'snri': {'venlafaxine', 'duloxetine'},
    'maoi': {'phenelzine', 'tranylcypromine', 'selegiline', 'isocarboxazid'},
    'triptan': {'sumatriptan', 'rizatriptan', 'zolmitriptan'},
    'opioid': {'tramadol', 'oxycodone', 'morphine', 'hydrocodone', 'codeine', 'fentanyl', 'methadone'},
    'benzodiazepine': {'diazepam', 'lorazepam', 'alprazolam', 'clonazepam'},
    'statin': {'simvastatin', 'atorvastatin', 'lovastatin', 'rosuvastatin', 'pravastatin'},
    'nitrate': {'nitroglycerin', 'isosorbide'},
    'pde5_inhibitor': {'sildenafil', 'tadalafil', 'vardenafil'},
    'beta_blocker': {'metoprolol', 'atenolol', 'bisoprolol', 'propranolol', 'nadolol', 'carvedilol', 'timolol'},
    'nonselective_beta_blocker': {'propranolol', 'nadolol', 'carvedilol', 'timolol'},
    'decongestant': {'pseudoephedrine', 'phenylephrine'},
    'biguanide': {'metformin'},
    'corticosteroid': {'prednisone', 'prednisolone', 'dexamethasone', 'methylprednisolone', 'hydrocortisone'},
    'analgesic': {'acetaminophen'},
}

ALL_DRUGS = set().union(*DRUG_CLASSES.values()) | set(BRAND_NAMES.values())

# allergy keyword -> [(class, severity, message)]
ALLERGY_RULES = {
    'penicillin': [
        ('penicillin', 'critical', 'Patient has a documented penicillin allergy; {drug} is a penicillin.'),
        ('cephalosporin', 'warning', 'Penicillin allergy: low but real cross-reactivity with cephalosporins such as {drug}.'),
    ],
    'amoxicillin': [('penicillin', 'critical', 'Documented amoxicillin allergy; {drug} is in the same penicillin class.')],
    'cephalosporin': [('cephalosporin', 'critical', 'Documented cephalosporin allergy; {drug} is a cephalosporin.')],
    'sulfa': [('sulfonamide_antibiotic', 'critical', 'Documented sulfa allergy; {drug} is a sulfonamide antibiotic.')],
    'sulfonamide': [('sulfonamide_antibiotic', 'critical', 'Documented sulfonamide allergy; {drug} is a sulfonamide.')],
    'nsaid': [('nsaid', 'critical', 'Documented NSAID allergy; {drug} is an NSAID.')],
    'aspirin': [('nsaid', 'critical', 'Documented aspirin allergy; NSAIDs such as {drug} commonly cross-react.')],
    'ibuprofen': [('nsaid', 'critical', 'Documented ibuprofen allergy; {drug} is an NSAID and may cross-react.')],
    'codeine': [('opioid', 'warning', 'Documented codeine allergy/intolerance; use caution with opioid {drug}.')],
    'macrolide': [('macrolide', 'critical', 'Documented macrolide allergy; {drug} is a macrolide.')],
    'quinolone': [('fluoroquinolone', 'critical', 'Documented quinolone allergy; {drug} is a fluoroquinolone.')],
    'statin': [('statin', 'critical', 'Documented statin intolerance; {drug} is a statin.')],
}

# (class_or_drug_a, class_or_drug_b, severity, message)
INTERACTIONS = [
    ('anticoagulant', 'nsaid', 'critical', 'Anticoagulant + NSAID markedly increases bleeding risk.'),
    ('maoi', 'ssri', 'critical', 'MAOI + SSRI can cause serotonin syndrome (contraindicated).'),
    ('maoi', 'snri', 'critical', 'MAOI + SNRI can cause serotonin syndrome (contraindicated).'),
    ('maoi', 'opioid', 'critical', 'MAOI + opioid (esp. tramadol/meperidine) risks serotonin syndrome / hypertensive crisis.'),
    ('maoi', 'decongestant', 'critical', 'MAOI + sympathomimetic decongestant risks hypertensive crisis.'),
    ('opioid', 'benzodiazepine', 'critical', 'Opioid + benzodiazepine: risk of profound sedation and respiratory depression.'),
    ('nitrate', 'pde5_inhibitor', 'critical', 'Nitrate + PDE5 inhibitor can cause severe hypotension (contraindicated).'),
    ('simvastatin', 'clarithromycin', 'critical', 'Simvastatin + clarithromycin: high risk of myopathy/rhabdomyolysis (contraindicated).'),
    ('simvastatin', 'erythromycin', 'critical', 'Simvastatin + erythromycin: high risk of myopathy/rhabdomyolysis.'),
    ('lovastatin', 'clarithromycin', 'critical', 'Lovastatin + clarithromycin: high risk of rhabdomyolysis.'),
    ('tramadol', 'ssri', 'warning', 'Tramadol + SSRI: serotonin syndrome and seizure risk.'),
    ('tramadol', 'snri', 'warning', 'Tramadol + SNRI: serotonin syndrome and seizure risk.'),
    ('triptan', 'ssri', 'warning', 'Triptan + SSRI: monitor for serotonin syndrome.'),
    ('ace_inhibitor', 'potassium_sparing_diuretic', 'warning', 'ACE inhibitor + potassium-sparing diuretic: hyperkalemia risk — monitor K+.'),
    ('arb', 'potassium_sparing_diuretic', 'warning', 'ARB + potassium-sparing diuretic: hyperkalemia risk — monitor K+.'),
    ('ace_inhibitor', 'potassium_supplement', 'warning', 'ACE inhibitor + potassium supplement: hyperkalemia risk.'),
    ('ace_inhibitor', 'arb', 'warning', 'Dual RAAS blockade (ACE inhibitor + ARB) increases hyperkalemia and AKI risk.'),
    ('ace_inhibitor', 'nsaid', 'warning', 'ACE inhibitor + NSAID: reduced antihypertensive effect and kidney injury risk.'),
    ('arb', 'nsaid', 'warning', 'ARB + NSAID: reduced antihypertensive effect and kidney injury risk.'),
    ('warfarin', 'macrolide', 'warning', 'Warfarin + macrolide antibiotic may raise INR — monitor closely.'),
    ('warfarin', 'fluoroquinolone', 'warning', 'Warfarin + fluoroquinolone may raise INR — monitor closely.'),
    ('warfarin', 'sulfonamide_antibiotic', 'critical', 'Warfarin + sulfamethoxazole markedly raises INR and bleeding risk.'),
    ('nsaid', 'corticosteroid', 'warning', 'NSAID + corticosteroid increases GI bleeding risk; consider gastroprotection.'),
    ('fluoroquinolone', 'corticosteroid', 'warning', 'Fluoroquinolone + corticosteroid increases tendon rupture risk.'),
    ('ssri', 'nsaid', 'info', 'SSRI + NSAID modestly increases GI bleeding risk.'),
    ('ssri', 'anticoagulant', 'warning', 'SSRI + anticoagulant increases bleeding risk.'),
]

# condition keyword -> [(class_or_drug, severity, message)]
CONDITION_RULES = {
    'hypertension': [
        ('nsaid', 'warning', 'NSAIDs can raise blood pressure in patients with hypertension.'),
        ('decongestant', 'warning', 'Decongestants can raise blood pressure in patients with hypertension.'),
    ],
    'kidney': [
        ('nsaid', 'critical', 'NSAIDs can worsen kidney function in chronic kidney disease.'),
        ('biguanide', 'warning', 'Metformin requires eGFR-based dosing in kidney disease; check renal function.'),
    ],
    'renal': [
        ('nsaid', 'critical', 'NSAIDs can worsen renal impairment.'),
        ('biguanide', 'warning', 'Metformin requires eGFR-based dosing in renal impairment.'),
    ],
    'ckd': [('nsaid', 'critical', 'NSAIDs can worsen chronic kidney disease.')],
    'asthma': [
        ('nonselective_beta_blocker', 'critical', 'Non-selective beta-blockers can trigger bronchospasm in asthma.'),
        ('aspirin', 'warning', 'Aspirin can trigger bronchospasm in aspirin-sensitive asthma.'),
    ],
    'copd': [('nonselective_beta_blocker', 'warning', 'Non-selective beta-blockers may worsen COPD.')],
    'ulcer': [('nsaid', 'critical', 'NSAIDs are high-risk with a history of peptic ulcer disease.')],
    'gi bleed': [('nsaid', 'critical', 'NSAIDs are high-risk with a history of GI bleeding.')],
    'heart failure': [
        ('nsaid', 'warning', 'NSAIDs cause fluid retention and can worsen heart failure.'),
    ],
    'pregnan': [
        ('ace_inhibitor', 'critical', 'ACE inhibitors are contraindicated in pregnancy (fetotoxic).'),
        ('arb', 'critical', 'ARBs are contraindicated in pregnancy (fetotoxic).'),
        ('statin', 'critical', 'Statins are generally contraindicated in pregnancy.'),
        ('warfarin', 'critical', 'Warfarin is teratogenic and generally contraindicated in pregnancy.'),
        ('fluoroquinolone', 'warning', 'Fluoroquinolones are generally avoided in pregnancy.'),
    ],
    'liver': [
        ('statin', 'warning', 'Use statins cautiously in active liver disease; check LFTs.'),
        ('acetaminophen', 'warning', 'Limit acetaminophen dose in liver disease.'),
    ],
    'diabetes': [('corticosteroid', 'info', 'Corticosteroids can raise blood glucose; monitor in diabetes.')],
    'bleeding disorder': [
        ('anticoagulant', 'critical', 'Anticoagulants in a patient with a bleeding disorder need specialist review.'),
        ('nsaid', 'warning', 'NSAIDs impair platelet function in bleeding disorders.'),
    ],
}

# drug -> (max single dose mg, max daily dose mg)
DOSE_LIMITS = {
    'ibuprofen': (800, 3200), 'naproxen': (500, 1500), 'acetaminophen': (1000, 4000),
    'aspirin': (1000, 4000), 'diclofenac': (75, 150), 'ketorolac': (30, 120), 'celecoxib': (400, 400),
    'amoxicillin': (1000, 3000), 'cephalexin': (1000, 4000), 'azithromycin': (500, 500),
    'clarithromycin': (500, 1000), 'ciprofloxacin': (750, 1500), 'levofloxacin': (750, 750),
    'lisinopril': (80, 80), 'losartan': (100, 100), 'metoprolol': (200, 400), 'atenolol': (100, 100),
    'metformin': (1000, 2550), 'atorvastatin': (80, 80), 'simvastatin': (40, 40), 'rosuvastatin': (40, 40),
    'sertraline': (200, 200), 'fluoxetine': (80, 80), 'escitalopram': (20, 20), 'citalopram': (40, 40),
    'warfarin': (10, 10), 'prednisone': (80, 80), 'tramadol': (100, 400), 'alprazolam': (2, 4),
    'diazepam': (10, 40), 'sildenafil': (100, 100), 'spironolactone': (100, 200),
}

SEVERITY_RANK = {'critical': 3, 'warning': 2, 'info': 1}

# ── Parsing helpers ─────────────────────────────────────────────────────────


def normalize_drugs(text: str) -> set:
    """Find known generic drug names in free text (handles brand names and combos)."""
    tokens = re.findall(r'[a-z]+', (text or '').lower())
    found = set()
    for tok in tokens:
        if tok in BRAND_NAMES:
            found.add(BRAND_NAMES[tok])
        elif tok in ALL_DRUGS:
            found.add(tok)
    return found


def drug_classes(drug: str) -> set:
    return {cls for cls, members in DRUG_CLASSES.items() if drug in members}


def _matches(term: str, drugs: set) -> set:
    """Drugs in `drugs` that match a class name or a specific drug name."""
    if term in DRUG_CLASSES:
        return {d for d in drugs if d in DRUG_CLASSES[term]}
    return {d for d in drugs if d == term}


def parse_dose_mg(dosage: str):
    if not dosage:
        return None
    m = re.search(r'(\d+(?:\.\d+)?)\s*(mg|g|mcg|µg)\b', dosage.lower())
    if not m:
        return None
    value, unit = float(m.group(1)), m.group(2)
    return value * 1000 if unit == 'g' else value / 1000 if unit in ('mcg', 'µg') else value


def parse_times_per_day(frequency: str):
    f = (frequency or '').lower()
    if not f:
        return None
    m = re.search(r'every\s+(\d+)\s*(?:h|hr|hrs|hour|hours)\b', f)
    if m and int(m.group(1)) > 0:
        return max(1, round(24 / int(m.group(1))))
    m = re.search(r'(\d+)\s*(?:x|times)\s*(?:a|per|/)?\s*day|(\d+)\s*times\s*daily', f)
    if m:
        return int(m.group(1) or m.group(2))
    words = [('four times', 4), ('qid', 4), ('three times', 3), ('tid', 3), ('thrice', 3),
             ('twice', 2), ('bid', 2), ('two times', 2), ('once', 1), ('daily', 1), ('qd', 1),
             ('at bedtime', 1), ('nightly', 1), ('every morning', 1)]
    for word, n in words:
        if re.search(rf'\b{word}\b', f):
            return n
    return None


def _age(dob):
    if not dob:
        return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


# ── Engine ──────────────────────────────────────────────────────────────────

@dataclass
class Finding:
    severity: str
    category: str
    message: str
    evidence: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


def active_medications(patient, exclude_prescription_id=None, lookback_days=90):
    """Prescriptions in the recent past, treated as currently active."""
    from medical_records.models import Prescription
    since = timezone.now() - timedelta(days=lookback_days)
    qs = Prescription.objects.filter(medical_record__patient=patient, created_at__gte=since)
    if exclude_prescription_id:
        qs = qs.exclude(pk=exclude_prescription_id)
    return list(qs.order_by('-created_at'))


def check_prescription(patient, medication_name, dosage='', frequency='', exclude_prescription_id=None):
    """Return a list of Finding for a proposed / newly created prescription."""
    findings = []
    new_drugs = normalize_drugs(medication_name)
    profile = getattr(patient, 'patient_profile', None)
    allergies = (getattr(profile, 'allergies', '') or '').lower()
    conditions = (getattr(profile, 'chronic_conditions', '') or '').lower()

    if not new_drugs:
        findings.append(Finding(
            'info', 'unrecognized',
            f'"{medication_name}" is not in the built-in safety knowledge base; '
            'allergy and interaction checks were limited. Verify manually.',
        ))

    # 1. Allergies (class-level + direct drug name mentions)
    if allergies and allergies.strip() not in ('none', 'nka', 'nkda', 'no known allergies'):
        for keyword, rules in ALLERGY_RULES.items():
            if keyword in allergies:
                for cls, severity, msg in rules:
                    for drug in _matches(cls, new_drugs):
                        findings.append(Finding(severity, 'allergy', msg.format(drug=drug),
                                                {'allergy': keyword, 'drug': drug}))
        for drug in new_drugs:
            if re.search(rf'\b{drug}\b', allergies) and not any(f.category == 'allergy' and f.evidence.get('drug') == drug for f in findings):
                findings.append(Finding('critical', 'allergy', f'Patient allergy list explicitly mentions {drug}.',
                                        {'allergy': drug, 'drug': drug}))

    # 2. Interactions + duplicate therapy against active medications
    current = active_medications(patient, exclude_prescription_id)
    for rx in current:
        for other in normalize_drugs(rx.medication_name):
            for drug in new_drugs:
                if drug == other:
                    findings.append(Finding('warning', 'duplicate',
                                            f'{drug} is already prescribed ({rx.dosage}, {rx.frequency}).',
                                            {'drug': drug, 'existing_prescription': rx.id}))
                    continue
                shared = (drug_classes(drug) & drug_classes(other)) - {'nonselective_beta_blocker'}
                if shared:
                    findings.append(Finding('warning', 'duplicate',
                                            f'Therapeutic duplication: {drug} and current {other} are both {sorted(shared)[0].replace("_", " ")}s.',
                                            {'drug': drug, 'other': other, 'existing_prescription': rx.id}))
                for a, b, severity, msg in INTERACTIONS:
                    if (_matches(a, {drug}) and _matches(b, {other})) or (_matches(b, {drug}) and _matches(a, {other})):
                        findings.append(Finding(severity, 'interaction', f'{drug} + {other}: {msg}',
                                                {'drug': drug, 'other': other, 'existing_prescription': rx.id}))

    # 3. Condition contraindications
    for keyword, rules in CONDITION_RULES.items():
        if keyword in conditions:
            for term, severity, msg in rules:
                for drug in _matches(term, new_drugs):
                    findings.append(Finding(severity, 'contraindication', f'{drug}: {msg}',
                                            {'condition': keyword, 'drug': drug}))

    # 4. Age-specific cautions
    age = _age(getattr(patient, 'date_of_birth', None))
    if age is not None:
        if age < 16 and 'aspirin' in new_drugs:
            findings.append(Finding('critical', 'contraindication', 'Aspirin in patients under 16 risks Reye syndrome.',
                                    {'age': age}))
        if age < 18 and _matches('fluoroquinolone', new_drugs):
            findings.append(Finding('warning', 'contraindication', 'Fluoroquinolones are generally avoided under 18.',
                                    {'age': age}))
        if age >= 65 and _matches('benzodiazepine', new_drugs):
            findings.append(Finding('warning', 'contraindication',
                                    'Benzodiazepines in adults ≥65 increase falls/delirium risk (Beers criteria).',
                                    {'age': age}))

    # 5. Dose ceilings
    dose = parse_dose_mg(dosage)
    per_day = parse_times_per_day(frequency)
    for drug in new_drugs:
        limits = DOSE_LIMITS.get(drug)
        if not limits or dose is None:
            continue
        max_single, max_daily = limits
        if dose > max_single:
            findings.append(Finding('critical', 'dose', f'{drug} {dose:g} mg exceeds the usual maximum single dose of {max_single} mg.',
                                    {'drug': drug, 'dose_mg': dose, 'max_single_mg': max_single}))
        if per_day and dose * per_day > max_daily:
            findings.append(Finding('critical', 'dose',
                                    f'{drug} {dose:g} mg × {per_day}/day = {dose * per_day:g} mg/day exceeds the usual maximum of {max_daily} mg/day.',
                                    {'drug': drug, 'daily_mg': dose * per_day, 'max_daily_mg': max_daily}))

    # De-duplicate identical messages and sort most severe first
    unique = {}
    for f in findings:
        unique.setdefault((f.category, f.message), f)
    return sorted(unique.values(), key=lambda f: -SEVERITY_RANK[f.severity])


def record_alerts(prescription):
    """Run the engine for a saved Prescription and persist SafetyAlert rows."""
    from .models import SafetyAlert
    patient = prescription.medical_record.patient
    findings = check_prescription(
        patient, prescription.medication_name, prescription.dosage, prescription.frequency,
        exclude_prescription_id=prescription.pk,
    )
    prescription.safety_alerts.all().delete()
    alerts = [
        SafetyAlert(prescription=prescription, severity=f.severity, category=f.category,
                    message=f.message, evidence=f.evidence)
        for f in findings
    ]
    SafetyAlert.objects.bulk_create(alerts)
    return alerts
