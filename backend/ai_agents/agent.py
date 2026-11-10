"""
Conversational agents (one per role) built on a manual Claude tool-use loop.

Why a manual loop instead of the SDK tool runner: every tool call must be
role-checked against the *Django* user and written to the audit log, write tools
must be converted into approval cards, and the conversation is persisted in
Postgres between HTTP requests.
"""
import logging

from django.utils import timezone

from .guardrails import detect_emergency, emergency_reply
from .llm import LLMRefusal, LLMUnavailable, content_to_dicts, create_message, llm_enabled
from .models import AgentConversation, PendingAction
from .tools import REGISTRY, ToolContext, execute_tool, infer_specialty, tools_for

logger = logging.getLogger(__name__)

COMMON_RULES = """
Ground rules:
- Use tools to look things up; never invent doctors, slots, prices, records or numbers.
- Tools that change data (names starting with "propose_") only create an approval card. After calling one,
  tell the user plainly that they need to click "Approve" on the card; never claim something is already booked,
  cancelled, invoiced or sent.
- If a tool returns an error, explain it briefly and try a sensible alternative (e.g. another slot or day).
- Keep replies short and scannable: a sentence or two, then bullets if listing options.
- Today's date and the user's identity are given at the top of each user message. Resolve relative dates
  ("next Tuesday", "tomorrow morning") against that date.
"""

SYSTEM_PROMPTS = {
    'patient': f"""You are MediLink's patient assistant. You help patients book, reschedule or cancel appointments,
understand their own records, prescriptions and lab results, and check their bills.

Booking workflow: understand the concern -> pick the right specialty (use General Medicine when unsure) ->
search_doctors -> get_available_slots for the requested window -> offer 2-4 concrete options -> once the patient
chooses (or clearly states a preference that matches a free slot), call propose_appointment.

Medical safety:
- You are not a doctor. Do not diagnose, do not recommend starting, stopping or changing medication doses.
  Explain records in plain language and encourage discussing decisions with their doctor.
- If anything suggests an emergency (chest pain with breathlessness, stroke signs, severe bleeding,
  thoughts of self-harm...), tell them to call emergency services immediately instead of booking.
{COMMON_RULES}""",
    'doctor': f"""You are MediLink's clinical copilot for doctors. You help with schedule questions, summarising
patient history before visits, and medication safety checks.

- Use get_patient_context for history questions and cite dates / values from it.
- Before discussing any new medication for a patient, call check_prescription_safety and report every
  finding, most severe first. The engine is decision support only: the prescriber makes the decision.
- Be concise and clinical; use standard abbreviations. Flag missing data rather than guessing.
- You cannot write medical records or prescriptions yourself; the doctor does that in the Medical Records page.
{COMMON_RULES}""",
    'admin': f"""You are MediLink's operations analyst and billing assistant for hospital administrators.

- Answer analytics questions with the analytics tools (appointment_analytics, revenue_analytics,
  no_show_report, outstanding_balances). State the date range you used. Lead with the key number, then
  1-3 insights. The UI renders charts from tool results automatically, so don't draw ASCII charts.
- For billing work, use insurance_claim_precheck, propose_invoice_for_appointment and propose_patient_message.
  When proposing outreach to patients, be respectful and never shame them about money.
- Default date range when unspecified: the last 30 days (revenue: last 6 months).
{COMMON_RULES}""",
}


def _context_line(user):
    now = timezone.localtime()
    return (f'[Context — today is {now:%A %Y-%m-%d}, time {now:%H:%M} ({timezone.get_current_timezone_name()}). '
            f'User: {user.get_full_name() or user.username} (id {user.id}, role {user.role}).]')


def _append_user_text(messages, text):
    """Append a user turn, merging into a trailing user message (e.g. after a step-limit tool_result)."""
    block = {'type': 'text', 'text': text}
    if messages and messages[-1]['role'] == 'user':
        content = messages[-1]['content']
        if isinstance(content, str):
            content = [{'type': 'text', 'text': content}]
        messages[-1]['content'] = content + [block]
    else:
        messages.append({'role': 'user', 'content': [block]})


def _final_text(content):
    return '\n'.join(b.get('text', '') for b in content if b.get('type') == 'text').strip()


