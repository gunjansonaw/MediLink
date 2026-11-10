from decimal import Decimal

from rest_framework import serializers

from users.models import User
from users.serializers import UserSerializer
from .models import Invoice, InvoiceItem, Payment, InsuranceClaim


class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = ['id', 'invoice', 'description', 'quantity', 'unit_price', 'total']
        read_only_fields = ['id', 'total']

    def validate_unit_price(self, value):
        if value < 0:
            raise serializers.ValidationError('Unit price cannot be negative.')
        return value


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'invoice', 'payment_date', 'amount', 'payment_method',
                  'transaction_id', 'notes']
        read_only_fields = ['id', 'payment_date']

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('Payment amount must be greater than zero.')
        return value


class InvoiceSerializer(serializers.ModelSerializer):
    patient_details = UserSerializer(source='patient', read_only=True)
    items = InvoiceItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    amount_paid = serializers.SerializerMethodField()
    amount_due = serializers.SerializerMethodField()
    remaining_balance = serializers.SerializerMethodField()
    patient = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role='patient'))

    class Meta:
        model = Invoice
        fields = ['id', 'patient', 'patient_details', 'appointment', 'invoice_number',
                  'invoice_date', 'due_date', 'status', 'subtotal', 'tax', 'discount',
                  'total', 'amount_paid', 'amount_due', 'remaining_balance', 'items', 'payments', 'notes',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'invoice_number', 'invoice_date', 'total', 'status',
                            'created_at', 'updated_at', 'amount_paid', 'amount_due', 'remaining_balance']

    def validate(self, attrs):
        get = lambda k: attrs.get(k, getattr(self.instance, k, None)) or Decimal('0')
        subtotal, tax, discount = get('subtotal'), get('tax'), get('discount')
        if min(subtotal, tax, discount) < 0:
            raise serializers.ValidationError('Subtotal, tax and discount cannot be negative.')
        if discount > subtotal + tax:
            raise serializers.ValidationError({'discount': 'Discount cannot exceed subtotal plus tax.'})
        appointment = attrs.get('appointment')
        patient = attrs.get('patient', getattr(self.instance, 'patient', None))
        if appointment and patient and appointment.patient_id != patient.id:
            raise serializers.ValidationError({'appointment': 'Appointment belongs to a different patient.'})
        return attrs

    def get_amount_paid(self, obj):
        # Uses prefetched payments to avoid N+1 queries
        return sum((payment.amount for payment in obj.payments.all()), Decimal('0.00'))

    def get_amount_due(self, obj):
        return max(Decimal('0.00'), obj.total - self.get_amount_paid(obj))

    def get_remaining_balance(self, obj):
        return self.get_amount_due(obj)


class InsuranceClaimSerializer(serializers.ModelSerializer):
    patient_details = UserSerializer(source='patient', read_only=True)
    patient = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role='patient'), required=False)

    class Meta:
        model = InsuranceClaim
        fields = ['id', 'patient', 'patient_details', 'invoice', 'claim_number',
                  'insurance_provider', 'insurance_policy_number', 'claim_amount',
                  'approved_amount', 'status', 'submitted_date', 'processed_date', 'notes']
        # Decision fields are only changed through the approve/reject actions
        read_only_fields = ['id', 'claim_number', 'submitted_date', 'status',
                            'approved_amount', 'processed_date']

    def validate(self, attrs):
        invoice = attrs.get('invoice', getattr(self.instance, 'invoice', None))
        claim_amount = attrs.get('claim_amount', getattr(self.instance, 'claim_amount', None))
        if claim_amount is not None and claim_amount <= 0:
            raise serializers.ValidationError({'claim_amount': 'Claim amount must be greater than zero.'})
        if invoice and claim_amount and claim_amount > invoice.total:
            raise serializers.ValidationError({'claim_amount': 'Claim amount cannot exceed the invoice total.'})
        return attrs
