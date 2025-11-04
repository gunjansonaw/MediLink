from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import MedicalRecord, Prescription, LabTest, VitalSigns
from .serializers import (
    MedicalRecordSerializer, PrescriptionSerializer, 
    LabTestSerializer, VitalSignsSerializer
)
from users.permissions import IsDoctorOrAdmin


class MedicalRecordViewSet(viewsets.ModelViewSet):
    queryset = MedicalRecord.objects.all()
    serializer_class = MedicalRecordSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['patient', 'doctor']
    search_fields = ['diagnosis', 'symptoms', 'patient__first_name', 'patient__last_name']
    ordering_fields = ['created_at', 'updated_at']
    
    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return MedicalRecord.objects.all()
        elif user.role == 'doctor':
            return MedicalRecord.objects.filter(doctor=user)
        elif user.role == 'patient':
            return MedicalRecord.objects.filter(patient=user)
        return MedicalRecord.objects.none()
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsDoctorOrAdmin()]
        return [permissions.IsAuthenticated()]
    
    def perform_create(self, serializer):
        serializer.save(doctor=self.request.user)
    
    @action(detail=False, methods=['get'])
    def my_records(self, request):
        if request.user.role != 'patient':
            return Response(
                {'error': 'Only patients can access this endpoint'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        records = MedicalRecord.objects.filter(patient=request.user)
        serializer = self.get_serializer(records, many=True)
        return Response(serializer.data)


class PrescriptionViewSet(viewsets.ModelViewSet):
    queryset = Prescription.objects.all()
    serializer_class = PrescriptionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['medical_record']
    
    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return Prescription.objects.all()
        elif user.role == 'doctor':
            return Prescription.objects.filter(medical_record__doctor=user)
        elif user.role == 'patient':
            return Prescription.objects.filter(medical_record__patient=user)
        return Prescription.objects.none()
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsDoctorOrAdmin()]
        return [permissions.IsAuthenticated()]


class LabTestViewSet(viewsets.ModelViewSet):
    queryset = LabTest.objects.all()
    serializer_class = LabTestSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['medical_record', 'status', 'test_type']
    
    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return LabTest.objects.all()
        elif user.role == 'doctor':
            return LabTest.objects.filter(medical_record__doctor=user)
        elif user.role == 'patient':
            return LabTest.objects.filter(medical_record__patient=user)
        return LabTest.objects.none()
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsDoctorOrAdmin()]
        return [permissions.IsAuthenticated()]
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        lab_test = self.get_object()
        if request.user.role not in ['doctor', 'admin']:
            return Response(
                {'error': 'Only doctors or admins can complete lab tests'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        from django.utils import timezone
        lab_test.status = 'completed'
        lab_test.completed_date = timezone.now()
        lab_test.save()
        return Response({'status': 'Lab test completed'})


class VitalSignsViewSet(viewsets.ModelViewSet):
    queryset = VitalSigns.objects.all()
    serializer_class = VitalSignsSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['patient']
    ordering_fields = ['recorded_at']
    
    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return VitalSigns.objects.all()
        elif user.role == 'doctor':
            return VitalSigns.objects.all()
        elif user.role == 'patient':
            return VitalSigns.objects.filter(patient=user)
        return VitalSigns.objects.none()
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsDoctorOrAdmin()]
        return [permissions.IsAuthenticated()]
    
    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)
