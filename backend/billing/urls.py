from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import InvoiceViewSet, InvoiceItemViewSet, PaymentViewSet, InsuranceClaimViewSet

router = DefaultRouter()
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'invoice-items', InvoiceItemViewSet, basename='invoice-item')
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'insurance-claims', InsuranceClaimViewSet, basename='insurance-claim')

urlpatterns = [
    path('', include(router.urls)),
]
