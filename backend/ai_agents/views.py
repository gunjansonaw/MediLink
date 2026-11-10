import logging

from django.conf import settings
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from appointments.models import Appointment
from billing.models import InsuranceClaim
from medical_records.models import LabTest
from users.permissions import IsAdminUser, IsDoctorOrAdmin

from . import actions
from .agent import run_chat
from .briefs import generate_brief
from .claims import precheck_claim
from .context import AccessDenied, get_patient_for
from .labs import explain_lab
from .llm import llm_enabled
from .models import (AgentConversation, AgentToolCall, ClinicalBrief, LabInsight, Notification,
                     PendingAction, SafetyAlert)
from .safety import check_prescription
from .serializers import (ChatRequestSerializer, ClinicalBriefSerializer, ConversationListSerializer,
                          ConversationSerializer, LabInsightSerializer, NotificationSerializer,
                          PendingActionSerializer, PrescriptionCheckSerializer, SafetyAlertSerializer,
                          ToolCallSerializer)

logger = logging.getLogger(__name__)


class AIRateThrottle(UserRateThrottle):
    """Per-user limit on endpoints that may call the LLM."""
    scope = 'ai'


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def ai_status(request):
    return Response({'llm_enabled': llm_enabled(), 'model': settings.AI_MODEL if llm_enabled() else None,
                     'mode': 'llm' if llm_enabled() else 'rules'})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([AIRateThrottle])
def chat(request):
    data = ChatRequestSerializer(data=request.data)
    data.is_valid(raise_exception=True)
    conversation = None
    if data.validated_data.get('conversation_id'):
        conversation = get_object_or_404(AgentConversation, pk=data.validated_data['conversation_id'], user=request.user)
    try:
        result = run_chat(request.user, data.validated_data['message'], conversation)
    except Exception:
        logger.exception('chat failed')
        return Response({'error': 'The assistant is temporarily unavailable. Please try again.'},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)
    return Response(result)


class ConversationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.DestroyModelMixin,
                          viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return AgentConversation.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        return ConversationListSerializer if self.action == 'list' else ConversationSerializer


class PendingActionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = PendingActionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['status', 'action_type', 'conversation']

    def get_queryset(self):
        user = self.request.user
        q = Q(requested_by=user)
        if user.role == 'admin':
            q |= Q(approver_role='admin')
        return PendingAction.objects.filter(q).select_related('requested_by')

    def _decide(self, request, fn):
        action_obj = self.get_object()
        try:
            action_obj = fn(action_obj, request.user)
        except actions.ActionError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PendingActionSerializer(action_obj).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        return self._decide(request, actions.approve)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        return self._decide(request, actions.reject)


class SafetyAlertViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = SafetyAlertSerializer
    permission_classes = [IsDoctorOrAdmin]
    filterset_fields = ['prescription', 'severity', 'category']

    def get_queryset(self):
        user = self.request.user
        qs = SafetyAlert.objects.select_related('prescription__medical_record__patient')
        if user.role == 'doctor':
            qs = qs.filter(prescription__medical_record__doctor=user)
        if self.request.query_params.get('open') in ('1', 'true'):
            qs = qs.filter(acknowledged_at__isnull=True)
        return qs

    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        alert = self.get_object()
        note = (request.data.get('note') or '').strip()
        if alert.severity == 'critical' and not note:
            return Response({'error': 'A note explaining the clinical decision is required for critical alerts.'},
                            status=status.HTTP_400_BAD_REQUEST)
        alert.acknowledged_by = request.user
        alert.acknowledged_at = timezone.now()
        alert.acknowledgement_note = note
        alert.save(update_fields=['acknowledged_by', 'acknowledged_at', 'acknowledgement_note'])
        return Response(SafetyAlertSerializer(alert).data)


@api_view(['POST'])
@permission_classes([IsDoctorOrAdmin])
def prescription_check(request):
    """Pre-save check so the doctor sees problems *before* prescribing."""
    data = PrescriptionCheckSerializer(data=request.data)
    data.is_valid(raise_exception=True)
    v = data.validated_data
    try:
        patient = get_patient_for(request.user, v['patient'])
    except AccessDenied as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    findings = check_prescription(patient, v['medication_name'], v['dosage'], v['frequency'])
    return Response({
        'findings': [f.to_dict() for f in findings],
        'highest_severity': findings[0].severity if findings else 'none',
        'disclaimer': 'Clinical decision support only. The knowledge base is not exhaustive; '
                      'the prescriber remains responsible for the decision.',
    })


@api_view(['GET', 'POST'])
@permission_classes([IsDoctorOrAdmin])
def appointment_brief(request, appointment_id):
    appt = get_object_or_404(Appointment.objects.select_related('patient'), pk=appointment_id)
    if request.user.role == 'doctor' and appt.doctor_id != request.user.id:
        return Response({'error': 'Not your appointment'}, status=status.HTTP_403_FORBIDDEN)
    brief = generate_brief(appt, force=request.method == 'POST')
    return Response(ClinicalBriefSerializer(brief).data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def lab_insight(request, lab_test_id):
    lab = get_object_or_404(LabTest.objects.select_related('medical_record'), pk=lab_test_id)
    user, record = request.user, lab.medical_record
    allowed = user.role == 'admin' or record.patient_id == user.id or record.doctor_id == user.id
    if not allowed:
        return Response({'error': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)
    if lab.status != 'completed':
        return Response({'error': 'Result not available yet'}, status=status.HTTP_404_NOT_FOUND)
    insight = LabInsight.objects.filter(lab_test=lab).first() or explain_lab(lab, notify=False)
    return Response(LabInsightSerializer(insight).data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
@throttle_classes([AIRateThrottle])
def claim_precheck(request, claim_id):
    claim = get_object_or_404(InsuranceClaim.objects.select_related('invoice', 'patient__patient_profile'), pk=claim_id)
    return Response(precheck_claim(claim))


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Notification.objects.filter(user=self.request.user)
        if self.request.query_params.get('unread') in ('1', 'true'):
            qs = qs.filter(read_at__isnull=True)
        return qs

    @action(detail=True, methods=['post'])
    def read(self, request, pk=None):
        n = get_object_or_404(self.get_queryset(), pk=pk)
        n.read_at = n.read_at or timezone.now()
        n.save(update_fields=['read_at'])
        return Response({'status': 'read'})

    @action(detail=False, methods=['post'])
    def read_all(self, request):
        self.get_queryset().filter(read_at__isnull=True).update(read_at=timezone.now())
        return Response({'status': 'ok'})


class AuditLogViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = ToolCallSerializer
    permission_classes = [IsAdminUser]
    filterset_fields = ['agent', 'tool_name', 'status', 'user']
    queryset = AgentToolCall.objects.select_related('user')


@api_view(['POST'])
@permission_classes([IsAdminUser])
def run_agent(request, name):
    """Manually trigger a background agent (handy for demos)."""
    from .proactive import run_care_followups, run_collections
    from .tasks import generate_upcoming_briefs
    runners = {
        'collections': run_collections,
        'care-followups': run_care_followups,
        'briefs': lambda: generate_upcoming_briefs(),
    }
    if name not in runners:
        return Response({'error': f'Unknown agent {name}'}, status=status.HTTP_404_NOT_FOUND)
    return Response({'agent': name, 'result': runners[name]()})
