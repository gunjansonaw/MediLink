from rest_framework import viewsets, permissions, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Appointment, Schedule
from .serializers import AppointmentSerializer, ScheduleSerializer
from users.permissions import IsDoctorOrAdmin


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
    
    def perform_create(self, serializer):
        user = self.request.user
        doctor = serializer.validated_data.get('doctor')
        appointment_date = serializer.validated_data.get('appointment_date')
        appointment_time = serializer.validated_data.get('appointment_time')

        # Double booking check
        if Appointment.objects.filter(
            doctor=doctor,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            status__in=['scheduled', 'confirmed']
        ).exists():
            raise serializers.ValidationError({"detail": "This doctor is already booked for this date and time slot."})

        if user.role == 'patient':
            serializer.save(patient=user)
        else:
            serializer.save()
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        appointment = self.get_object()
        if request.user.role not in ['doctor', 'admin']:
            return Response(
                {'error': 'Only doctors or admins can confirm appointments'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        appointment.status = 'confirmed'
        appointment.save()
        return Response({'status': 'Appointment confirmed'})
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        appointment = self.get_object()
        appointment.status = 'cancelled'
        appointment.save()
        return Response({'status': 'Appointment cancelled'})
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        appointment = self.get_object()
        if request.user.role not in ['doctor', 'admin']:
            return Response(
                {'error': 'Only doctors or admins can mark appointments as completed'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        appointment.status = 'completed'
        appointment.save()
        return Response({'status': 'Appointment completed'})
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        today = timezone.now().date()
        queryset = self.get_queryset().filter(
            appointment_date__gte=today,
            status__in=['scheduled', 'confirmed']
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        if request.user.role not in ['doctor', 'admin']:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        queryset = self.get_queryset()
        today = timezone.now().date()
        
        stats = {
            'total': queryset.count(),
            'today': queryset.filter(appointment_date=today).count(),
            'scheduled': queryset.filter(status='scheduled').count(),
            'confirmed': queryset.filter(status='confirmed').count(),
            'completed': queryset.filter(status='completed').count(),
            'cancelled': queryset.filter(status='cancelled').count(),
        }
        
        return Response(stats)


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