def run_chat(user, text, conversation: AgentConversation | None = None, max_steps=None):
    """
    Run one user turn. Returns a dict:
      {conversation_id, reply, mode, tool_calls: [...], pending_actions: [...]}
    """
    from django.conf import settings
    max_steps = max_steps or settings.AI_MAX_AGENT_STEPS

    if conversation is None:
        conversation = AgentConversation.objects.create(user=user, role=user.role, title=text[:80])
    elif conversation.user_id != user.id:
        raise PermissionError('Not your conversation')

    emergency = detect_emergency(text)
    if emergency and user.role == 'patient':
        reply = emergency_reply(emergency)
        # Record the exchange as plain text so the history stays valid for the model
        messages = list(conversation.messages)
        _append_user_text(messages, f'{_context_line(user)}\n{text}')
        messages.append({'role': 'assistant', 'content': [{'type': 'text', 'text': reply}]})
        conversation.messages = messages
        conversation.save(update_fields=['messages', 'updated_at'])
        return _result(conversation, reply, 'guardrail', [])

    if not llm_enabled():
        return rules_chat(user, text, conversation)

    tools = [t.api_schema() for t in tools_for(user)]
    system = SYSTEM_PROMPTS[user.role]
    ctx = ToolContext(user=user, conversation=conversation, agent=f'{user.role}_assistant')

    messages = list(conversation.messages)
    _append_user_text(messages, f'{_context_line(user)}\n{text}')
    trace = []
    reply = ''

    try:
        for _step in range(max_steps):
            response = create_message(system=system, messages=messages, tools=tools)
            content = content_to_dicts(response.content)
            messages.append({'role': 'assistant', 'content': content})

            if response.stop_reason == 'pause_turn':
                continue
            if response.stop_reason != 'tool_use':
                reply = _final_text(content)
                if response.stop_reason == 'max_tokens':
                    reply += '\n\n_(Response was cut short — ask me to continue.)_'
                break

            results = []
            for block in content:
                if block.get('type') != 'tool_use':
                    continue
                output, is_error = execute_tool(ctx, block['name'], block.get('input') or {})
                trace.append({
                    'tool': block['name'], 'input': block.get('input') or {}, 'is_error': is_error,
                    'result': output if REGISTRY.get(block['name']) and REGISTRY[block['name']].ui and not is_error else None,
                })
                results.append({'type': 'tool_result', 'tool_use_id': block['id'],
                                'content': _json(output), 'is_error': is_error})
            messages.append({'role': 'user', 'content': results})
        else:
            reply = _final_text(messages[-2]['content']) if len(messages) >= 2 else ''
            reply = (reply + '\n\n' if reply else '') + "I've reached my step limit for this request — " \
                "could you narrow it down a little?"
    except LLMRefusal:
        reply = "I can't help with that request. If this is about your health, please contact your doctor."
        _append_assistant_note(messages, reply)
    except LLMUnavailable:
        return rules_chat(user, text, conversation)
    except Exception:
        logger.exception('Agent run failed for conversation %s', conversation.pk)
        raise

    conversation.messages = messages
    conversation.save(update_fields=['messages', 'updated_at'])
    return _result(conversation, reply, 'llm', trace)


def _append_assistant_note(messages, text):
    # Keep the stored history valid: the last entry must not be a dangling user turn
    messages.append({'role': 'assistant', 'content': [{'type': 'text', 'text': text}]})


def _json(obj):
    import json
    return json.dumps(obj, default=str)


def _result(conversation, reply, mode, trace):
    pending = PendingAction.objects.filter(conversation=conversation, status='pending').order_by('created_at')
    return {
        'conversation_id': conversation.id,
        'reply': reply,
        'mode': mode,
        'tool_calls': trace,
        'pending_actions': [
            {'id': a.id, 'action_type': a.action_type, 'summary': a.summary, 'status': a.status,
             'approver_role': a.approver_role}
            for a in pending
        ],
    }


# ── Rules-only mode (no API key) ────────────────────────────────────────────

def _has(text, *words):
    t = text.lower()
    return any(w in t for w in words)


