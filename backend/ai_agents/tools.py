"""
Tool registry for MediLink agents.

Design rules
------------
* Every tool declares which roles may use it; the agent for a user only *sees*
  that user's tools, and `execute_tool` re-checks the role before running.
* Data access goes through the same scoping as the REST API (context.py), so a
  tool can never reveal more than the user could see in the UI.
* Tools that change state never write directly. They create a PendingAction the
  human approves in the UI (human-in-the-loop) — see actions.py.
* Every call is written to the AgentToolCall audit log.
"""
import json
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import ExtractWeekDay, TruncDay, TruncMonth
from django.utils import timezone
from django.utils.dateparse import parse_date

from appointments.models import Appointment
from appointments.services import available_slots
from billing.models import Invoice, InsuranceClaim, Payment
from users.models import User

from .context import AccessDenied, get_patient_for, patient_context, visible_patients
from .guardrails import redact, truncate
from .models import AgentToolCall, PendingAction


class ToolError(Exception):
    """A recoverable error reported back to the model as an is_error tool_result."""


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    roles: tuple
    handler: callable
    writes: bool = False
    ui: bool = False  # surface the raw result to the frontend (cards / charts)

    def api_schema(self):
        return {'name': self.name, 'description': self.description, 'input_schema': self.input_schema}


@dataclass
class ToolContext:
    user: User
    conversation: object = None
    agent: str = 'assistant'


REGISTRY: dict[str, Tool] = {}


def tool(name, description, properties, required=(), roles=('patient', 'doctor', 'admin'), writes=False, ui=False):
    def decorator(fn):
        REGISTRY[name] = Tool(
            name=name,
            description=description,
            input_schema={'type': 'object', 'properties': properties, 'required': list(required),
                          'additionalProperties': False},
            roles=tuple(roles),
            handler=fn,
            writes=writes,
            ui=ui,
        )
        return fn
    return decorator


def tools_for(user):
    return [t for t in REGISTRY.values() if user.role in t.roles]


def execute_tool(ctx: ToolContext, name: str, tool_input: dict):
    """Run a tool with RBAC + audit. Returns (result_dict, is_error)."""
    started = time.monotonic()
    t = REGISTRY.get(name)
    status = 'ok'
    if t is None:
        result, is_error, status = {'error': f'Unknown tool {name}'}, True, 'error'
    elif ctx.user.role not in t.roles:
        result, is_error, status = {'error': 'This tool is not available for your role.'}, True, 'denied'
    else:
        try:
            result = t.handler(ctx, **(tool_input or {}))
            is_error = False
            if t.writes:
                status = 'proposed'
        except (ToolError, AccessDenied) as exc:
            result, is_error = {'error': str(exc)}, True
            status = 'denied' if isinstance(exc, AccessDenied) else 'error'
        except TypeError as exc:  # wrong / missing arguments from the model
            result, is_error, status = {'error': f'Invalid arguments: {exc}'}, True, 'error'

    AgentToolCall.objects.create(
        conversation=ctx.conversation if getattr(ctx.conversation, 'pk', None) else None,
        user=ctx.user,
        agent=ctx.agent,
        tool_name=name,
        tool_input=tool_input or {},
        result_summary=truncate(redact(json.dumps(result, default=str)), 1000),
        status=status,
        duration_ms=int((time.monotonic() - started) * 1000),
    )
    return result, is_error


# ── helpers ────────────────────────────────────────────────────────────────

def _date(value, field, default=None):
    if value in (None, ''):
        if default is not None:
            return default
        raise ToolError(f'{field} is required (YYYY-MM-DD).')
    d = parse_date(str(value))
    if d is None:
        raise ToolError(f'{field} must be a date in YYYY-MM-DD format.')
    return d


def _time(value):
    try:
        return datetime.strptime(str(value)[:5], '%H:%M').time()
    except ValueError:
        raise ToolError('time must be HH:MM (24h).')


