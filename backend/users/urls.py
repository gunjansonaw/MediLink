from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, login_view

router = DefaultRouter()
router.register(r'', UserViewSet, basename='user')

urlpatterns = [
    path('login/', login_view, name='user-login'),
    path('', include(router.urls)),
]
