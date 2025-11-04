from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Sum, Count, Q
from datetime import timedelta
from .models import Invoice, InvoiceItem, Payment, InsuranceClaim
from .serializers import (
    InvoiceSerializer, InvoiceItemSerializer, 
    PaymentSerializer, InsuranceClaimSerializer
)
from users.permissions import IsAdminUser


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['patient', 'status', 'invoice_date']
    search_fields = ['invoice_number', 'patient__first_name', 'patient__last_name']
    ordering_fields = ['invoice_date', 'due_date', 'total']
    
    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return Invoice.objects.all()
        elif user.role == 'patient':
            return Invoice.objects.filter(patient=user)
        elif user.role == 'doctor':
            # Doctors can see invoices for their appointments
            return Invoice.objects.filter(appointment__doctor=user)
        return Invoice.objects.none()
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [permissions.IsAuthenticated()]
    
    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        if request.user.role != 'admin':
            return Response(
                {'error': 'Only admins can mark invoices as paid'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        invoice = self.get_object()
        invoice.status = 'paid'
        invoice.save()
        return Response({'status': 'Invoice marked as paid'})
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        if request.user.role != 'admin':
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        queryset = self.get_queryset()
        today = timezone.now().date()
        
        # Calculate total revenue
        total_revenue = queryset.filter(status='paid').aggregate(Sum('total'))['total__sum'] or 0
        
        # Pending amount
        pending_amount = queryset.filter(status='pending').aggregate(Sum('total'))['total__sum'] or 0
        
        # Monthly revenue (last 6 months)
        monthly_revenue = []
        for i in range(6):
            month_start = today.replace(day=1) - timedelta(days=30*i)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            revenue = queryset.filter(
                invoice_date__gte=month_start,
                invoice_date__lte=month_end,
                status='paid'
            ).aggregate(Sum('total'))['total__sum'] or 0
            
            monthly_revenue.insert(0, {
                'month': month_start.strftime('%B %Y'),
                'revenue': float(revenue)
            })
        
        stats = {
            'total_invoices': queryset.count(),
            'total_revenue': float(total_revenue),
            'pending_amount': float(pending_amount),
            'paid_invoices': queryset.filter(status='paid').count(),
            'pending_invoices': queryset.filter(status='pending').count(),
            'overdue_invoices': queryset.filter(status='overdue').count(),
            'monthly_revenue': monthly_revenue,
        }
        
        return Response(stats)


class InvoiceItemViewSet(viewsets.ModelViewSet):
    queryset = InvoiceItem.objects.all()
    serializer_class = InvoiceItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['invoice']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [permissions.IsAuthenticated()]


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['invoice', 'payment_method']
    ordering_fields = ['payment_date', 'amount']
    
    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return Payment.objects.all()
        elif user.role == 'patient':
            return Payment.objects.filter(invoice__patient=user)
        return Payment.objects.none()
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [permissions.IsAuthenticated()]
    
    def perform_create(self, serializer):
        payment = serializer.save()
        
        # Check if invoice is fully paid
        invoice = payment.invoice
        total_paid = invoice.payments.aggregate(Sum('amount'))['amount__sum'] or 0
        
        if total_paid >= invoice.total:
            invoice.status = 'paid'
            invoice.save()


class InsuranceClaimViewSet(viewsets.ModelViewSet):
    queryset = InsuranceClaim.objects.all()
    serializer_class = InsuranceClaimSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['patient', 'status', 'insurance_provider']
    search_fields = ['claim_number', 'patient__first_name', 'patient__last_name']
    ordering_fields = ['submitted_date', 'processed_date']
    
    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return InsuranceClaim.objects.all()
        elif user.role == 'patient':
            return InsuranceClaim.objects.filter(patient=user)
        return InsuranceClaim.objects.none()
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        if request.user.role != 'admin':
            return Response(
                {'error': 'Only admins can approve claims'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        claim = self.get_object()
        approved_amount = request.data.get('approved_amount')
        
        if not approved_amount:
            return Response(
                {'error': 'Approved amount is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        claim.status = 'approved'
        claim.approved_amount = approved_amount
        claim.processed_date = timezone.now().date()
        claim.save()
        
        return Response({'status': 'Claim approved'})
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        if request.user.role != 'admin':
            return Response(
                {'error': 'Only admins can reject claims'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        claim = self.get_object()
        claim.status = 'rejected'
        claim.processed_date = timezone.now().date()
        claim.save()
        
        return Response({'status': 'Claim rejected'})