def _range(start_date, end_date, default_days=30):
    end = _date(end_date, 'end_date', timezone.localdate())
    start = _date(start_date, 'start_date', end - timedelta(days=default_days))
    if start > end:
        raise ToolError('start_date must be on or before end_date.')
    if (end - start).days > 731:
        raise ToolError('Please use a date range of at most two years.')
    return start, end


def _doctor_card(u):
    p = getattr(u, 'doctor_profile', None)
    return {
        'doctor_id': u.id, 'name': f'Dr. {u.get_full_name()}',
        'specialization': getattr(p, 'specialization', None),
        'experience_years': getattr(p, 'experience_years', None),
        'consultation_fee': float(p.consultation_fee) if p else None,
        'available_days': getattr(p, 'available_days', None),
    }


def _appointment_card(a):
    return {
        'appointment_id': a.id, 'date': a.appointment_date.isoformat(),
        'time': a.appointment_time.strftime('%H:%M'), 'status': a.status, 'reason': a.reason,
        'doctor': f'Dr. {a.doctor.get_full_name()}', 'doctor_id': a.doctor_id,
        'patient': a.patient.get_full_name(), 'patient_id': a.patient_id,
    }


def _scoped_appointments(user):
    qs = Appointment.objects.select_related('doctor', 'patient', 'doctor__doctor_profile')
    if user.role == 'admin':
        return qs
    if user.role == 'doctor':
        return qs.filter(doctor=user)
    return qs.filter(patient=user)


def _propose(ctx, action_type, payload, summary, approver_role='self'):
    action = PendingAction.objects.create(
        conversation=ctx.conversation if getattr(ctx.conversation, 'pk', None) else None,
        requested_by=ctx.user,
        approver_role=approver_role,
        action_type=action_type,
        payload=payload,
        summary=summary,
    )
    who = 'the user' if approver_role == 'self' else 'an administrator'
    return {
        'status': 'awaiting_approval',
        'pending_action_id': action.id,
        'summary': summary,
        'note': f'Nothing has been changed yet. {who.capitalize()} must click Approve on this action card.',
    }


# ── Scheduling tools (all roles) ───────────────────────────────────────────

SPECIALTY_KEYWORDS = {
    'Cardiology': ['heart', 'chest', 'palpitation', 'blood pressure', 'hypertension', 'cholesterol', 'ecg'],
    'Pediatrics': ['child', 'baby', 'kid', 'infant', 'toddler', 'son', 'daughter', 'vaccination'],
    'Dermatology': ['skin', 'rash', 'acne', 'eczema', 'mole', 'itch', 'hair loss'],
    'Neurology': ['headache', 'migraine', 'seizure', 'numbness', 'dizziness', 'memory', 'tingling'],
    'Orthopedics': ['bone', 'joint', 'back pain', 'knee', 'fracture', 'shoulder', 'sprain', 'hip'],
    'Psychiatry': ['anxiety', 'depression', 'stress', 'insomnia', 'panic', 'mood', 'sleep'],
}


def infer_specialty(text: str) -> str:
    t = (text or '').lower()
    for spec, words in SPECIALTY_KEYWORDS.items():
        if any(w in t for w in words):
            return spec
    return 'General Medicine'


@tool('search_doctors',
      'Find doctors, optionally filtered by specialization (partial match, e.g. "cardio") or name. '
      'Returns doctor_id, specialization, fee and working days. Use this before checking slots.',
      {'specialization': {'type': 'string'}, 'name': {'type': 'string'}}, ui=True)
def search_doctors(ctx, specialization=None, name=None):
    qs = User.objects.filter(role='doctor', is_active=True).select_related('doctor_profile')
    if specialization:
        first_word = specialization.split()[0][:6]
        qs = qs.filter(doctor_profile__specialization__icontains=first_word)
    if name:
        for part in name.replace('Dr.', '').split():
            qs = qs.filter(Q(first_name__icontains=part) | Q(last_name__icontains=part))
    doctors = [_doctor_card(d) for d in qs[:20]]
    if not doctors and specialization:
        general = User.objects.filter(role='doctor', is_active=True, doctor_profile__specialization__icontains='general')
        return {'doctors': [], 'note': f'No {specialization} specialist found.',
                'general_practitioners': [_doctor_card(d) for d in general[:5]]}
    return {'doctors': doctors}


