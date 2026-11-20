from decimal import Decimal

from rest_framework import serializers

from apps.customers.models import Customer
from apps.materials.models import Material
from apps.projects.models import PaymentStage, Project
from apps.quotations.models import Quotation

from .models import Invoice, InvoiceItem

POS = Decimal("0")


class InvoiceItemSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    material = serializers.PrimaryKeyRelatedField(
        queryset=Material.objects.all(), required=False, allow_null=True
    )
    unit_display = serializers.CharField(source="get_unit_display", read_only=True)

    class Meta:
        model = InvoiceItem
        fields = [
            "id",
            "item_type",
            "material",
            "description",
            "hsn_code",
            "quantity",
            "unit",
            "unit_display",
            "rate",
            "discount_percent",
            "gst_rate",
            "discount_amount",
            "taxable_amount",
            "cgst_amount",
            "sgst_amount",
            "igst_amount",
            "line_total",
        ]
        read_only_fields = [
            "discount_amount",
            "taxable_amount",
            "cgst_amount",
            "sgst_amount",
            "igst_amount",
            "line_total",
        ]
        extra_kwargs = {
            "description": {"required": False, "allow_blank": True},
            "unit": {"required": False},
            "hsn_code": {"required": False, "allow_blank": True},
            "gst_rate": {"required": False, "allow_null": True},
            "quantity": {"min_value": Decimal("0.001")},
            "rate": {"min_value": POS},
            "discount_percent": {"min_value": POS, "max_value": Decimal("100")},
        }


class InvoiceListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_phone = serializers.CharField(source="customer.phone", read_only=True)
    project_code = serializers.CharField(source="project.code", read_only=True, default=None)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            "id",
            "number",
            "invoice_date",
            "due_date",
            "customer",
            "customer_name",
            "customer_phone",
            "project",
            "project_code",
            "status",
            "status_display",
            "grand_total",
            "advance_adjusted",
            "amount_paid",
            "balance_due",
            "is_overdue",
        ]

    def get_is_overdue(self, obj) -> bool:
        from datetime import date

        return bool(obj.due_date and obj.due_date < date.today() and obj.status in ("UNPAID", "PARTIAL"))


class InvoiceSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True)
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(), required=False, allow_null=True
    )
    quotation = serializers.PrimaryKeyRelatedField(
        queryset=Quotation.objects.all(), required=False, allow_null=True
    )
    payment_stage = serializers.PrimaryKeyRelatedField(
        queryset=PaymentStage.objects.all(), required=False, allow_null=True
    )
    customer_detail = serializers.SerializerMethodField()
    project_detail = serializers.SerializerMethodField()
    stage_name = serializers.CharField(source="payment_stage.name", read_only=True, default=None)
    quotation_number = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    adjustments = serializers.SerializerMethodField()
    payments = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    auto_adjust_advance = serializers.BooleanField(write_only=True, required=False, default=True)
    can_edit = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            "id",
            "number",
            "customer",
            "customer_detail",
            "project",
            "project_detail",
            "quotation",
            "quotation_number",
            "payment_stage",
            "stage_name",
            "invoice_date",
            "due_date",
            "status",
            "status_display",
            "billing_name",
            "billing_address",
            "billing_gstin",
            "header_discount",
            "place_of_supply",
            "is_interstate",
            "subtotal",
            "discount_total",
            "taxable_amount",
            "cgst_amount",
            "sgst_amount",
            "igst_amount",
            "round_off",
            "grand_total",
            "amount_in_words",
            "advance_adjusted",
            "amount_paid",
            "balance_due",
            "terms_and_conditions",
            "notes",
            "cancelled_reason",
            "deduct_stock",
            "items",
            "adjustments",
            "payments",
            "is_overdue",
            "auto_adjust_advance",
            "can_edit",
            "created_at",
        ]
        read_only_fields = [
            "number",
            "status",
            "billing_name",
            "billing_address",
            "billing_gstin",
            "place_of_supply",
            "is_interstate",
            "subtotal",
            "discount_total",
            "taxable_amount",
            "cgst_amount",
            "sgst_amount",
            "igst_amount",
            "round_off",
            "grand_total",
            "amount_in_words",
            "advance_adjusted",
            "amount_paid",
            "balance_due",
            "cancelled_reason",
            "created_at",
        ]
        extra_kwargs = {
            "invoice_date": {"required": False},
            "due_date": {"required": False},
            "header_discount": {"min_value": POS},
        }

    def get_customer_detail(self, obj) -> dict:
        c = obj.customer
        return {"id": c.id, "name": c.name, "phone": c.phone, "email": c.email, "state_code": c.state_code}

    def get_project_detail(self, obj) -> dict | None:
        p = obj.project
        return {"id": p.id, "code": p.code, "name": p.name} if p else None

    def get_quotation_number(self, obj) -> str | None:
        return f"{obj.quotation.number} Rev {obj.quotation.revision}" if obj.quotation_id else None

    def get_adjustments(self, obj) -> list:
        return [
            {
                "id": a.id,
                "advance": a.advance_id,
                "receipt_number": a.advance.receipt_number,
                "amount": str(a.amount),
                "date": a.date,
            }
            for a in obj.advance_adjustments.select_related("advance")
        ]

    def get_payments(self, obj) -> list:
        return [
            {
                "id": p.id,
                "receipt_number": p.receipt_number,
                "date": p.date,
                "amount": str(p.amount),
                "mode": p.get_mode_display(),
                "reference_number": p.reference_number,
                "cheque_status": p.cheque_status,
            }
            for p in obj.payments.order_by("date")
        ]

    def get_is_overdue(self, obj) -> bool:
        from datetime import date

        return bool(obj.due_date and obj.due_date < date.today() and obj.status in ("UNPAID", "PARTIAL"))

    def get_can_edit(self, obj) -> bool:
        return obj.status == "UNPAID" and not obj.advance_adjusted and not obj.amount_paid

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError("Add at least one item.")
        return items


class InvoiceCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)


class FromStageSerializer(serializers.Serializer):
    payment_stage = serializers.PrimaryKeyRelatedField(queryset=PaymentStage.objects.all())
    gst_rate = serializers.DecimalField(max_digits=5, decimal_places=2, default=Decimal("18"))
    sac = serializers.CharField(max_length=8, default="995411")