def rules_chat(user, text, conversation):
    """
    A deterministic assistant used when no Claude API key is configured, so the
    product still works on a free deployment. It reuses the same audited tools.
    """
    ctx = ToolContext(user=user, conversation=conversation, agent=f'{user.role}_rules')
    trace = []

    def call(name, **kwargs):
        out, err = execute_tool(ctx, name, kwargs)
        trace.append({'tool': name, 'input': kwargs, 'is_error': err, 'result': None if err else out})
        return out, err

    today = timezone.localdate()
    reply = None
    if user.role == 'patient':
        if _has(text, 'book', 'appointment', 'see a doctor', 'specialist', 'consult'):
            spec = infer_specialty(text)
            out, _ = call('search_doctors', specialization=spec)
            doctors = out.get('doctors') or out.get('general_practitioners') or []
            if doctors:
                d = doctors[0]
                slots, _ = call('get_available_slots', doctor_id=d['doctor_id'], start_date=today.isoformat())
                options = ', '.join(f"{s['date']} {s['time']}" for s in slots.get('slots', [])[:4]) or 'none this week'
                reply = (f"Based on your message, **{spec}** looks like the right place to start. "
                         f"{d['name']} has openings: {options}. Use **Book Appointment** on the Appointments page "
                         "to pick one.")
            else:
                reply = 'I could not find a matching doctor. Please use the Appointments page to browse all doctors.'
        elif _has(text, 'bill', 'invoice', 'pay', 'balance', 'owe'):
            out, _ = call('list_my_invoices', open_only=True)
            inv = out.get('invoices', [])
            reply = ('You have no open invoices. 🎉' if not inv else
                     'Open invoices:\n' + '\n'.join(f"- #{i['number']}: ${i['balance']:.2f} due {i['due_date']} ({i['status']})" for i in inv))
        elif _has(text, 'cancel', 'upcoming', 'my appointments', 'when is'):
            out, _ = call('list_appointments', upcoming_only=True)
            ap = out.get('appointments', [])
            reply = ('You have no upcoming appointments.' if not ap else
                     'Your upcoming appointments:\n' + '\n'.join(f"- #{a['appointment_id']} {a['date']} {a['time']} with {a['doctor']}" for a in ap))
    elif user.role == 'doctor':
        out, _ = call('list_appointments', date=today.isoformat())
        ap = out.get('appointments', [])
        reply = ("Today's schedule:\n" + '\n'.join(f"- {a['time']} {a['patient']} — {a['reason']}" for a in ap)
                 if ap else 'You have no appointments today.')
        reply += '\n\nPre-visit briefs and prescription safety checks are available on each appointment and prescription.'
    elif user.role == 'admin':
        if _has(text, 'revenue', 'income', 'earn', 'money'):
            out, _ = call('revenue_analytics', group_by='month')
            reply = f"Collected revenue for {out['start_date']} → {out['end_date']}: **${out['total']:,.2f}**."
        elif _has(text, 'no-show', 'no show', 'noshow', 'missed'):
            out, _ = call('no_show_report')
            reply = f"No-show rate over the last 90 days: **{out['overall_rate_pct']}%**."
        elif _has(text, 'overdue', 'outstanding', 'unpaid', 'balance'):
            out, _ = call('outstanding_balances', limit=10)
            reply = f"Outstanding across the top {len(out['invoices'])} open invoices: **${out['total_outstanding']:,.2f}**."
        elif _has(text, 'appointment', 'visits', 'bookings'):
            group = 'doctor' if _has(text, 'doctor') else 'specialization' if _has(text, 'special') else 'status'
            out, _ = call('appointment_analytics', group_by=group)
            reply = f"{out['total']} appointments between {out['start_date']} and {out['end_date']}, grouped by {group}."

    if reply is None:
        reply = ('The AI assistant is running in **limited mode** (no Claude API key configured), so I can only '
                 'handle common requests: ' + {
                     'patient': 'booking help ("book a cardiologist"), your bills, or your upcoming appointments.',
                     'doctor': "today's schedule.",
                     'admin': 'revenue, no-shows, outstanding balances or appointment counts.',
                 }[user.role])

    messages = list(conversation.messages)
    _append_user_text(messages, f'{_context_line(user)}\n{text}')
    messages.append({'role': 'assistant', 'content': [{'type': 'text', 'text': reply}]})
    conversation.messages = messages
    conversation.save(update_fields=['messages', 'updated_at'])
    return _result(conversation, reply, 'rules', trace)
