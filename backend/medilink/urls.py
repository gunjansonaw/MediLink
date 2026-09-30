"""
URL configuration for medilink project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.middleware.csrf import get_token
from django.http import JsonResponse
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi


schema_view = get_schema_view(
    openapi.Info(
        title="MediLink API",
        default_version='v1',
        description="Hospital Management System API Documentation",
        terms_of_service="https://www.medilink.com/terms/",
        contact=openapi.Contact(email="contact@medilink.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)


def csrf_token_view(request):
    """
    GET /api/csrf/ — Returns a JSON response whose only purpose is to trigger
    Django's middleware to set the csrftoken cookie on the client.
    The frontend calls this once on startup so subsequent POST requests can
    read the cookie and send it as X-CSRFToken.
    """
    return JsonResponse({'detail': 'CSRF cookie set', 'csrfToken': get_token(request)})


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/users/', include('users.urls')),
    path('api/appointments/', include('appointments.urls')),
    path('api/medical-records/', include('medical_records.urls')),
    path('api/billing/', include('billing.urls')),

    # CSRF cookie endpoint — call once on app init so JS can read the cookie
    path('api/csrf/', csrf_token_view, name='csrf-token'),

    # API Documentation
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
