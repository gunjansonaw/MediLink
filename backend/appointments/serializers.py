from datetime import datetime, timedelta

from django.utils import timezone
from rest_framework import serializers

from users.models import User
from users.serializers import UserSerializer
from .models import Appointment, Schedule


class AppointmentSerializer(serializers.ModelSerializer):
    patient_details = UserSerializer(source='patient', read_only=True)
    doctor_details = UserSerializer(source='doctor', read_only=True)
    patient = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='patient'), required=False
    )
    doctor = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role='doctor'))

    class Meta:
        model = Appointment
        fields = ['id', 'patient', 'doctor', 'patient_details', 'doctor_details',
                  'appointment_date', 'appointment_time', 'duration_minutes',
                  'status', 'reason', 'notes', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'status']

    def validate_duration_minutes(self, value):
        if not 5 <= value <= 240:
            raise serializers.ValidationError('Duration must be between 5 and 240 minutes.')
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        user = getattr(request, 'user', None)

        doctor = attrs.get('doctor', getattr(self.instance, 'doctor', None))
        appointment_date = attrs.get('appointment_date', getattr(self.instance, 'appointment_date', None))
        appointment_time = attrs.get('appointment_time', getattr(self.instance, 'appointment_time', None))

        # Patients always book for themselves; staff must say who the patient is.
        if self.instance is None and user is not None and user.role != 'patient' and not attrs.get('patient'):
            raise serializers.ValidationError({'patient': 'This field is required.'})

        # Cannot book (or move a booking) into the past.
        if 'appointment_date' in attrs or 'appointment_time' in attrs or self.instance is None:
            slot = timezone.make_aware(datetime.combine(appointment_date, appointment_time))
            if slot < timezone.now() - timedelta(minutes=1):
                raise serializers.ValidationError({'appointment_date': 'Appointments cannot be booked in the past.'})

        conflicting = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            status__in=Appointment.ACTIVE_STATUSES,
        )
        if self.instance:
            conflicting = conflicting.exclude(id=self.instance.id)
        if conflicting.exists():
            raise serializers.ValidationError({'detail': 'This time slot is already booked.'})

        return attrs


class ScheduleSerializer(serializers.ModelSerializer):
    doctor_details = UserSerializer(source='doctor', read_only=True)
    doctor = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='doctor'), required=False
    )

    class Meta:
        model = Schedule
        fields = ['id', 'doctor', 'doctor_details', 'day_of_week',
                  'start_time', 'end_time', 'is_active']
        read_only_fields = ['id']

    def validate(self, attrs):
        start = attrs.get('start_time', getattr(self.instance, 'start_time', None))
        end = attrs.get('end_time', getattr(self.instance, 'end_time', None))
        if start and end and start >= end:
            raise serializers.ValidationError({'end_time': 'End time must be after start time.'})
        return attrs
