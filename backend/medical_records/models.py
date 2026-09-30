from django.db import models
from users.models import User
from appointments.models import Appointment


class MedicalRecord(models.Model):
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='medical_records')
    doctor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_records')
    appointment = models.OneToOneField(Appointment, on_delete=models.SET_NULL, null=True, blank=True)
    diagnosis = models.TextField()
    symptoms = models.TextField()
    treatment_plan = models.TextField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Record for {self.patient.get_full_name()} - {self.created_at.date()}"


class Prescription(models.Model):
    medical_record = models.ForeignKey(MedicalRecord, on_delete=models.CASCADE, related_name='prescriptions')
    medication_name = models.CharField(max_length=200)
    dosage = models.CharField(max_length=100)
    frequency = models.CharField(max_length=100)
    duration = models.CharField(max_length=100)
    instructions = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.medication_name} - {self.dosage}"


class LabTest(models.Model):
    STATUS_CHOICES = (
        ('ordered', 'Ordered'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    medical_record = models.ForeignKey(MedicalRecord, on_delete=models.CASCADE, related_name='lab_tests')
    test_name = models.CharField(max_length=200)
    test_type = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ordered')
    result = models.TextField(blank=True)
    result_file = models.FileField(upload_to='lab_results/', null=True, blank=True)
    ordered_date = models.DateTimeField(auto_now_add=True)
    completed_date = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-ordered_date']
    
    def __str__(self):
        return f"{self.test_name} - {self.status}"


class VitalSigns(models.Model):
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vital_signs')
    recorded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recorded_vitals')
    blood_pressure_systolic = models.IntegerField(null=True, blank=True)
    blood_pressure_diastolic = models.IntegerField(null=True, blank=True)
    heart_rate = models.IntegerField(null=True, blank=True)  # bpm
    temperature = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)  # Celsius
    respiratory_rate = models.IntegerField(null=True, blank=True)  # breaths per minute
    oxygen_saturation = models.IntegerField(null=True, blank=True)  # percentage
    weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # kg
    height = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # cm
    notes = models.TextField(blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-recorded_at']
        verbose_name_plural = 'Vital Signs'
    
    def __str__(self):
        return f"Vitals for {self.patient.get_full_name()} - {self.recorded_at.date()}"
