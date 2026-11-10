from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'conversations', views.ConversationViewSet, basename='ai-conversation')
router.register(r'pending-actions', views.PendingActionViewSet, basename='ai-pending-action')
router.register(r'safety-alerts', views.SafetyAlertViewSet, basename='ai-safety-alert')
router.register(r'notifications', views.NotificationViewSet, basename='ai-notification')
router.register(r'audit-log', views.AuditLogViewSet, basename='ai-audit-log')

urlpatterns = [
    path('status/', views.ai_status, name='ai-status'),
    path('chat/', views.chat, name='ai-chat'),
    path('prescription-check/', views.prescription_check, name='ai-prescription-check'),
    path('briefs/<int:appointment_id>/', views.appointment_brief, name='ai-brief'),
    path('lab-insights/<int:lab_test_id>/', views.lab_insight, name='ai-lab-insight'),
    path('claims/<int:claim_id>/precheck/', views.claim_precheck, name='ai-claim-precheck'),
    path('agents/<str:name>/run/', views.run_agent, name='ai-run-agent'),
    path('', include(router.urls)),
]