@tool('get_available_slots',
      'List free 30-minute appointment slots for one doctor between start_date and end_date '
      '(inclusive, max 31 days). Optionally restrict to morning (<12:00), afternoon (12-17) or evening (>=17).',
      {'doctor_id': {'type': 'integer'}, 'start_date': {'type': 'string', 'description': 'YYYY-MM-DD'},
       'end_date': {'type': 'string', 'description': 'YYYY-MM-DD'},
       'time_of_day': {'type': 'string', 'enum': ['any', 'morning', 'afternoon', 'evening']}},
      required=('doctor_id', 'start_date'), ui=True)
def get_available_slots(ctx, doctor_id, start_date, end_date=None, time_of_day='any'):
    try:
        doctor = User.objects.select_related('doctor_profile').get(pk=doctor_id, role='doctor')
    except User.DoesNotExist:
        raise ToolError(f'Doctor {doctor_id} not found.')
    start = _date(start_date, 'start_date')
    end = _date(end_date, 'end_date', start + timedelta(days=6))
    slots = available_slots(doctor, max(start, timezone.localdate()), end)
    bounds = {'morning': ('00:00', '12:00'), 'afternoon': ('12:00', '17:00'), 'evening': ('17:00', '24:00')}
    if time_of_day in bounds:
        lo, hi = bounds[time_of_day]
        slots = [s for s in slots if lo <= s['time'] < hi]
    return {'doctor': _doctor_card(doctor), 'slots': slots[:40], 'total_free_slots': len(slots)}


@tool('list_appointments',
      "List the user's appointments (patients: their own; doctors: their calendar; admins: all). "
      'Use upcoming_only to see future scheduled/confirmed visits.',
      {'upcoming_only': {'type': 'boolean'}, 'status': {'type': 'string',
       'enum': ['scheduled', 'confirmed', 'completed', 'cancelled', 'no_show']},
       'date': {'type': 'string', 'description': 'Only this day, YYYY-MM-DD'}}, ui=True)
def list_appointments(ctx, upcoming_only=False, status=None, date=None):
    qs = _scoped_appointments(ctx.user)
    if upcoming_only:
        qs = qs.filter(appointment_date__gte=timezone.localdate(), status__in=Appointment.ACTIVE_STATUSES)
        qs = qs.order_by('appointment_date', 'appointment_time')
    if status:
        qs = qs.filter(status=status)
    if date:
        qs = qs.filter(appointment_date=_date(date, 'date'))
    return {'appointments': [_appointment_card(a) for a in qs[:25]]}


@tool('propose_appointment',
      'Propose booking an appointment in a free slot. This does NOT book immediately: it creates an '
      'action card the user must approve. Always confirm the slot is free with get_available_slots first. '
      'patient_id is required only for admins booking on behalf of a patient.',
      {'doctor_id': {'type': 'integer'}, 'date': {'type': 'string', 'description': 'YYYY-MM-DD'},
       'time': {'type': 'string', 'description': 'HH:MM 24h'}, 'reason': {'type': 'string'},
       'patient_id': {'type': 'integer'}},
      required=('doctor_id', 'date', 'time', 'reason'), roles=('patient', 'admin'), writes=True)
def propose_appointment(ctx, doctor_id, date, time, reason, patient_id=None):
    try:
        doctor = User.objects.get(pk=doctor_id, role='doctor')
    except User.DoesNotExist:
        raise ToolError(f'Doctor {doctor_id} not found.')
    day, slot_time = _date(date, 'date'), _time(time)
    free = {(s['date'], s['time']) for s in available_slots(doctor, day, day)}
    if (day.isoformat(), slot_time.strftime('%H:%M')) not in free:
        raise ToolError('That slot is not available. Call get_available_slots and pick a listed slot.')
    if ctx.user.role == 'patient':
        patient = ctx.user
    else:
        if not patient_id:
            raise ToolError('patient_id is required when booking on behalf of a patient.')
        patient = get_patient_for(ctx.user, patient_id)
    summary = (f'Book {patient.get_full_name()} with Dr. {doctor.get_full_name()} on '
               f'{day:%a %d %b %Y} at {slot_time:%H:%M} — "{truncate(reason, 120)}"')
    return _propose(ctx, 'book_appointment', {
        'patient_id': patient.id, 'doctor_id': doctor.id, 'date': day.isoformat(),
        'time': slot_time.strftime('%H:%M'), 'reason': reason,
    }, summary)


