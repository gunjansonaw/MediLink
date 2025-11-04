from django.contrib import admin
from .models import MedicalRecord, Prescription, LabTest, VitalSigns


class PrescriptionInline(admin.TabularInline):
    model = Prescription
    extra = 1


class LabTestInline(admin.TabularInline):
    model = LabTest
    extra = 1


@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ['patient', 'doctor', 'created_at', 'diagnosis']
    list_filter = ['created_at', 'doctor']
    search_fields = ['patient__username', 'doctor__username', 'diagnosis']
    date_hierarchy = 'created_at'
    inlines = [PrescriptionInline, LabTestInline]


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ['medication_name', 'dosage', 'frequency', 'duration']
    search_fields = ['medication_name', 'medical_record__patient__username']


@admin.register(LabTest)
class LabTestAdmin(admin.ModelAdmin):
    list_display = ['test_name', 'test_type', 'status', 'ordered_date', 'completed_date']
    list_filter = ['status', 'test_type', 'ordered_date']
    search_fields = ['test_name', 'medical_record__patient__username']


@admin.register(VitalSigns)
class VitalSignsAdmin(admin.ModelAdmin):
    list_display = ['patient', 'blood_pressure_systolic', 'blood_pressure_diastolic', 
                    'heart_rate', 'temperature', 'recorded_at']
    list_filter = ['recorded_at']
    search_fields = ['patient__username']
