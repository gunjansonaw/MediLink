"""
Django settings for medilink project.
"""

from pathlib import Path
from datetime import timedelta
import os

try:
    import dj_database_url
    HAS_DJ_DATABASE_URL = True
except ImportError:
    HAS_DJ_DATABASE_URL = False

try:
    from decouple import config
except ImportError:
    # Fallback if decouple is not available
    def config(key, default=None, cast=None):
        value = os.getenv(key, default)
        if cast and value is not None:
            return cast(value)
        return value

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-your-secret-key-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)

_allowed_hosts = config(
    'ALLOWED_HOSTS', 
    default='localhost,127.0.0.1,testserver,backend,web,frontend,*', 
    cast=lambda v: [s.strip() for s in v.split(',') if s.strip()]
)
# Automatically support Railway and Render dynamic hostnames
_railway_host = os.getenv('RAILWAY_STATIC_URL', '')
if _railway_host and _railway_host not in _allowed_hosts:
    _allowed_hosts.append(_railway_host)

_render_host = os.getenv('RENDER_EXTERNAL_HOSTNAME', '')
if _render_host and _render_host not in _allowed_hosts:
    _allowed_hosts.append(_render_host)

ALLOWED_HOSTS = _allowed_hosts

# CSRF Trusted Origins for HTTPS cloud deployments
_csrf_trusted = config(
    'CSRF_TRUSTED_ORIGINS',
    default='http://localhost:3000,http://127.0.0.1:3000',
    cast=lambda v: [s.strip() for s in v.split(',') if s.strip()]
)
if _render_host and f'https://{_render_host}' not in _csrf_trusted:
    _csrf_trusted.append(f'https://{_render_host}')
if _railway_host and f'https://{_railway_host}' not in _csrf_trusted:
    _csrf_trusted.append(f'https://{_railway_host}')
CSRF_TRUSTED_ORIGINS = _csrf_trusted



# Application definition

INSTALLED_APPS = [
    # Local apps - users must come first due to custom user model
    'users',
    
    # Django apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',  # needed for logout token invalidation
    'corsheaders',
    'django_filters',
    'drf_yasg',
    
    # Other local apps
    'appointments',
    'medical_records',
    'billing',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'medilink.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'medilink.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

_database_url = config('DATABASE_URL', default='')
if _database_url and HAS_DJ_DATABASE_URL:
    # Production: use DATABASE_URL (Railway provides this automatically)
    DATABASES = {
        'default': dj_database_url.config(
            default=_database_url,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    # Local development: use individual DB_* variables
    _default_engine = config('DB_ENGINE', default='django.db.backends.postgresql')
    if 'sqlite' in _default_engine:
        _sqlite_name = config('SQLITE_NAME', default='db.sqlite3')
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / _sqlite_name,
            }
        }
    else:
        DATABASES = {
            'default': {
                'ENGINE': _default_engine,
                'NAME': config('DB_NAME', default='medilink'),
                'USER': config('DB_USER', default='postgres'),
                'PASSWORD': config('DB_PASSWORD', default='postgres'),
                'HOST': config('DB_HOST', default='localhost'),
                'PORT': config('DB_PORT', default='5432'),
            }
        }


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
# Django 4.2+ uses STORAGES dict; whitenoise compression for production
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'users.User'

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        # Reads JWT from HttpOnly cookie; falls back to Authorization header
        'users.authentication.CookieJWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
}

# JWT Configuration
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    # Keep the default algorithm & signing key
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
}

# ── Cookie-based JWT transport settings ──────────────────────────────────────
# Name of the HttpOnly cookies that hold the JWT tokens
JWT_AUTH_COOKIE         = 'medilink_access'
JWT_AUTH_REFRESH_COOKIE = 'medilink_refresh'
# In production (DEBUG=False) cookies must be Secure (HTTPS only)
JWT_AUTH_COOKIE_SECURE  = not DEBUG
# 'Lax' allows cookies on same-site navigations; use 'None' for cross-site
# (requires Secure=True).  'Strict' is the most locked down.
JWT_AUTH_COOKIE_SAMESITE = 'Lax'
# Set to your domain in production if needed (leave None for localhost)
JWT_AUTH_COOKIE_DOMAIN  = config('COOKIE_DOMAIN', default=None)

# CORS Configuration
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:3000,http://127.0.0.1:3000',
    cast=lambda v: [s.strip() for s in v.split(',')]
)
CORS_ALLOW_CREDENTIALS = True

# ── CSRF / Cookie Security ────────────────────────────────────────────────────
# The csrftoken cookie must NOT be HttpOnly so our JS can read it and send it
# as the X-CSRFToken request header (standard Django CSRF protection for SPAs).
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE   = not DEBUG   # True in production (HTTPS)

# Session cookie (if Django sessions are used alongside JWT)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE   = not DEBUG

# Celery Configuration
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    'check-overdue-invoices-every-hour': {
        'task': 'billing.tasks.check_overdue_invoices',
        'schedule': 3600.0,
    },
}

