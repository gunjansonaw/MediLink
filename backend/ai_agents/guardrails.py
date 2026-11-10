"""
Deterministic guardrails that run *before* any model call.

Emergency detection is intentionally rule-based: it must work with no API key,
must be fast, and must never be talked out of escalating.
"""
import re

EMERGENCY_PATTERNS = [
    (r'\bchest (pain|pressure|tightness)\b.*\b(breath|sweat|arm|jaw)|\b(breath|sweat|arm|jaw)\w*\b.*\bchest (pain|pressure|tightness)',
     'possible heart attack'),
    (r"\b(can'?t|cannot|unable to|hard to|trouble) breath(e|ing)?\b|\bshort(ness)? of breath\b.*\b(severe|sudden|worse)",
     'severe breathing difficulty'),
    (r'\b(face (is )?droop|slurred speech|sudden (numbness|weakness)|one side of (my|the) body)\b', 'possible stroke'),
    (r'\b(kill myself|suicid\w*|end my life|want to die|self[- ]harm)\b', 'risk of self-harm'),
    (r"\b(severe|heavy|uncontrolled|won'?t stop) bleeding\b", 'severe bleeding'),
    (r'\b(throat (is )?(closing|swelling)|anaphyla\w+|swollen (tongue|lips) .*breath)', 'possible anaphylaxis'),
    (r'\b(unconscious|not breathing|unresponsive|seizure|overdose)\b', 'medical emergency'),
]

EMERGENCY_REPLY = (
    "⚠️ What you're describing may be a medical emergency ({reason}). "
    "Please call your local emergency number (e.g. 911 / 112 / 108) or go to the nearest emergency "
    "department now. Don't wait for an online appointment.\n\n"
    "If you are in crisis or thinking about harming yourself, contact a crisis line such as 988 (US) "
    "or your local equivalent immediately."
)

_EMAIL = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
_PHONE = re.compile(r'\+?\d[\d\s().-]{7,}\d')


def detect_emergency(text: str):
    lowered = (text or '').lower()
    for pattern, reason in EMERGENCY_PATTERNS:
        if re.search(pattern, lowered):
            return reason
    return None


def emergency_reply(reason: str) -> str:
    return EMERGENCY_REPLY.format(reason=reason)


def redact(text: str) -> str:
    """Mask direct identifiers before writing free text to logs / audit summaries."""
    text = _EMAIL.sub('[email]', text or '')
    return _PHONE.sub('[phone]', text)


def truncate(text: str, limit=500) -> str:
    text = text or ''
    return text if len(text) <= limit else text[: limit - 1] + '…'