@tool('propose_cancellation',
      'Propose cancelling one of the user\'s scheduled/confirmed appointments. Creates an action card '
      'the user must approve; nothing is cancelled until then.',
      {'appointment_id': {'type': 'integer'}, 'reason': {'type': 'string'}},
      required=('appointment_id',), writes=True)
def propose_cancellation(ctx, appointment_id, reason=''):
    try:
        appt = _scoped_appointments(ctx.user).get(pk=appointment_id)
    except Appointment.DoesNotExist:
        raise ToolError(f'Appointment {appointment_id} not found.')
    if appt.status not in Appointment.ACTIVE_STATUSES:
        raise ToolError(f'Appointment is already {appt.status}.')
    summary = (f'Cancel appointment #{appt.id}: {appt.patient.get_full_name()} with '
               f'Dr. {appt.doctor.get_full_name()} on {appt.appointment_date:%a %d %b} at {appt.appointment_time:%H:%M}')
    return _propose(ctx, 'cancel_appointment', {'appointment_id': appt.id, 'reason': reason}, summary)


# ── Patient self-service ──────────────────────────────────────────────────

@tool('get_my_health_summary',
      "Return the signed-in patient's own records: allergies, conditions, current medications, recent "
      'diagnoses, vitals and lab results. Use it to answer questions about their own care.',
      {}, roles=('patient',))
def get_my_health_summary(ctx):
    return patient_context(ctx.user, record_limit=5)


@tool('list_my_invoices', "List the signed-in patient's invoices with remaining balances and due dates.",
      {'open_only': {'type': 'boolean'}}, roles=('patient',), ui=True)
def list_my_invoices(ctx, open_only=True):
    qs = Invoice.objects.filter(patient=ctx.user).prefetch_related('payments')
    if open_only:
        qs = qs.filter(status__in=['pending', 'partially_paid', 'overdue'])
    return {'invoices': [
        {'invoice_id': i.id, 'number': i.invoice_number, 'status': i.status, 'total': float(i.total),
         'balance': float(i.remaining_balance), 'due_date': i.due_date.isoformat()}
        for i in qs[:20]
    ]}


# ── Clinical tools (doctors / admins) ──────────────────────────────────────

@tool('search_patients',
      'Find patients you have a care relationship with (admins: any patient) by name.',
      {'query': {'type': 'string'}}, required=('query',), roles=('doctor', 'admin'))
def search_patients(ctx, query):
    qs = visible_patients(ctx.user)
    for part in query.split():
        qs = qs.filter(Q(first_name__icontains=part) | Q(last_name__icontains=part) | Q(username__icontains=part))
    return {'patients': [{'patient_id': p.id, 'name': p.get_full_name() or p.username} for p in qs[:15]]}


@tool('get_patient_context',
      'Full clinical context for one patient: allergies, chronic conditions, active medications with open '
      'safety alerts, recent diagnoses, vitals trend, labs and visit history.',
      {'patient_id': {'type': 'integer'}}, required=('patient_id',), roles=('doctor', 'admin'))
def get_patient_context(ctx, patient_id):
    patient = get_patient_for(ctx.user, patient_id)
    return patient_context(patient)


@tool('check_prescription_safety',
      'Run the deterministic prescription safety engine for a proposed medication: allergy cross-reactivity, '
      'drug-drug interactions with active meds, condition contraindications, age cautions and dose ceilings. '
      'Always run this before recommending or discussing a new medication for a patient.',
      {'patient_id': {'type': 'integer'}, 'medication_name': {'type': 'string'},
       'dosage': {'type': 'string', 'description': 'e.g. "500mg"'},
       'frequency': {'type': 'string', 'description': 'e.g. "twice daily"'}},
      required=('patient_id', 'medication_name'), roles=('doctor', 'admin'), ui=True)
