from decimal import Decimal

from rest_framework import serializers

from apps.core.models import PaymentMode
from apps.customers.models import Customer
from apps.invoices.models import Invoice
from apps.projects.models import PaymentStage, Project
from apps.quotations.models import Quotation

from .models import AdvanceAdjustment, AdvancePayment, AdvanceRefund, Payment


def _user_name(u):
    return (u.get_full_name() or u.username) if u else ""


class AdvanceRefundSerializer(serializers.ModelSerializer):
    mode_display = serializers.CharField(source="get_mode_display", read_only=True)

    class Meta:
        model = AdvanceRefund
        fields = [
            "id",
            "refund_number",
            "date",
            "amount",
            "mode",
            "mode_display",
            "reference_number",
            "reason",
        ]


class AdvanceSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_phone = serializers.CharField(source="customer.phone", read_only=True)
    project_code = serializers.CharField(source="project.code", read_only=True, default=None)
    quotation_number = serializers.CharField(source="quotation.number", read_only=True, default=None)
    mode_display = serializers.CharField(source="get_mode_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    received_by_name = serializers.SerializerMethodField()
    adjustments = serializers.SerializerMethodField()
    refunds = AdvanceRefundSerializer(many=True, read_only=True)

    class Meta:
        model = AdvancePayment
        fields = [
            "id",
            "receipt_number",
            "customer",
            "customer_name",
            "customer_phone",
            "project",
            "project_code",
            "quotation",
            "quotation_number",
            "date",
            "amount",
            "mode",
            "mode_display",
            "reference_number",
            "cheque_number",
            "cheque_date",
            "bank_name",
            "adjusted_amount",
            "refunded_amount",
            "balance",
            "status",
            "status_display",
            "notes",
            "received_by_name",
            "adjustments",
            "refunds",
            "created_at",
        ]

    def get_received_by_name(self, obj) -> str:
        return _user_name(obj.received_by)

    def get_adjustments(self, obj) -> list:
        return [
            {
                "id": a.id,
                "invoice": a.invoice_id,
                "invoice_number": a.invoice.number,
                "amount": str(a.amount),
                "date": a.date,
            }
            for a in obj.adjustments.select_related("invoice")
        ]


class AdvanceCreateSerializer(serializers.Serializer):
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(), required=False, allow_null=True
    )
    quotation = serializers.PrimaryKeyRelatedField(
        queryset=Quotation.objects.all(), required=False, allow_null=True
    )
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    date = serializers.DateField()
    mode = serializers.ChoiceField(choices=PaymentMode.choices)
    reference_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    cheque_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    cheque_date = serializers.DateField(required=False, allow_null=True)
    bank_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class AdjustSerializer(serializers.Serializer):
    invoice = serializers.PrimaryKeyRelatedField(queryset=Invoice.objects.all())
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))


class RefundSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    date = serializers.DateField()
    mode = serializers.ChoiceField(choices=PaymentMode.choices)
    reason = serializers.CharField(max_length=255)
    reference_number = serializers.CharField(max_length=100, required=False, allow_blank=True)


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)


class PaymentSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_phone = serializers.CharField(source="customer.phone", read_only=True)
    invoice_number = serializers.CharField(source="invoice.number", read_only=True, default=None)
    project_code = serializers.CharField(source="project.code", read_only=True, default=None)
    stage_name = serializers.CharField(source="payment_stage.name", read_only=True, default=None)
    mode_display = serializers.CharField(source="get_mode_display", read_only=True)
    cheque_status_display = serializers.CharField(source="get_cheque_status_display", read_only=True)
    received_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id",
            "receipt_number",
            "customer",
            "customer_name",
            "customer_phone",
            "project",
            "project_code",
            "invoice",
            "invoice_number",
            "payment_stage",
            "stage_name",
            "date",
            "amount",
            "mode",
            "mode_display",
            "reference_number",
            "cheque_number",
            "cheque_date",
            "bank_name",
            "cheque_status",
            "cheque_status_display",
            "notes",
            "received_by_name",
            "created_at",
        ]

    def get_received_by_name(self, obj) -> str:
        return _user_name(obj.received_by)


class PaymentCreateSerializer(serializers.Serializer):
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    invoice = serializers.PrimaryKeyRelatedField(
        queryset=Invoice.objects.all(), required=False, allow_null=True
    )
    payment_stage = serializers.PrimaryKeyRelatedField(
        queryset=PaymentStage.objects.all(), required=False, allow_null=True
    )
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    date = serializers.DateField()
    mode = serializers.ChoiceField(choices=PaymentMode.choices)
    reference_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    cheque_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    cheque_date = serializers.DateField(required=False, allow_null=True)
    bank_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class ChequeSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[("CLEARED", "Cleared"), ("BOUNCED", "Bounced")])
    date = serializers.DateField(required=False)


class AdjustmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdvanceAdjustment
        fields = ["id", "advance", "invoice", "amount", "date"]
