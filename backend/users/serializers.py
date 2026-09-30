from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User, DoctorProfile, PatientProfile


class DoctorProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorProfile
        fields = ['specialization', 'license_number', 'experience_years', 
                  'consultation_fee', 'available_days', 'available_hours', 'bio']


class PatientProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientProfile
        fields = ['blood_group', 'emergency_contact', 'emergency_contact_name', 
                  'allergies', 'chronic_conditions', 'insurance_provider', 'insurance_number']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make emergency fields optional when updating
        if self.instance:
            self.fields['emergency_contact'].required = False
            self.fields['emergency_contact_name'].required = False


class UserSerializer(serializers.ModelSerializer):
    doctor_profile = DoctorProfileSerializer(required=False)
    patient_profile = PatientProfileSerializer(required=False)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 
                  'phone', 'date_of_birth', 'address', 'profile_picture', 
                  'doctor_profile', 'patient_profile', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)
    doctor_profile = DoctorProfileSerializer(required=False)
    patient_profile = PatientProfileSerializer(required=False)
    
    class Meta:
        model = User
        fields = ['username', 'password', 'password2', 'email', 'first_name', 'last_name', 
                  'role', 'phone', 'date_of_birth', 'address', 'doctor_profile', 'patient_profile']
    
    def validate(self, attrs):
        # Prevent privilege escalation via public registration
        if attrs.get('role') == 'admin':
            raise serializers.ValidationError({
                "role": "Admin accounts cannot be registered via the public registration endpoint."
            })
        
        # Enforce password confirmation
        if attrs.get('password') != attrs.get('password2'):
            raise serializers.ValidationError({"password2": "Password fields did not match."})
        
        # Default role to patient if not specified or invalid
        if attrs.get('role') not in ['patient', 'doctor']:
            attrs['role'] = 'patient'
        
        # Validate role matches profile
        if 'doctor_profile' in attrs and attrs.get('role') != 'doctor':
            raise serializers.ValidationError({"doctor_profile": "Doctor profile can only be set for doctor role."})
        
        if 'patient_profile' in attrs and attrs.get('role') != 'patient':
            raise serializers.ValidationError({"patient_profile": "Patient profile can only be set for patient role."})
        
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password2', None)
        doctor_profile_data = validated_data.pop('doctor_profile', None)
        patient_profile_data = validated_data.pop('patient_profile', None)
        
        user = User.objects.create_user(**validated_data)
        
        if user.role == 'doctor':
            if not doctor_profile_data:
                doctor_profile_data = {
                    'specialization': 'General Medicine',
                    'license_number': f'MED-{user.id:06d}',
                    'experience_years': 1,
                    'consultation_fee': 50.00
                }
            DoctorProfile.objects.create(user=user, **doctor_profile_data)
        elif user.role == 'patient':
            if not patient_profile_data:
                patient_profile_data = {}
            if 'emergency_contact' not in patient_profile_data:
                patient_profile_data['emergency_contact'] = ''
            if 'emergency_contact_name' not in patient_profile_data:
                patient_profile_data['emergency_contact_name'] = ''
            PatientProfile.objects.create(user=user, **patient_profile_data)
        
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    doctor_profile = DoctorProfileSerializer(required=False)
    patient_profile = PatientProfileSerializer(required=False)
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone', 'date_of_birth', 'address', 
                  'profile_picture', 'doctor_profile', 'patient_profile']
    
    def update(self, instance, validated_data):
        doctor_profile_data = validated_data.pop('doctor_profile', None)
        patient_profile_data = validated_data.pop('patient_profile', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if instance.role == 'doctor' and doctor_profile_data:
            DoctorProfile.objects.update_or_create(user=instance, defaults=doctor_profile_data)
        elif instance.role == 'patient' and patient_profile_data:
            PatientProfile.objects.update_or_create(user=instance, defaults=patient_profile_data)
        
        return instance
