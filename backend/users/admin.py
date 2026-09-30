from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, DoctorProfile, PatientProfile


class DoctorProfileInline(admin.StackedInline):
    model = DoctorProfile
    can_delete = False


class PatientProfileInline(admin.StackedInline):
    model = PatientProfile
    can_delete = False


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'role', 'is_active']
    list_filter = ['role', 'is_active', 'is_staff']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('role', 'phone', 'date_of_birth', 'address', 'profile_picture')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Additional Info', {'fields': ('role', 'phone', 'date_of_birth', 'address')}),
    )
    
    def get_inline_instances(self, request, obj=None):
        if not obj:
            return []
        
        inlines = []
        if obj.role == 'doctor':
            inlines.append(DoctorProfileInline(self.model, self.admin_site))
        elif obj.role == 'patient':
            inlines.append(PatientProfileInline(self.model, self.admin_site))
        
        return inlines


@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'specialization', 'license_number', 'consultation_fee']
    search_fields = ['user__username', 'specialization', 'license_number']


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'blood_group', 'emergency_contact']
    search_fields = ['user__username', 'blood_group']
