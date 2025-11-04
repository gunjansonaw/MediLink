from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from .models import User, DoctorProfile, PatientProfile
from .serializers import (
    UserSerializer, UserRegistrationSerializer, 
    UserUpdateSerializer, DoctorProfileSerializer, PatientProfileSerializer
)
from .permissions import IsOwnerOrAdmin, IsDoctorOrAdmin, IsAdminUser


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            return [IsOwnerOrAdmin()]
        return [permissions.IsAuthenticated()]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return UserRegistrationSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        return UserSerializer
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def login(self, request):
        username_or_email = request.data.get('username')
        password = request.data.get('password')

        if not username_or_email or not password:
            return Response(
                {'error': 'Username (or email) and password are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Allow login with either username or email
        auth_username = username_or_email
        if '@' in username_or_email:
            try:
                from django.contrib.auth import get_user_model
                UserModel = get_user_model()
                matched_user = UserModel.objects.filter(email__iexact=username_or_email).first()
                if matched_user:
                    auth_username = matched_user.get_username()
            except Exception:
                pass

        user = authenticate(username=auth_username, password=password)

        if user:
            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': UserSerializer(user).data
            })
        
        return Response(
            {'error': 'Invalid credentials'}, 
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def doctors(self, request):
        doctors = User.objects.filter(role='doctor').select_related('doctor_profile')
        serializer = self.get_serializer(doctors, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def patients(self, request):
        if request.user.role not in ['admin', 'doctor']:
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        patients = User.objects.filter(role='patient').select_related('patient_profile')
        serializer = self.get_serializer(patients, many=True)
        return Response(serializer.data)
