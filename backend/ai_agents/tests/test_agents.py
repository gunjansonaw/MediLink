import os
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from ai_agents import llm
from ai_agents.agent import run_chat
from ai_agents.claims import precheck_claim
from ai_agents.labs import flag_abnormal
from ai_agents.models import AgentToolCall, Notification, PendingAction
from ai_agents.proactive import run_collections
from ai_agents.tools import ToolContext, execute_tool
from appointments.models import Appointment
from billing.models import Invoice, InvoiceItem, InsuranceClaim

from .factories import (FakeClient, make_admin, make_appt, make_doctor, make_patient, make_record, text,
                        tool_use)

NO_KEY = mock.patch.dict(os.environ, {'ANTHROPIC_API_KEY': '', 'ANTHROPIC_AUTH_TOKEN': ''})
WITH_KEY = mock.patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'sk-test'})


class AgentLoopTests(TestCase):
    def setUp(self):
        self.doctor = make_doctor()
        self.patient = make_patient()

    def tearDown(self):
        llm.reset_client()

    @WITH_KEY
    def test_booking_flow_creates_pending_action_then_books_on_approval(self):
        day = (timezone.localdate() + timedelta(days=2)).isoformat()
        fake = FakeClient([
            ('tool_use', [text('Let me find a cardiologist.'),
                          tool_use('t1', 'search_doctors', {'specialization': 'Cardiology'})]),
            ('tool_use', [tool_use('t2', 'get_available_slots', {'doctor_id': self.doctor.id, 'start_date': day})]),
            ('tool_use', [tool_use('t3', 'propose_appointment', {
                'doctor_id': self.doctor.id, 'date': day, 'time': '10:00', 'reason': 'Palpitations'})]),
            ('end_turn', [text('I have prepared the booking — please click Approve.')]),
        ])
        llm.set_client(fake)

        result = run_chat(self.patient, 'Book me a cardiologist in two days at 10am, I have palpitations')
        self.assertEqual(result['mode'], 'llm')
        self.assertIn('Approve', result['reply'])
        self.assertEqual(len(result['pending_actions']), 1)
        self.assertEqual(Appointment.objects.count(), 0, 'agent must not book without approval')

        # Request shape: model, effort, refusal fallback, tools filtered by role
        first = fake.requests[0]
        self.assertEqual(first['model'], 'claude-opus-5-5')
        self.assertEqual(first['fallbacks'], 'default')
        tool_names = {t['name'] for t in first['tools']}
        self.assertIn('propose_appointment', tool_names)
        self.assertNotIn('revenue_analytics', tool_names)
        # Tool results are sent back as a single user turn, matched by id
        last = fake.requests[-1]['messages'][-1]
        self.assertEqual(last['content'][0]['tool_use_id'], 't3')

        # Approve through the API
        client = APIClient()
        client.force_authenticate(self.patient)
        action_id = result['pending_actions'][0]['id']
        resp = client.post(f'/api/ai/pending-actions/{action_id}/approve/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['status'], 'approved')
        self.assertTrue(Appointment.objects.filter(patient=self.patient, doctor=self.doctor).exists())
        self.assertEqual(AgentToolCall.objects.filter(conversation_id=result['conversation_id']).count(), 3)

    @WITH_KEY
    def test_conversation_history_is_replayed(self):
        fake = FakeClient([('end_turn', [text('Hi!')]), ('end_turn', [text('Sure.')])])
        llm.set_client(fake)
        r1 = run_chat(self.patient, 'hello')
        from ai_agents.models import AgentConversation
        conv = AgentConversation.objects.get(pk=r1['conversation_id'])
        run_chat(self.patient, 'thanks', conv)
        msgs = fake.requests[1]['messages']
        self.assertEqual([m['role'] for m in msgs], ['user', 'assistant', 'user'])

    def test_emergency_guardrail_never_calls_model(self):
        with WITH_KEY:
            llm.set_client(FakeClient([]))  # would raise IndexError if called
            r = run_chat(self.patient, 'I have crushing chest pain and my left arm is numb')
        self.assertEqual(r['mode'], 'guardrail')
        self.assertIn('emergency', r['reply'].lower())

    @NO_KEY
    def test_rules_mode_without_api_key(self):
        r = run_chat(self.patient, 'I need to book an appointment, my heart races')
        self.assertEqual(r['mode'], 'rules')
        self.assertIn('Cardiology', r['reply'])

    def test_other_users_approval_is_rejected(self):
        other = make_patient(username='other')
        action = PendingAction.objects.create(requested_by=self.patient, action_type='cancel_appointment',
                                              payload={'appointment_id': 1}, summary='x')
        client = APIClient()
        client.force_authenticate(other)
        self.assertEqual(client.post(f'/api/ai/pending-actions/{action.id}/approve/').status_code, 404)


class ToolRBACTests(TestCase):
    def setUp(self):
        self.doctor = make_doctor()
        self.patient = make_patient()

    def test_patient_cannot_use_admin_tools(self):
        out, err = execute_tool(ToolContext(self.patient), 'revenue_analytics', {'group_by': 'month'})
        self.assertTrue(err)
        self.assertEqual(AgentToolCall.objects.get().status, 'denied')

    def test_doctor_without_care_relationship_is_denied(self):
        out, err = execute_tool(ToolContext(self.doctor), 'get_patient_context', {'patient_id': self.patient.id})
        self.assertTrue(err)
        make_appt(self.patient, self.doctor)
        out, err = execute_tool(ToolContext(self.doctor), 'get_patient_context', {'patient_id': self.patient.id})
        self.assertFalse(err)
        self.assertEqual(out['patient_id'], self.patient.id)

    def test_propose_rejects_taken_slot(self):
        appt = make_appt(make_patient(username='p2'), self.doctor, days_ahead=2)
        out, err = execute_tool(ToolContext(self.patient), 'propose_appointment', {
            'doctor_id': self.doctor.id, 'date': appt.appointment_date.isoformat(), 'time': '10:00', 'reason': 'x'})
        self.assertTrue(err)
        self.assertIn('not available', out['error'])

    def test_admin_analytics(self):
        admin = make_admin()
        make_appt(self.patient, self.doctor, days_ahead=-1, status='no_show')
        out, err = execute_tool(ToolContext(admin), 'no_show_report', {})
        self.assertFalse(err)
        self.assertEqual(out['overall_rate_pct'], 100.0)


class ProactiveAgentTests(TestCase):
    def setUp(self):
        self.doctor = make_doctor()
        self.patient = make_patient()

    def _overdue_invoice(self, days):
        inv = Invoice.objects.create(patient=self.patient, due_date=timezone.localdate() - timedelta(days=days),
                                     subtotal=Decimal('100'), total=Decimal('100'))
        return inv

    def test_collections_stages_and_idempotency(self):
        make_admin()
        self._overdue_invoice(5)
        self._overdue_invoice(30)
        self._overdue_invoice(60)
        self.assertEqual(run_collections(), {'reminder': 1, 'payment_plan': 1, 'escalate': 1})
        self.assertEqual(run_collections(), {'reminder': 0, 'payment_plan': 0, 'escalate': 0})
        self.assertEqual(Notification.objects.filter(kind='payment_reminder').count(), 3)

    def test_lab_flags(self):
        flags = flag_abnormal('Total cholesterol 228 mg/dL, LDL 162 mg/dL, HDL 41 mg/dL')
        self.assertEqual({f['analyte'] for f in flags}, {'ldl', 'total_cholesterol'})

    @NO_KEY
    def test_claim_precheck_finds_problems(self):
        appt = make_appt(self.patient, self.doctor, days_ahead=1)  # not completed
        inv = Invoice.objects.create(patient=self.patient, appointment=appt, due_date=timezone.localdate(),
                                     subtotal=Decimal('100'), total=Decimal('100'))
        claim = InsuranceClaim.objects.create(patient=self.patient, invoice=inv, insurance_provider='Aetna',
                                              insurance_policy_number='WRONG', claim_amount=Decimal('90'))
        codes = {i['code'] for i in precheck_claim(claim)['issues']}
        self.assertTrue({'policy_mismatch', 'encounter_not_completed', 'no_diagnosis', 'no_line_items'} <= codes)

    @NO_KEY
    def test_brief_endpoint_highlights_allergy(self):
        patient = make_patient(username='p3', allergies='Penicillin')
        appt = make_appt(patient, self.doctor)
        client = APIClient()
        client.force_authenticate(self.doctor)
        resp = client.get(f'/api/ai/briefs/{appt.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['source'], 'rules')
        self.assertTrue(any('Penicillin' in h['text'] for h in resp.data['highlights']))
        other = make_doctor(username='doc2')
        client.force_authenticate(other)
        self.assertEqual(client.get(f'/api/ai/briefs/{appt.id}/').status_code, 403)