def check_prescription_safety_tool(ctx, patient_id, medication_name, dosage='', frequency=''):
    from .safety import check_prescription
    patient = get_patient_for(ctx.user, patient_id)
    findings = check_prescription(patient, medication_name, dosage, frequency)
    return {
        'medication': medication_name, 'patient_id': patient.id,
        'findings': [f.to_dict() for f in findings],
        'highest_severity': findings[0].severity if findings else 'none',
        'disclaimer': 'Decision support only; knowledge base is not exhaustive.',
    }


# ── Admin analytics (read-only, parameterised ORM queries — no free-form SQL) ─

@tool('appointment_analytics',
      'Count appointments in a date range grouped by status, doctor, specialization, day, or weekday. '
      'Returns rows plus a chart hint.',
      {'start_date': {'type': 'string'}, 'end_date': {'type': 'string'},
       'group_by': {'type': 'string', 'enum': ['status', 'doctor', 'specialization', 'day', 'weekday']}},
      required=('group_by',), roles=('admin',), ui=True)
def appointment_analytics(ctx, group_by, start_date=None, end_date=None):
    start, end = _range(start_date, end_date)
    qs = Appointment.objects.filter(appointment_date__range=(start, end))
    if group_by == 'status':
        rows = [{'label': r['status'], 'value': r['n']} for r in qs.values('status').annotate(n=Count('id')).order_by('-n')]
    elif group_by == 'doctor':
        rows = [{'label': f"Dr. {r['doctor__first_name']} {r['doctor__last_name']}", 'value': r['n'],
                 'no_shows': r['ns'], 'completed': r['done']}
                for r in qs.values('doctor__first_name', 'doctor__last_name').annotate(
                    n=Count('id'), ns=Count('id', filter=Q(status='no_show')),
                    done=Count('id', filter=Q(status='completed'))).order_by('-n')]
    elif group_by == 'specialization':
        rows = [{'label': r['doctor__doctor_profile__specialization'] or 'Unknown', 'value': r['n']}
                for r in qs.values('doctor__doctor_profile__specialization').annotate(n=Count('id')).order_by('-n')]
    elif group_by == 'day':
        rows = [{'label': r['d'].isoformat() if hasattr(r['d'], 'isoformat') else str(r['d']), 'value': r['n']}
                for r in qs.annotate(d=TruncDay('appointment_date')).values('d').annotate(n=Count('id')).order_by('d')]
    else:
        names = {1: 'Sun', 2: 'Mon', 3: 'Tue', 4: 'Wed', 5: 'Thu', 6: 'Fri', 7: 'Sat'}
        rows = [{'label': names[r['wd']], 'value': r['n']}
                for r in qs.annotate(wd=ExtractWeekDay('appointment_date')).values('wd').annotate(n=Count('id')).order_by('wd')]
    return {'metric': 'appointments', 'group_by': group_by, 'start_date': start.isoformat(),
            'end_date': end.isoformat(), 'total': qs.count(), 'rows': rows,
            'chart': {'type': 'line' if group_by == 'day' else 'bar', 'x': 'label', 'y': 'value'}}


@tool('revenue_analytics',
      'Collected revenue (sum of payments) in a date range grouped by month, doctor, specialization or payment_method.',
      {'start_date': {'type': 'string'}, 'end_date': {'type': 'string'},
       'group_by': {'type': 'string', 'enum': ['month', 'doctor', 'specialization', 'payment_method']}},
      required=('group_by',), roles=('admin',), ui=True)
