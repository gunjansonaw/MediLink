from rest_framework import serializers
from .models import Appointment, Schedule
from users.serializers import UserSerializer


class AppointmentSerializer(serializers.ModelSerializer):
    patient_details = UserSerializer(source='patient', read_only=True)
    doctor_details = UserSerializer(source='doctor', read_only=True)
    
    class Meta:
        model = Appointment
        fields = ['id', 'patient', 'doctor', 'patient_details', 'doctor_details',
                  'appointment_date', 'appointment_time', 'duration_minutes', 
                  'status', 'reason', 'notes', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'patient']
    
    def validate(self, attrs):
        # Get doctor from attrs, patient from request context if available
        doctor = attrs.get('doctor')
        appointment_date = attrs.get('appointment_date')
        appointment_time = attrs.get('appointment_time')
        
        # Check for conflicting appointments
        conflicting = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            status__in=['scheduled', 'confirmed']
        )
        
        # Exclude current appointment when updating
        if self.instance:
            conflicting = conflicting.exclude(id=self.instance.id)
        
        if conflicting.exists():
            raise serializers.ValidationError("This time slot is already booked.")
        
        return attrs


class ScheduleSerializer(serializers.ModelSerializer):
    doctor_details = UserSerializer(source='doctor', read_only=True)
    
    class Meta:
        model = Schedule
        fields = ['id', 'doctor', 'doctor_details', 'day_of_week', 
                  'start_time', 'end_time', 'is_active']
        read_only_fields = ['id']
