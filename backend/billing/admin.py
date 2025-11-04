from django.contrib import admin
from .models import Invoice, InvoiceItem, Payment, InsuranceClaim


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'patient', 'invoice_date', 'due_date', 'total', 'status']
    list_filter = ['status', 'invoice_date', 'due_date']
    search_fields = ['invoice_number', 'patient__username']
    date_hierarchy = 'invoice_date'
    inlines = [InvoiceItemInline, PaymentInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['invoice', 'payment_date', 'amount', 'payment_method', 'transaction_id']
    list_filter = ['payment_method', 'payment_date']
    search_fields = ['invoice__invoice_number', 'transaction_id']


@admin.register(InsuranceClaim)
class InsuranceClaimAdmin(admin.ModelAdmin):
    list_display = ['claim_number', 'patient', 'insurance_provider', 'claim_amount', 'status']
    list_filter = ['status', 'insurance_provider', 'submitted_date']
    search_fields = ['claim_number', 'patient__username', 'insurance_policy_number']
