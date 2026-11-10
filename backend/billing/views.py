import html
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from users.permissions import IsAdminUser
from .models import Invoice, InvoiceItem, Payment, InsuranceClaim
from .serializers import (
    InvoiceSerializer, InvoiceItemSerializer,
    PaymentSerializer, InsuranceClaimSerializer
)


def _month_starts(today, count):
    """First day of the current month and the (count-1) months before it, oldest first."""
    y, m = today.year, today.month
    out = []
    for _ in range(count):
        out.append(date(y, m, 1))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(out))


def _next_month(d):
    return date(d.year + (d.month // 12), d.month % 12 + 1, 1)


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
            qs = base_qs.all()
        elif user.role == 'patient':
            qs = base_qs.filter(patient=user)
        elif user.role == 'doctor':
            qs = base_qs.filter(appointment__doctor=user)
        else:
            return Invoice.objects.none()

        # ?status=pending,overdue  (comma-separated convenience filter)
        status_param = self.request.query_params.get('status_in')
        if status_param:
            qs = qs.filter(status__in=[s.strip() for s in status_param.split(',') if s.strip()])
        return qs

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        user = self.request.user
        if user.role == 'patient':
            raise PermissionDenied('Patients cannot create invoices.')
        if user.role == 'doctor':
            appointment = serializer.validated_data.get('appointment')
            if not appointment or appointment.doctor_id != user.id:
                raise PermissionDenied('Doctors can only invoice their own appointments.')
        invoice = serializer.save()
        invoice.sync_payment_status()

    def perform_update(self, serializer):
        invoice = serializer.save()
        invoice.sync_payment_status()

    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        """Settle the remaining balance with an offline payment record."""
        if request.user.role != 'admin':
            return Response(
                {'error': 'Only admins can mark invoices as paid'},
                status=status.HTTP_403_FORBIDDEN
            )

        with transaction.atomic():
            invoice = Invoice.objects.select_for_update().get(pk=self.get_object().pk)
            if invoice.status == 'cancelled':
                return Response({'error': 'Cancelled invoices cannot be paid'}, status=status.HTTP_400_BAD_REQUEST)
            balance = invoice.remaining_balance
            if balance > 0:
                Payment.objects.create(
                    invoice=invoice, amount=balance,
                    payment_method=request.data.get('payment_method', 'cash'),
                    notes=f'Marked as paid by {request.user.get_username()}',
                )
            invoice.sync_payment_status()
        return Response({'status': 'Invoice marked as paid'})

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        if request.user.role != 'admin':
            return Response({'error': 'Only admins can cancel invoices'}, status=status.HTTP_403_FORBIDDEN)
        invoice = self.get_object()
        if invoice.total_paid > 0:
            return Response({'error': 'Invoices with payments cannot be cancelled; refund first'},
                            status=status.HTTP_400_BAD_REQUEST)
        invoice.status = 'cancelled'
        invoice.save(update_fields=['status', 'updated_at'])
        return Response({'status': 'Invoice cancelled'})

    @action(detail=True, methods=['get'])
    def download_pdf(self, request, pk=None):
        invoice = self.get_object()
        e = html.escape

        # Format HTML invoice document ready for print / save as PDF
        items_html = "".join([
            f"<tr><td style='padding:8px;border-bottom:1px solid #eee;'>{e(item.description)}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:center;'>{item.quantity}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:right;'>${float(item.unit_price):.2f}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:right;'>${float(item.total):.2f}</td></tr>"
            for item in invoice.items.all()
        ])

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Invoice {e(invoice.invoice_number)} - MediLink</title>
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
            <p style="margin: 4px 0;"><strong>Invoice #:</strong> {e(invoice.invoice_number)}</p>
            <p style="margin: 4px 0;"><strong>Date:</strong> {invoice.invoice_date}</p>
            <p style="margin: 4px 0;"><strong>Due Date:</strong> {invoice.due_date}</p>
            <p style="margin: 4px 0;"><strong>Status:</strong> <span class="badge paid">{e(invoice.status)}</span></p>
        </div>
    </div>

    <div style="margin-top: 30px; display: flex; justify-content: space-between;">
        <div>
            <strong>Billed To:</strong><br>
            {e(invoice.patient.get_full_name())}<br>
            Email: {e(invoice.patient.email)}<br>
            Phone: {e(invoice.patient.phone or 'N/A')}
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
        response = HttpResponse(html_content, content_type='text/html; charset=utf-8')
        response['Content-Security-Policy'] = "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'"
        response['Content-Disposition'] = f'inline; filename="invoice_{e(invoice.invoice_number)}.html"'
        return response
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        if request.user.role != 'admin':
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )

        queryset = self.get_queryset()
        payments = Payment.objects.filter(invoice__in=queryset)

        # Revenue = money actually collected (includes partial payments)
        total_revenue = payments.aggregate(s=Sum('amount'))['s'] or Decimal('0')

        open_invoices = queryset.filter(status__in=['pending', 'partially_paid', 'overdue'])
        open_total = open_invoices.aggregate(s=Sum('total'))['s'] or Decimal('0')
        open_paid = payments.filter(invoice__in=open_invoices).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        pending_amount = max(Decimal('0'), open_total - open_paid)

        # Monthly collected revenue for the last 6 calendar months
        monthly_revenue = []
        for month_start in _month_starts(timezone.localdate(), 6):
            revenue = payments.filter(
                payment_date__date__gte=month_start,
                payment_date__date__lt=_next_month(month_start),
            ).aggregate(s=Sum('amount'))['s'] or 0
            monthly_revenue.append({'month': month_start.strftime('%B %Y'), 'revenue': float(revenue)})

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

    def get_queryset(self):
        user = self.request.user
        qs = InvoiceItem.objects.select_related('invoice').order_by('id')
        if user.role == 'admin':
            return qs
        if user.role == 'patient':
            return qs.filter(invoice__patient=user)
        if user.role == 'doctor':
            return qs.filter(invoice__appointment__doctor=user)
        return qs.none()

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [permissions.IsAuthenticated()]

    # Keep invoice totals consistent with their line items
    def perform_create(self, serializer):
        item = serializer.save()
        item.invoice.recalculate_from_items()
        item.invoice.sync_payment_status()

    def perform_update(self, serializer):
        item = serializer.save()
        item.invoice.recalculate_from_items()
        item.invoice.sync_payment_status()

    def perform_destroy(self, instance):
        invoice = instance.invoice
        instance.delete()
        invoice.recalculate_from_items()
        invoice.sync_payment_status()


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
        # Payments are a financial ledger: only admins may edit or delete them
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        user = self.request.user
        if user.role not in ['patient', 'admin']:
            raise PermissionDenied('Only patients or admins can record payments.')

        with transaction.atomic():
            # Lock the invoice row so concurrent payments can't overpay it
            invoice = Invoice.objects.select_for_update().get(pk=serializer.validated_data['invoice'].pk)
            if user.role == 'patient' and invoice.patient_id != user.id:
                raise PermissionDenied('Patients can only pay their own invoices')
            if invoice.status in ['cancelled', 'paid']:
                raise serializers.ValidationError({'detail': f'This invoice is {invoice.status} and cannot accept payments.'})
            amount = serializer.validated_data['amount']
            balance = invoice.remaining_balance
            if amount > balance:
                raise serializers.ValidationError(
                    {'detail': f'Payment amount exceeds the remaining balance of ${balance:.2f}.'}
                )
            serializer.save(invoice=invoice)
            invoice.sync_payment_status()

    def perform_update(self, serializer):
        payment = serializer.save()
        payment.invoice.sync_payment_status()

    def perform_destroy(self, instance):
        invoice = instance.invoice
        instance.delete()
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

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        user = self.request.user
        invoice = serializer.validated_data['invoice']
        if user.role == 'patient':
            if invoice.patient_id != user.id:
                raise PermissionDenied('You can only file claims for your own invoices.')
            serializer.save(patient=user)
        elif user.role == 'admin':
            serializer.save(patient=invoice.patient)
        else:
            raise PermissionDenied('Only patients or admins can file insurance claims.')

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        if request.user.role != 'admin':
            return Response(
                {'error': 'Only admins can approve claims'},
                status=status.HTTP_403_FORBIDDEN
            )

        claim = self.get_object()
        try:
            approved_amount = Decimal(str(request.data.get('approved_amount')))
        except Exception:
            return Response({'error': 'approved_amount must be a number'}, status=status.HTTP_400_BAD_REQUEST)
        if approved_amount <= 0 or approved_amount > claim.claim_amount:
            return Response({'error': 'approved_amount must be > 0 and not exceed the claimed amount'},
                            status=status.HTTP_400_BAD_REQUEST)
        if claim.status not in ['submitted', 'under_review']:
            return Response({'error': f'Claim is already {claim.status}'}, status=status.HTTP_400_BAD_REQUEST)

        claim.status = 'approved'
        claim.approved_amount = approved_amount
        claim.processed_date = timezone.localdate()
        claim.save()

        return Response({'status': 'Claim approved'})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        if request.user.role != 'admin':
            return Response({'error': 'Only admins can reject claims'}, status=status.HTTP_403_FORBIDDEN)
        claim = self.get_object()
        if claim.status not in ['submitted', 'under_review']:
            return Response({'error': f'Claim is already {claim.status}'}, status=status.HTTP_400_BAD_REQUEST)
        claim.status = 'rejected'
        claim.processed_date = timezone.localdate()
        if request.data.get('reason'):
            claim.notes = (claim.notes + '\n' if claim.notes else '') + f"Rejected: {request.data['reason']}"
        claim.save()
        return Response({'status': 'Claim rejected'})
