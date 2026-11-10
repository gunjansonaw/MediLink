from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from django.db.models import Q
from django.contrib.auth import authenticate
from django.conf import settings
from .models import User, DoctorProfile, PatientProfile
from .serializers import (
    UserSerializer, UserRegistrationSerializer,
    UserUpdateSerializer, DoctorProfileSerializer, PatientProfileSerializer
)
from .permissions import IsOwnerOrAdmin, IsDoctorOrAdmin, IsAdminUser


# ─── Cookie helpers ──────────────────────────────────────────────────────────

ACCESS_COOKIE  = getattr(settings, 'JWT_AUTH_COOKIE', 'medilink_access')
REFRESH_COOKIE = getattr(settings, 'JWT_AUTH_REFRESH_COOKIE', 'medilink_refresh')
COOKIE_SECURE  = getattr(settings, 'JWT_AUTH_COOKIE_SECURE', not settings.DEBUG)
COOKIE_SAMESITE = getattr(settings, 'JWT_AUTH_COOKIE_SAMESITE', 'Lax')
COOKIE_DOMAIN  = getattr(settings, 'JWT_AUTH_COOKIE_DOMAIN', None) or None
# The refresh cookie must reach BOTH /token/refresh/ and /logout/ (logout needs
# it to blacklist the token), so scope it to the whole users API prefix.
REFRESH_COOKIE_PATH = '/api/users/'
LEGACY_REFRESH_COOKIE_PATH = '/api/users/token/refresh/'


def _cookie_kwargs():
    return dict(
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        domain=COOKIE_DOMAIN,
    )


def _set_auth_cookies(response, refresh_token):
    """Attach the access & refresh JWT tokens as HttpOnly cookies."""
    _set_access_cookie(response, str(refresh_token.access_token))
    _set_refresh_cookie(response, str(refresh_token))


def _set_access_cookie(response, access_token):
    access_lifetime = int(settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds())
    response.set_cookie(ACCESS_COOKIE, access_token, max_age=access_lifetime, path='/', **_cookie_kwargs())


def _set_refresh_cookie(response, refresh_token):
    refresh_lifetime = int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds())
    response.set_cookie(REFRESH_COOKIE, refresh_token, max_age=refresh_lifetime,
                        path=REFRESH_COOKIE_PATH, **_cookie_kwargs())


def _clear_auth_cookies(response):
    """Remove both auth cookies (including the legacy refresh-cookie path)."""
    kw = dict(domain=COOKIE_DOMAIN, samesite=COOKIE_SAMESITE)
    response.delete_cookie(ACCESS_COOKIE, path='/', **kw)
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, **kw)
    response.delete_cookie(REFRESH_COOKIE, path=LEGACY_REFRESH_COOKIE_PATH, **kw)


class LoginRateThrottle(ScopedRateThrottle):
    scope = 'login'

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}


# ─── Auth endpoints ───────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@throttle_classes([LoginRateThrottle])
def login_view(request):
    """
    Login endpoint.
    Sets HttpOnly cookies for access & refresh tokens.
    Returns only the user payload (no tokens in the body).
    """
    username_or_email = request.data.get('username')
    password = request.data.get('password')

    if not username_or_email or not password:
        return Response(
            {'error': 'Username (or email) and password are required'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Allow login with email or username
    auth_username = username_or_email
    if '@' in username_or_email:
        try:
            matched = User.objects.filter(email__iexact=username_or_email).first()
            if matched:
                auth_username = matched.get_username()
        except Exception:
            pass

    user = authenticate(username=auth_username, password=password)
    if not user or not user.is_active:
        return Response(
            {'error': 'Invalid credentials'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    refresh = RefreshToken.for_user(user)
    response = Response({'user': UserSerializer(user).data})
    _set_auth_cookies(response, refresh)
    return response


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def token_refresh_view(request):
    """
    Silently refresh the access token using the HttpOnly refresh cookie.
    Issues a new access cookie (and rotates the refresh cookie when
    ROTATE_REFRESH_TOKENS is True).
    """
    raw_refresh = request.COOKIES.get(REFRESH_COOKIE)
    if not raw_refresh:
        return Response({'error': 'No refresh token cookie'}, status=status.HTTP_401_UNAUTHORIZED)

    # TokenRefreshSerializer performs real rotation: it blacklists the old
    # refresh token and issues a new one when ROTATE_REFRESH_TOKENS is on.
    serializer = TokenRefreshSerializer(data={'refresh': raw_refresh})
    try:
        serializer.is_valid(raise_exception=True)
    except (TokenError, InvalidToken) as exc:
        response = Response({'error': str(exc)}, status=status.HTTP_401_UNAUTHORIZED)
        _clear_auth_cookies(response)
        return response
    except Exception:
        response = Response({'error': 'Invalid refresh token'}, status=status.HTTP_401_UNAUTHORIZED)
        _clear_auth_cookies(response)
        return response

    data = serializer.validated_data
    response = Response({'detail': 'Token refreshed'})
    _set_access_cookie(response, data['access'])
    if 'refresh' in data:
        _set_refresh_cookie(response, data['refresh'])
    return response


@api_view(['POST'])
@permission_classes([permissions.AllowAny])  # must work even when the access token has expired
def logout_view(request):
    """
    Logout: blacklists the refresh token and clears auth cookies.
    """
    raw_refresh = request.COOKIES.get(REFRESH_COOKIE)
    if raw_refresh:
        try:
            token = RefreshToken(raw_refresh)
            token.blacklist()
        except Exception:
            pass  # Already invalid – still clear cookies

    response = Response({'detail': 'Logged out successfully'})
    _clear_auth_cookies(response)
    return response


# ─── User ViewSet ─────────────────────────────────────────────────────────────

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    filterset_fields = ['role']
    search_fields = ['first_name', 'last_name', 'username', 'email']

    def get_queryset(self):
        """
        Users may only see the people they legitimately interact with:
        admins see everyone; doctors see themselves, doctors and patients;
        patients see themselves and doctors (never other patients).
        """
        user = self.request.user
        qs = User.objects.select_related('doctor_profile', 'patient_profile')
        if not user.is_authenticated:
            return qs.none()
        if user.role == 'admin':
            return qs
        if user.role == 'doctor':
            return qs.filter(Q(role__in=['doctor', 'patient']) | Q(pk=user.pk))
        return qs.filter(Q(role='doctor') | Q(pk=user.pk))

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        elif self.action == 'destroy':
            return [IsAdminUser()]
        elif self.action in ['update', 'partial_update']:
            return [IsOwnerOrAdmin()]
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'create':
            return UserRegistrationSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        return UserSerializer

    @action(detail=False, methods=['get'])
    def me(self, request):
        serializer = UserSerializer(request.user, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def doctors(self, request):
        doctors = User.objects.filter(role='doctor', is_active=True).select_related('doctor_profile')
        serializer = self.get_serializer(doctors, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def patients(self, request):
        if request.user.role not in ['admin', 'doctor']:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN,
            )
        patients = User.objects.filter(role='patient').select_related('patient_profile')
        serializer = self.get_serializer(patients, many=True)
        return Response(serializer.data)