def revenue_analytics(ctx, group_by, start_date=None, end_date=None):
    start, end = _range(start_date, end_date, default_days=180)
    qs = Payment.objects.filter(payment_date__date__range=(start, end))
    if group_by == 'month':
        data = qs.annotate(m=TruncMonth('payment_date')).values('m').annotate(total=Sum('amount')).order_by('m')
        rows = [{'label': r['m'].strftime('%b %Y'), 'value': float(r['total'])} for r in data]
    elif group_by == 'doctor':
        data = qs.values('invoice__appointment__doctor__first_name', 'invoice__appointment__doctor__last_name') \
            .annotate(total=Sum('amount')).order_by('-total')
        rows = [{'label': (f"Dr. {r['invoice__appointment__doctor__first_name']} {r['invoice__appointment__doctor__last_name']}"
                           if r['invoice__appointment__doctor__first_name'] else 'No appointment linked'),
                 'value': float(r['total'])} for r in data]
    elif group_by == 'specialization':
        data = qs.values('invoice__appointment__doctor__doctor_profile__specialization') \
            .annotate(total=Sum('amount')).order_by('-total')
        rows = [{'label': r['invoice__appointment__doctor__doctor_profile__specialization'] or 'Unlinked',
                 'value': float(r['total'])} for r in data]
    else:
        data = qs.values('payment_method').annotate(total=Sum('amount')).order_by('-total')
        rows = [{'label': r['payment_method'], 'value': float(r['total'])} for r in data]
    total = qs.aggregate(s=Sum('amount'))['s'] or Decimal('0')
    return {'metric': 'revenue_usd', 'group_by': group_by, 'start_date': start.isoformat(),
            'end_date': end.isoformat(), 'total': float(total), 'rows': rows,
            'chart': {'type': 'line' if group_by == 'month' else 'bar', 'x': 'label', 'y': 'value'}}


@tool('no_show_report',
      'No-show rate per doctor and the patients with repeated no-shows in a date range.',
      {'start_date': {'type': 'string'}, 'end_date': {'type': 'string'}}, roles=('admin',), ui=True)
def no_show_report(ctx, start_date=None, end_date=None):
    start, end = _range(start_date, end_date, default_days=90)
    qs = Appointment.objects.filter(appointment_date__range=(start, end))
    per_doc = qs.values('doctor__first_name', 'doctor__last_name').annotate(
        total=Count('id'), ns=Count('id', filter=Q(status='no_show'))).order_by('-ns')
    rows = [{'label': f"Dr. {r['doctor__first_name']} {r['doctor__last_name']}", 'value': r['ns'],
             'total': r['total'], 'rate_pct': round(100 * r['ns'] / r['total'], 1) if r['total'] else 0}
            for r in per_doc]
    repeat = qs.filter(status='no_show').values('patient_id', 'patient__first_name', 'patient__last_name') \
        .annotate(n=Count('id')).filter(n__gte=2).order_by('-n')[:10]
    overall = qs.count()
    return {'metric': 'no_shows', 'start_date': start.isoformat(), 'end_date': end.isoformat(),
            'overall_rate_pct': round(100 * qs.filter(status='no_show').count() / overall, 1) if overall else 0,
            'rows': rows, 'repeat_no_show_patients': [
                {'patient_id': r['patient_id'], 'name': f"{r['patient__first_name']} {r['patient__last_name']}",
                 'no_shows': r['n']} for r in repeat],
            'chart': {'type': 'bar', 'x': 'label', 'y': 'value'}}


@tool('outstanding_balances',
      'Open invoices with remaining balances, most overdue first.',
      {'limit': {'type': 'integer'}, 'overdue_only': {'type': 'boolean'}}, roles=('admin',), ui=True)
def outstanding_balances(ctx, limit=20, overdue_only=False):
    qs = Invoice.objects.filter(status__in=['pending', 'partially_paid', 'overdue']).select_related('patient') \
        .prefetch_related('payments').order_by('due_date')
    if overdue_only:
        qs = qs.filter(due_date__lt=timezone.localdate())
    today = timezone.localdate()
    rows = []
    for inv in qs[: max(1, min(int(limit or 20), 100))]:
        rows.append({'invoice_id': inv.id, 'number': inv.invoice_number, 'patient': inv.patient.get_full_name(),
                     'patient_id': inv.patient_id, 'balance': float(inv.remaining_balance),
                     'due_date': inv.due_date.isoformat(), 'days_overdue': max(0, (today - inv.due_date).days),
                     'status': inv.status})
    return {'invoices': rows, 'total_outstanding': round(sum(r['balance'] for r in rows), 2)}


