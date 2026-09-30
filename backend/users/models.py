from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom User model with role-based access"""
    
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('doctor', 'Doctor'),
        ('patient', 'Patient'),
    )
    
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    phone = models.CharField(max_length=15, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"
    
    class Meta:
        ordering = ['-created_at']


class DoctorProfile(models.Model):
    """Extended profile for doctors"""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='doctor_profile')
    specialization = models.CharField(max_length=100)
    license_number = models.CharField(max_length=50, unique=True)
    experience_years = models.PositiveIntegerField(default=0)
    consultation_fee = models.DecimalField(max_digits=10, decimal_places=2)
    available_days = models.JSONField(default=list)  # List of available days
    available_hours = models.JSONField(default=dict)  # Time slots for each day
    bio = models.TextField(blank=True)
    
    def __str__(self):
        return f"Dr. {self.user.get_full_name()} - {self.specialization}"
    
    class Meta:
        ordering = ['specialization']


class PatientProfile(models.Model):
    """Extended profile for patients"""
    
    BLOOD_GROUP_CHOICES = (
        ('A+', 'A+'),
        ('A-', 'A-'),
        ('B+', 'B+'),
        ('B-', 'B-'),
        ('AB+', 'AB+'),
        ('AB-', 'AB-'),
        ('O+', 'O+'),
        ('O-', 'O-'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES, blank=True)
    emergency_contact = models.CharField(max_length=15, blank=True, default='')
    emergency_contact_name = models.CharField(max_length=100, blank=True, default='')
    allergies = models.TextField(blank=True)
    chronic_conditions = models.TextField(blank=True)
    insurance_provider = models.CharField(max_length=100, blank=True)
    insurance_number = models.CharField(max_length=50, blank=True)
    
    def __str__(self):
        return f"{self.user.get_full_name()}"
    
    class Meta:
        ordering = ['user__last_name']
