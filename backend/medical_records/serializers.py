from rest_framework import serializers
from .models import MedicalRecord, Prescription, LabTest, VitalSigns
from users.serializers import UserSerializer


class PrescriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prescription
        fields = ['id', 'medical_record', 'medication_name', 'dosage', 
                  'frequency', 'duration', 'instructions', 'created_at']
        read_only_fields = ['id', 'created_at']


class LabTestSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabTest
        fields = ['id', 'medical_record', 'test_name', 'test_type', 'status', 
                  'result', 'result_file', 'ordered_date', 'completed_date', 'notes']
        read_only_fields = ['id', 'ordered_date']


class MedicalRecordSerializer(serializers.ModelSerializer):
    patient_details = UserSerializer(source='patient', read_only=True)
    doctor_details = UserSerializer(source='doctor', read_only=True)
    prescriptions = PrescriptionSerializer(many=True, read_only=True)
    lab_tests = LabTestSerializer(many=True, read_only=True)
    
    class Meta:
        model = MedicalRecord
        fields = ['id', 'patient', 'doctor', 'patient_details', 'doctor_details',
                  'appointment', 'diagnosis', 'symptoms', 'treatment_plan', 
                  'notes', 'prescriptions', 'lab_tests', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class VitalSignsSerializer(serializers.ModelSerializer):
    patient_details = UserSerializer(source='patient', read_only=True)
    recorded_by_details = UserSerializer(source='recorded_by', read_only=True)
    
    class Meta:
        model = VitalSigns
        fields = ['id', 'patient', 'patient_details', 'recorded_by', 'recorded_by_details',
                  'blood_pressure_systolic', 'blood_pressure_diastolic', 'heart_rate',
                  'temperature', 'respiratory_rate', 'oxygen_saturation', 
                  'weight', 'height', 'notes', 'recorded_at']
        read_only_fields = ['id', 'recorded_at']
