"""
Thin wrapper around the Anthropic SDK.

Every AI feature in MediLink calls Claude through `create_message()` so that
model choice, effort, refusal fallbacks, timeouts and the "no API key" mode are
configured in exactly one place.
"""
import logging
import os

from django.conf import settings

logger = logging.getLogger(__name__)

FALLBACK_BETA = 'server-side-fallback-2026-07-01'

_client = None


class LLMUnavailable(Exception):
    """Raised when no Claude credentials are configured or AI is disabled."""


class LLMRefusal(Exception):
    """Raised when the model (and its fallback) declined the request."""


def llm_enabled() -> bool:
    if not getattr(settings, 'AI_ENABLED', True):
        return False
    return bool(os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('ANTHROPIC_AUTH_TOKEN'))


def get_client():
    global _client
    if not llm_enabled():
        raise LLMUnavailable('AI features are running in rules-only mode (no ANTHROPIC_API_KEY).')
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(timeout=settings.AI_REQUEST_TIMEOUT, max_retries=2)
    return _client


def reset_client():
    """Used by tests to swap in a fake client."""
    global _client
    _client = None


def set_client(client):
    global _client
    _client = client


def create_message(*, system, messages, tools=None, max_tokens=16000, effort=None):
    """
    One Messages API call with MediLink defaults:
    - model from settings.AI_MODEL (default claude-opus-5-5, adaptive thinking is on by default)
    - explicit effort (Opus 5.5 defaults to medium; we make it configurable)
    - server-side refusal fallback ("default" routing) so a policy decline is
      retried on Anthropic's recommended fallback model instead of failing.
    """
    client = get_client()
    params = dict(
        model=settings.AI_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
        output_config={'effort': effort or settings.AI_EFFORT},
        betas=[FALLBACK_BETA],
        fallbacks='default',
    )
    if tools:
        params['tools'] = tools
    response = client.beta.messages.create(**params)
    if response.stop_reason == 'refusal':
        category = getattr(getattr(response, 'stop_details', None), 'category', None)
        logger.warning('Claude declined request (category=%s, request_id=%s)', category,
                       getattr(response, '_request_id', None))
        raise LLMRefusal(category or 'unspecified')
    return response


def response_text(response) -> str:
    return '\n'.join(b.text for b in response.content if getattr(b, 'type', None) == 'text').strip()


def content_to_dicts(content):
    """Serialize SDK content blocks so they can be stored as JSON and replayed unchanged."""
    out = []
    for block in content:
        if hasattr(block, 'to_dict'):
            out.append(block.to_dict())
        elif hasattr(block, 'model_dump'):
            out.append(block.model_dump(exclude_none=True))
        else:
            out.append(block)
    return out
