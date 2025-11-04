from rest_framework import serializers
from .models import Invoice, InvoiceItem, Payment, InsuranceClaim
from users.serializers import UserSerializer


class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = ['id', 'invoice', 'description', 'quantity', 'unit_price', 'total']
        read_only_fields = ['id', 'total']


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'invoice', 'payment_date', 'amount', 'payment_method', 
                  'transaction_id', 'notes']
        read_only_fields = ['id', 'payment_date']


class InvoiceSerializer(serializers.ModelSerializer):
    patient_details = UserSerializer(source='patient', read_only=True)
    items = InvoiceItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    amount_paid = serializers.SerializerMethodField()
    amount_due = serializers.SerializerMethodField()
    
    class Meta:
        model = Invoice
        fields = ['id', 'patient', 'patient_details', 'appointment', 'invoice_number',
                  'invoice_date', 'due_date', 'status', 'subtotal', 'tax', 'discount',
                  'total', 'amount_paid', 'amount_due', 'items', 'payments', 'notes',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'invoice_number', 'invoice_date', 'total', 
                           'created_at', 'updated_at', 'amount_paid', 'amount_due']
    
    def get_amount_paid(self, obj):
        return sum(payment.amount for payment in obj.payments.all())
    
    def get_amount_due(self, obj):
        amount_paid = self.get_amount_paid(obj)
        return obj.total - amount_paid


class InsuranceClaimSerializer(serializers.ModelSerializer):
    patient_details = UserSerializer(source='patient', read_only=True)
    
    class Meta:
        model = InsuranceClaim
        fields = ['id', 'patient', 'patient_details', 'invoice', 'claim_number',
                  'insurance_provider', 'insurance_policy_number', 'claim_amount',
                  'approved_amount', 'status', 'submitted_date', 'processed_date', 'notes']
        read_only_fields = ['id', 'claim_number', 'submitted_date']
