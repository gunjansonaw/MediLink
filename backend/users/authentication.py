"""
Custom JWT authentication that reads tokens from HttpOnly cookies
instead of the Authorization header.
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.conf import settings


class CookieJWTAuthentication(JWTAuthentication):
    """
    Authenticates requests using JWT stored in an HttpOnly cookie.
    Falls back to the standard Authorization header for API clients
    (e.g. Swagger, mobile apps, tests).
    """

    def authenticate(self, request):
        # 1. Try the cookie first
        cookie_name = getattr(settings, 'JWT_AUTH_COOKIE', 'medilink_access')
        raw_token = request.COOKIES.get(cookie_name)

        if raw_token:
            try:
                validated_token = self.get_validated_token(raw_token)
                return self.get_user(validated_token), validated_token
            except (InvalidToken, TokenError):
                # Cookie token is invalid / expired — fall through to header
                pass

        # 2. Fall back to the standard Bearer header
        return super().authenticate(request)
