from django.test import TestCase

from ai_agents.models import SafetyAlert
from ai_agents.safety import check_prescription, normalize_drugs, parse_dose_mg, parse_times_per_day

from .factories import make_doctor, make_patient, make_record, make_rx


def cats(findings):
    return {(f.severity, f.category) for f in findings}


class SafetyEngineTests(TestCase):
    def setUp(self):
        self.doctor = make_doctor()

    def test_penicillin_allergy_blocks_amoxicillin(self):
        p = make_patient(allergies='Penicillin')
        f = check_prescription(p, 'Amoxicillin', '500mg', 'three times daily')
        self.assertIn(('critical', 'allergy'), cats(f))
        self.assertEqual(f[0].severity, 'critical')

    def test_brand_name_is_resolved(self):
        p = make_patient(allergies='penicillin (hives)')
        self.assertIn(('critical', 'allergy'), cats(check_prescription(p, 'Augmentin 625')))

    def test_penicillin_allergy_cephalosporin_cross_reactivity_is_warning(self):
        p = make_patient(allergies='Penicillin')
        self.assertIn(('warning', 'allergy'), cats(check_prescription(p, 'Cephalexin', '500mg')))

    def test_no_allergy_false_positive(self):
        p = make_patient(allergies='None')
        self.assertNotIn('allergy', {x.category for x in check_prescription(p, 'Amoxicillin', '500mg')})

    def test_warfarin_plus_nsaid_interaction(self):
        p = make_patient()
        make_rx(make_record(p, self.doctor), 'Warfarin', '5mg', 'once daily')
        self.assertIn(('critical', 'interaction'), cats(check_prescription(p, 'Ibuprofen', '400mg')))

    def test_duplicate_class(self):
        p = make_patient()
        make_rx(make_record(p, self.doctor), 'Lisinopril')
        self.assertIn(('warning', 'duplicate'), cats(check_prescription(p, 'Enalapril', '10mg')))

    def test_condition_contraindication(self):
        p = make_patient(conditions='Chronic kidney disease stage 3, hypertension')
        f = check_prescription(p, 'Naproxen', '500mg', 'twice daily')
        self.assertIn(('critical', 'contraindication'), cats(f))

    def test_dose_ceiling(self):
        p = make_patient()
        self.assertIn(('critical', 'dose'), cats(check_prescription(p, 'Ibuprofen', '1200mg', 'once daily')))
        self.assertIn(('critical', 'dose'), cats(check_prescription(p, 'Ibuprofen', '800mg', 'every 4 hours')))
        self.assertNotIn('dose', {x.category for x in check_prescription(p, 'Ibuprofen', '400mg', 'three times daily')})

    def test_unknown_drug_is_flagged_as_unchecked(self):
        p = make_patient()
        self.assertIn(('info', 'unrecognized'), cats(check_prescription(p, 'Zyxorab')))

    def test_signal_persists_alerts_on_prescription_save(self):
        p = make_patient(allergies='Sulfa')
        rx = make_rx(make_record(p, self.doctor), 'Bactrim DS', '800mg', 'twice daily')
        self.assertTrue(SafetyAlert.objects.filter(prescription=rx, severity='critical', category='allergy').exists())

    def test_parsers(self):
        self.assertEqual(parse_dose_mg('0.5 g'), 500)
        self.assertEqual(parse_dose_mg('250 mcg'), 0.25)
        self.assertEqual(parse_times_per_day('BID'), 2)
        self.assertEqual(parse_times_per_day('every 8 hours'), 3)
        self.assertEqual(parse_times_per_day('3 times a day'), 3)
        self.assertEqual(normalize_drugs('Tylenol + Advil'), {'acetaminophen', 'ibuprofen'})
