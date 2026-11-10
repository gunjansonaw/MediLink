from rest_framework import serializers

from users.models import User
from users.serializers import UserSerializer
from .models import MedicalRecord, Prescription, LabTest, VitalSigns


def _record_is_writable_by(user, record):
    return user.role == 'admin' or (user.role == 'doctor' and record.doctor_id == user.id)


class PrescriptionSerializer(serializers.ModelSerializer):
    safety_alerts = serializers.SerializerMethodField()

    class Meta:
        model = Prescription
        fields = ['id', 'medical_record', 'medication_name', 'dosage',
                  'frequency', 'duration', 'instructions', 'created_at', 'safety_alerts']
        read_only_fields = ['id', 'created_at', 'safety_alerts']

    def get_safety_alerts(self, obj):
        alerts = getattr(obj, 'safety_alerts', None)
        if alerts is None:
            return []
        return [
            {'id': a.id, 'severity': a.severity, 'category': a.category,
             'message': a.message, 'acknowledged': a.acknowledged_at is not None}
            for a in alerts.all()
        ]

    def validate_medical_record(self, record):
        request = self.context.get('request')
        if request and not _record_is_writable_by(request.user, record):
            raise serializers.ValidationError('You can only add prescriptions to your own medical records.')
        return record


class LabTestSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabTest
        fields = ['id', 'medical_record', 'test_name', 'test_type', 'status',
                  'result', 'result_file', 'ordered_date', 'completed_date', 'notes']
        read_only_fields = ['id', 'ordered_date', 'completed_date']

    def validate_medical_record(self, record):
        request = self.context.get('request')
        if request and not _record_is_writable_by(request.user, record):
            raise serializers.ValidationError('You can only order lab tests on your own medical records.')
        return record


class MedicalRecordSerializer(serializers.ModelSerializer):
    patient_details = UserSerializer(source='patient', read_only=True)
    doctor_details = UserSerializer(source='doctor', read_only=True)
    prescriptions = PrescriptionSerializer(many=True, read_only=True)
    lab_tests = LabTestSerializer(many=True, read_only=True)
    patient = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role='patient'))
    # Doctors are taken from the request; admins must name one explicitly.
    doctor = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role='doctor'), required=False)

    class Meta:
        model = MedicalRecord
        fields = ['id', 'patient', 'doctor', 'patient_details', 'doctor_details',
                  'appointment', 'diagnosis', 'symptoms', 'treatment_plan',
                  'notes', 'prescriptions', 'lab_tests', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if self.instance is None and user is not None and user.role == 'admin' and not attrs.get('doctor'):
            raise serializers.ValidationError({'doctor': 'This field is required.'})
        appointment = attrs.get('appointment')
        patient = attrs.get('patient', getattr(self.instance, 'patient', None))
        if appointment and patient and appointment.patient_id != patient.id:
            raise serializers.ValidationError({'appointment': 'Appointment belongs to a different patient.'})
        return attrs


class VitalSignsSerializer(serializers.ModelSerializer):
    patient_details = UserSerializer(source='patient', read_only=True)
    recorded_by_details = UserSerializer(source='recorded_by', read_only=True)
    patient = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role='patient'))

    class Meta:
        model = VitalSigns
        fields = ['id', 'patient', 'patient_details', 'recorded_by', 'recorded_by_details',
                  'blood_pressure_systolic', 'blood_pressure_diastolic', 'heart_rate',
                  'temperature', 'respiratory_rate', 'oxygen_saturation',
                  'weight', 'height', 'notes', 'recorded_at']
        # recorded_by is always the authenticated user
        read_only_fields = ['id', 'recorded_at', 'recorded_by']

    def validate(self, attrs):
        ranges = {
            'blood_pressure_systolic': (40, 300), 'blood_pressure_diastolic': (20, 200),
            'heart_rate': (20, 300), 'respiratory_rate': (4, 80), 'oxygen_saturation': (30, 100),
            'temperature': (25, 45), 'weight': (0.3, 500), 'height': (20, 260),
        }
        errors = {}
        for field, (lo, hi) in ranges.items():
            value = attrs.get(field)
            if value is not None and not lo <= float(value) <= hi:
                errors[field] = f'Must be between {lo} and {hi}.'
        if errors:
            raise serializers.ValidationError(errors)
        return attrs
