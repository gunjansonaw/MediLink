from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AppointmentViewSet, ScheduleViewSet

router = DefaultRouter()
router.register(r'appointments', AppointmentViewSet, basename='appointment')
router.register(r'schedules', ScheduleViewSet, basename='schedule')

urlpatterns = [
    path('', include(router.urls)),
]
