from datetime import date, timedelta

from django.db import IntegrityError
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from users.models import User
from users.permissions import IsDoctorOrAdmin
from .models import Appointment, Schedule
from .serializers import AppointmentSerializer, ScheduleSerializer
from .services import SlotUnavailable, available_slots, book_appointment

# Allowed status transitions: {from_status: {to_status, ...}}
TRANSITIONS = {
    'scheduled': {'confirmed', 'cancelled', 'completed', 'no_show'},
    'confirmed': {'cancelled', 'completed', 'no_show'},
    'completed': set(),
    'cancelled': set(),
    'no_show': set(),
}


def _transition(appointment, new_status):
    if new_status not in TRANSITIONS.get(appointment.status, set()):
        return Response(
            {'error': f'Cannot change appointment from {appointment.status} to {new_status}.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    appointment.status = new_status
    appointment.save(update_fields=['status', 'updated_at'])
    return None


class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['patient', 'doctor', 'status', 'appointment_date']
    search_fields = ['patient__first_name', 'patient__last_name', 'doctor__first_name', 'doctor__last_name']
    ordering_fields = ['appointment_date', 'appointment_time', 'created_at']

    def get_queryset(self):
        user = self.request.user
        base_qs = Appointment.objects.select_related(
            'patient', 'doctor', 'patient__patient_profile', 'doctor__doctor_profile'
        )
        if user.role == 'admin':
            return base_qs.all()
        elif user.role == 'doctor':
            return base_qs.filter(doctor=user)
        elif user.role == 'patient':
            return base_qs.filter(patient=user)
        return Appointment.objects.none()

    def get_permissions(self):
        if self.action == 'destroy':
            from users.permissions import IsAdminUser
            return [IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = request.user

        if user.role == 'patient':
            patient = user
        else:
            patient = data['patient']
            if user.role == 'doctor' and data['doctor'] != user:
                raise PermissionDenied('Doctors can only create appointments in their own calendar.')

        try:
            appointment = book_appointment(
                patient=patient,
                doctor=data['doctor'],
                appointment_date=data['appointment_date'],
                appointment_time=data['appointment_time'],
                reason=data['reason'],
                duration_minutes=data.get('duration_minutes', 30),
                notes=data.get('notes', ''),
            )
        except SlotUnavailable as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        _queue_reminder(appointment)
        out = self.get_serializer(appointment)
        return Response(out.data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        user = self.request.user
        instance = serializer.instance
        if instance.status not in Appointment.ACTIVE_STATUSES:
            raise serializers.ValidationError({'detail': f'A {instance.status} appointment cannot be edited.'})
        if user.role == 'patient':
            # Patients may reschedule / edit the reason, but never re-assign the
            # booking to another patient.
            serializer.validated_data.pop('patient', None)
        if user.role == 'doctor':
            new_doctor = serializer.validated_data.get('doctor')
            if new_doctor and new_doctor != user:
                raise PermissionDenied('Doctors cannot move appointments to another doctor.')
        try:
            serializer.save()
        except IntegrityError:
            raise serializers.ValidationError({'detail': 'This time slot is already booked.'})

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        appointment = self.get_object()
        if request.user.role not in ['doctor', 'admin']:
            return Response(
                {'error': 'Only doctors or admins can confirm appointments'},
                status=status.HTTP_403_FORBIDDEN
            )
        error = _transition(appointment, 'confirmed')
        return error or Response({'status': 'Appointment confirmed'})

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        appointment = self.get_object()
        error = _transition(appointment, 'cancelled')
        return error or Response({'status': 'Appointment cancelled'})

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        appointment = self.get_object()
        if request.user.role not in ['doctor', 'admin']:
            return Response(
                {'error': 'Only doctors or admins can mark appointments as completed'},
                status=status.HTTP_403_FORBIDDEN
            )
        error = _transition(appointment, 'completed')
        return error or Response({'status': 'Appointment completed'})

    @action(detail=True, methods=['post'])
    def no_show(self, request, pk=None):
        appointment = self.get_object()
        if request.user.role not in ['doctor', 'admin']:
            return Response({'error': 'Only doctors or admins can mark no-shows'}, status=status.HTTP_403_FORBIDDEN)
        error = _transition(appointment, 'no_show')
        return error or Response({'status': 'Appointment marked as no-show'})

    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        today = timezone.localdate()
        queryset = self.get_queryset().filter(
            appointment_date__gte=today,
            status__in=Appointment.ACTIVE_STATUSES,
        ).order_by('appointment_date', 'appointment_time')
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def available_slots(self, request):
        """GET ?doctor=<id>&start=YYYY-MM-DD&end=YYYY-MM-DD → free slots."""
        try:
            doctor = User.objects.select_related('doctor_profile').get(pk=request.query_params.get('doctor'), role='doctor')
        except (User.DoesNotExist, ValueError, TypeError):
            return Response({'error': 'Valid doctor id is required'}, status=status.HTTP_400_BAD_REQUEST)
        start = parse_date(request.query_params.get('start') or '') or timezone.localdate()
        end = parse_date(request.query_params.get('end') or '') or start + timedelta(days=6)
        if end < start:
            return Response({'error': 'end must be on or after start'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'doctor': doctor.id, 'slots': available_slots(doctor, start, end)})

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        if request.user.role not in ['doctor', 'admin']:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )

        queryset = self.get_queryset()
        today = timezone.localdate()

        stats = {
            'total': queryset.count(),
            'today': queryset.filter(appointment_date=today).count(),
            'scheduled': queryset.filter(status='scheduled').count(),
            'confirmed': queryset.filter(status='confirmed').count(),
            'completed': queryset.filter(status='completed').count(),
            'cancelled': queryset.filter(status='cancelled').count(),
            'no_show': queryset.filter(status='no_show').count(),
        }

        return Response(stats)


def _queue_reminder(appointment):
    """Fire-and-forget reminder; never let a broker outage break booking."""
    try:
        from billing.tasks import send_appointment_reminder_email
        send_appointment_reminder_email.delay(appointment.id)
    except Exception:  # pragma: no cover - broker unavailable
        import logging
        logging.getLogger(__name__).warning('Could not queue reminder for appointment %s', appointment.id)


class ScheduleViewSet(viewsets.ModelViewSet):
    queryset = Schedule.objects.all()
    serializer_class = ScheduleSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['doctor', 'day_of_week', 'is_active']

    def get_queryset(self):
        user = self.request.user
        base_qs = Schedule.objects.select_related('doctor', 'doctor__doctor_profile')
        if user.role == 'admin':
            return base_qs.all()
        elif user.role == 'doctor':
            return base_qs.filter(doctor=user)
        return base_qs.filter(is_active=True)

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsDoctorOrAdmin()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        user = self.request.user
        if user.role == 'doctor':
            serializer.save(doctor=user)  # doctors manage only their own schedule
        else:
            if not serializer.validated_data.get('doctor'):
                raise serializers.ValidationError({'doctor': 'This field is required.'})
            serializer.save()

    def perform_update(self, serializer):
        if self.request.user.role == 'doctor':
            serializer.save(doctor=self.request.user)
        else:
            serializer.save()
