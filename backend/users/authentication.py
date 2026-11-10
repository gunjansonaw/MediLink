"""
Custom JWT authentication that reads tokens from HttpOnly cookies
instead of the Authorization header.
"""
from django.conf import settings
from django.middleware.csrf import CsrfViewMiddleware
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class _CSRFCheck(CsrfViewMiddleware):
    def _reject(self, request, reason):
        # Return the failure reason instead of an HttpResponse
        return reason


def enforce_csrf(request):
    """
    Cookies are sent automatically by the browser, so cookie-authenticated
    requests must carry a valid CSRF token (same approach as DRF's
    SessionAuthentication). Header (Bearer) auth is not CSRF-prone.
    """
    def dummy_get_response(_request):  # pragma: no cover
        return None

    check = _CSRFCheck(dummy_get_response)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise exceptions.PermissionDenied(f'CSRF Failed: {reason}')


class CookieJWTAuthentication(JWTAuthentication):
    """
    Authenticates requests using JWT stored in an HttpOnly cookie.
    Falls back to the standard Authorization header for API clients
    (e.g. Swagger, mobile apps, tests).
    """

    def authenticate(self, request):
        # 1. Prefer an explicit Authorization header (API clients)
        header = self.get_header(request)
        if header is not None:
            return super().authenticate(request)

        # 2. Otherwise use the HttpOnly cookie
        cookie_name = getattr(settings, 'JWT_AUTH_COOKIE', 'medilink_access')
        raw_token = request.COOKIES.get(cookie_name)
        if not raw_token:
            return None

        try:
            validated_token = self.get_validated_token(raw_token)
        except (InvalidToken, TokenError):
            # Expired / invalid cookie: treat as anonymous so the client gets a
            # 401 and can silently refresh.
            return None

        user = self.get_user(validated_token)
        enforce_csrf(request)
        return user, validated_token