@tool('insurance_claim_precheck',
      'Check an insurance claim for problems likely to cause rejection (policy mismatch, missing diagnosis, '
      'amount issues, duplicates, late filing). Returns a risk level and issues.',
      {'claim_id': {'type': 'integer'}}, required=('claim_id',), roles=('admin',), ui=True)
def insurance_claim_precheck_tool(ctx, claim_id):
    from .claims import precheck_claim
    try:
        claim = InsuranceClaim.objects.select_related('invoice', 'patient', 'patient__patient_profile').get(pk=claim_id)
    except InsuranceClaim.DoesNotExist:
        raise ToolError(f'Claim {claim_id} not found.')
    return precheck_claim(claim, use_llm=False)


@tool('propose_invoice_for_appointment',
      'Draft an invoice for a completed appointment: consultation fee from the doctor profile, plus any '
      'extra line items (lab tests, procedures). Creates an action card an admin must approve.',
      {'appointment_id': {'type': 'integer'},
       'extra_items': {'type': 'array', 'items': {'type': 'object', 'properties': {
           'description': {'type': 'string'}, 'quantity': {'type': 'integer'}, 'unit_price': {'type': 'number'}},
           'required': ['description', 'unit_price']}},
       'tax_rate_pct': {'type': 'number'}, 'due_in_days': {'type': 'integer'}},
      required=('appointment_id',), roles=('admin',), writes=True)
def propose_invoice_for_appointment(ctx, appointment_id, extra_items=None, tax_rate_pct=8.0, due_in_days=14):
    try:
        appt = Appointment.objects.select_related('doctor__doctor_profile', 'patient').get(pk=appointment_id)
    except Appointment.DoesNotExist:
        raise ToolError(f'Appointment {appointment_id} not found.')
    if appt.status != 'completed':
        raise ToolError('Only completed appointments can be invoiced.')
    if Invoice.objects.filter(appointment=appt).exclude(status='cancelled').exists():
        raise ToolError('This appointment already has an invoice.')
    profile = getattr(appt.doctor, 'doctor_profile', None)
    items = [{'description': f'Consultation — {getattr(profile, "specialization", "General")}',
              'quantity': 1, 'unit_price': float(profile.consultation_fee) if profile else 50.0}]
    for raw in (extra_items or [])[:20]:
        price = float(raw.get('unit_price', 0))
        qty = int(raw.get('quantity', 1) or 1)
        if price < 0 or qty < 1:
            raise ToolError('Line items need a non-negative price and quantity ≥ 1.')
        items.append({'description': str(raw['description'])[:200], 'quantity': qty, 'unit_price': price})
    subtotal = sum(i['quantity'] * i['unit_price'] for i in items)
    tax = round(subtotal * max(0.0, min(float(tax_rate_pct), 30.0)) / 100, 2)
    summary = (f'Invoice {appt.patient.get_full_name()} for appointment #{appt.id} '
               f'({len(items)} items, subtotal ${subtotal:.2f} + tax ${tax:.2f})')
    return _propose(ctx, 'draft_invoice', {
        'appointment_id': appt.id, 'items': items, 'tax': tax,
        'due_in_days': max(1, min(int(due_in_days or 14), 90)),
    }, summary, approver_role='admin')


@tool('propose_patient_message',
      'Draft an in-app message to a patient (e.g. payment plan offer, follow-up reminder). An admin must approve '
      'before it is sent.',
      {'patient_id': {'type': 'integer'}, 'title': {'type': 'string'}, 'body': {'type': 'string'}},
      required=('patient_id', 'title', 'body'), roles=('admin',), writes=True)
def propose_patient_message(ctx, patient_id, title, body):
    patient = get_patient_for(ctx.user, patient_id)
    return _propose(ctx, 'send_patient_message',
                    {'patient_id': patient.id, 'title': title[:200], 'body': body[:4000]},
                    f'Send message to {patient.get_full_name()}: "{truncate(title, 80)}"', approver_role='admin')
