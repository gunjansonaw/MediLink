from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse
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
        base_qs = Invoice.objects.select_related(
            'patient', 'appointment', 'patient__patient_profile'
        ).prefetch_related('items', 'payments')

        if user.role == 'admin':
            return base_qs.all()
        elif user.role == 'patient':
            return base_qs.filter(patient=user)
        elif user.role == 'doctor':
            return base_qs.filter(appointment__doctor=user)
        return Invoice.objects.none()
    
    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
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

    @action(detail=True, methods=['get'])
    def download_pdf(self, request, pk=None):
        invoice = self.get_object()
        
        # Format HTML invoice document ready for print / save as PDF
        items_html = "".join([
            f"<tr><td style='padding:8px;border-bottom:1px solid #eee;'>{item.description}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:center;'>{item.quantity}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:right;'>${float(item.unit_price):.2f}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:right;'>${float(item.total):.2f}</td></tr>"
            for item in invoice.items.all()
        ])

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Invoice {invoice.invoice_number} - MediLink</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333; margin: 40px; background: #fff; }}
        .header {{ display: flex; justify-content: space-between; border-bottom: 2px solid #1890ff; padding-bottom: 20px; }}
        .brand {{ font-size: 28px; font-weight: bold; color: #1890ff; }}
        .badge {{ display: inline-block; padding: 4px 12px; border-radius: 4px; font-size: 13px; font-weight: bold; text-transform: uppercase; }}
        .paid {{ background: #e6f7ff; color: #1890ff; border: 1px solid #91d5ff; }}
        .table {{ width: 100%; border-collapse: collapse; margin-top: 30px; }}
        .table th {{ background: #fafafa; padding: 10px 8px; text-align: left; border-bottom: 2px solid #e8e8e8; }}
        .summary {{ width: 300px; margin-left: auto; margin-top: 30px; }}
        .summary-row {{ display: flex; justify-content: space-between; padding: 6px 0; }}
        .total-row {{ font-weight: bold; font-size: 18px; border-top: 2px solid #1890ff; padding-top: 8px; color: #1890ff; }}
        @media print {{ body {{ margin: 0; }} }}
    </style>
</head>
<body onload="window.print()">
    <div class="header">
        <div>
            <div class="brand">MediLink SaaS Health</div>
            <p style="color: #666; margin-top: 4px;">Smart Healthcare Management Platform</p>
        </div>
        <div style="text-align: right;">
            <h2 style="margin: 0; color: #333;">INVOICE</h2>
            <p style="margin: 4px 0;"><strong>Invoice #:</strong> {invoice.invoice_number}</p>
            <p style="margin: 4px 0;"><strong>Date:</strong> {invoice.invoice_date}</p>
            <p style="margin: 4px 0;"><strong>Due Date:</strong> {invoice.due_date}</p>
            <p style="margin: 4px 0;"><strong>Status:</strong> <span class="badge paid">{invoice.status}</span></p>
        </div>
    </div>

    <div style="margin-top: 30px; display: flex; justify-content: space-between;">
        <div>
            <strong>Billed To:</strong><br>
            {invoice.patient.get_full_name()}<br>
            Email: {invoice.patient.email}<br>
            Phone: {invoice.patient.phone or 'N/A'}
        </div>
        <div>
            <strong>Provider:</strong><br>
            MediLink Telehealth Network<br>
            support@medilink.health<br>
            +1 (800) 555-MEDI
        </div>
    </div>

    <table class="table">
        <thead>
            <tr>
                <th>Description</th>
                <th style="text-align: center;">Qty</th>
                <th style="text-align: right;">Unit Price</th>
                <th style="text-align: right;">Total</th>
            </tr>
        </thead>
        <tbody>
            {items_html if items_html else "<tr><td colspan='4' style='padding:12px;text-align:center;'>Consultation and General Medical Services</td></tr>"}
        </tbody>
    </table>

    <div class="summary">
        <div class="summary-row"><span>Subtotal:</span><span>${float(invoice.subtotal):.2f}</span></div>
        <div class="summary-row"><span>Tax:</span><span>${float(invoice.tax):.2f}</span></div>
        <div class="summary-row"><span>Discount:</span><span>-${float(invoice.discount):.2f}</span></div>
        <div class="summary-row total-row"><span>Total:</span><span>${float(invoice.total):.2f}</span></div>
        <div class="summary-row" style="color:#52c41a;"><span>Amount Paid:</span><span>${float(invoice.total_paid):.2f}</span></div>
        <div class="summary-row" style="color:#ff4d4f;font-weight:bold;"><span>Amount Due:</span><span>${float(invoice.remaining_balance):.2f}</span></div>
    </div>

    <div style="margin-top: 50px; border-top: 1px solid #eee; padding-top: 20px; font-size: 12px; color: #888; text-align: center;">
        Thank you for choosing MediLink. For billing inquiries, contact billing@medilink.health.
    </div>
</body>
</html>"""
        response = HttpResponse(html_content, content_type='text/html')
        response['Content-Disposition'] = f'inline; filename="invoice_{invoice.invoice_number}.html"'
        return response
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        if request.user.role != 'admin':
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        queryset = self.get_queryset()
        
        total_revenue = queryset.filter(status='paid').aggregate(
            Sum('total')
        )['total__sum'] or 0
        
        pending_amount = queryset.filter(status__in=['pending', 'partially_paid']).aggregate(
            Sum('total')
        )['total__sum'] or 0
        
        # Monthly revenue for last 6 months
        monthly_revenue = []
        today = timezone.now().date()
        for i in range(6):
            month_start = (today.replace(day=1) - timedelta(days=i*30)).replace(day=1)
            next_month = (month_start + timedelta(days=32)).replace(day=1)
            
            revenue = queryset.filter(
                invoice_date__gte=month_start,
                invoice_date__lt=next_month,
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
            'partially_paid_invoices': queryset.filter(status='partially_paid').count(),
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
        base_qs = Payment.objects.select_related('invoice', 'invoice__patient')
        if user.role == 'admin':
            return base_qs.all()
        elif user.role == 'patient':
            return base_qs.filter(invoice__patient=user)
        return Payment.objects.none()
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]
    
    def perform_create(self, serializer):
        invoice = serializer.validated_data.get('invoice')
        user = self.request.user

        if user.role == 'patient' and invoice.patient != user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Patients can only pay their own invoices')

        payment = serializer.save()

        # Update invoice payment status automatically via sync_payment_status
        invoice.sync_payment_status()


class InsuranceClaimViewSet(viewsets.ModelViewSet):
    queryset = InsuranceClaim.objects.all()
    serializer_class = InsuranceClaimSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['patient', 'status', 'insurance_provider']
    search_fields = ['claim_number', 'patient__first_name', 'patient__last_name']
    ordering_fields = ['submitted_date', 'processed_date']
    
    def get_queryset(self):
        user = self.request.user
        base_qs = InsuranceClaim.objects.select_related('patient', 'invoice')
        if user.role == 'admin':
            return base_qs.all()
        elif user.role == 'patient':
            return base_qs.filter(patient=user)
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
                {'error': 'approved_amount is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        claim.status = 'approved'
        claim.approved_amount = approved_amount
        claim.processed_date = timezone.now().date()
        claim.save()
        
        return Response({'status': 'Claim approved'})
