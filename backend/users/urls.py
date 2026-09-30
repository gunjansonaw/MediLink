from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, login_view, logout_view, token_refresh_view

router = DefaultRouter()
router.register(r'', UserViewSet, basename='user')

urlpatterns = [
    # Auth endpoints (cookie-based)
    path('login/',                login_view,         name='user-login'),
    path('logout/',               logout_view,        name='user-logout'),
    path('token/refresh/',        token_refresh_view, name='user-token-refresh'),
    # User CRUD
    path('', include(router.urls)),
]
