from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MedicalRecordViewSet, PrescriptionViewSet, LabTestViewSet, VitalSignsViewSet

router = DefaultRouter()
router.register(r'records', MedicalRecordViewSet, basename='medical-record')
router.register(r'prescriptions', PrescriptionViewSet, basename='prescription')
router.register(r'lab-tests', LabTestViewSet, basename='lab-test')
router.register(r'vital-signs', VitalSignsViewSet, basename='vital-signs')

urlpatterns = [
    path('', include(router.urls)),
]
