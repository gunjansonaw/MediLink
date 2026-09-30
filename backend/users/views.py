from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
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
COOKIE_DOMAIN  = getattr(settings, 'JWT_AUTH_COOKIE_DOMAIN', None)


def _set_auth_cookies(response, refresh_token):
    """Attach the access & refresh JWT tokens as HttpOnly cookies."""
    access_token = refresh_token.access_token
    access_lifetime  = int(settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds())
    refresh_lifetime = int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds())

    common = dict(
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        domain=COOKIE_DOMAIN,
    )
    response.set_cookie(ACCESS_COOKIE,  str(access_token),      max_age=access_lifetime,  path='/', **common)
    response.set_cookie(REFRESH_COOKIE, str(refresh_token),     max_age=refresh_lifetime, path='/api/users/token/refresh/', **common)


def _clear_auth_cookies(response):
    """Remove both auth cookies."""
    response.delete_cookie(ACCESS_COOKIE,  path='/')
    response.delete_cookie(REFRESH_COOKIE, path='/api/users/token/refresh/')


# ─── Auth endpoints ───────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
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
    if not user:
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

    try:
        refresh = RefreshToken(raw_refresh)
        # Trigger rotation / blacklisting configured in SIMPLE_JWT
        new_access = str(refresh.access_token)
    except (TokenError, InvalidToken) as exc:
        response = Response({'error': str(exc)}, status=status.HTTP_401_UNAUTHORIZED)
        _clear_auth_cookies(response)
        return response

    response = Response({'detail': 'Token refreshed'})
    access_lifetime = int(settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds())
    common = dict(
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        domain=COOKIE_DOMAIN,
    )
    response.set_cookie(ACCESS_COOKIE, new_access, max_age=access_lifetime, path='/', **common)

    # If rotation is enabled, update the refresh cookie too
    if settings.SIMPLE_JWT.get('ROTATE_REFRESH_TOKENS', False):
        refresh_lifetime = int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds())
        response.set_cookie(
            REFRESH_COOKIE, str(refresh),
            max_age=refresh_lifetime,
            path='/api/users/token/refresh/',
            **common,
        )

    return response


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
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

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        elif self.action in ['update', 'partial_update', 'destroy']:
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
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def doctors(self, request):
        doctors = User.objects.filter(role='doctor').select_related('doctor_profile')
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
