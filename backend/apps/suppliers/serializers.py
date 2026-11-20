from decimal import Decimal

from rest_framework import serializers

from apps.core.models import PaymentMode
from apps.core.serializer_fields import validate_gstin_for_state, validate_indian_mobile
from apps.core.utils import INDIAN_STATES
from apps.materials.models import Material

from .models import Purchase, PurchaseItem, Supplier, SupplierPayment

POSITIVE = Decimal("0")


class SupplierSerializer(serializers.ModelSerializer):
    state_name = serializers.SerializerMethodField()
    total_purchases = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True, default=None)
    total_paid = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True, default=None)
    payable = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True, default=None)
    # raw input like "+91 98765-43210" is accepted and normalised in validate_phone
    phone = serializers.CharField(max_length=20)
    alternate_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    gstin = serializers.CharField(max_length=15, required=False, allow_blank=True)  # checked in validate()

    class Meta:
        model = Supplier
        fields = [
            "id",
            "name",
            "contact_person",
            "phone",
            "alternate_phone",
            "email",
            "address",
            "city",
            "state_code",
            "state_name",
            "pincode",
            "gstin",
            "opening_balance",
            "bank_details",
            "notes",
            "total_purchases",
            "total_paid",
            "payable",
            "created_at",
        ]
        read_only_fields = ["created_at"]
        extra_kwargs = {"opening_balance": {"min_value": POSITIVE}}

    def get_state_name(self, obj) -> str:
        return INDIAN_STATES.get(obj.state_code, "")

    def validate_name(self, value):
        value = " ".join(value.split())
        qs = Supplier.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A supplier with this name already exists.")
        return value

    def validate_phone(self, value):
        return validate_indian_mobile(value)

    def validate_alternate_phone(self, value):
        return validate_indian_mobile(value, required=False)

    def validate(self, attrs):
        return validate_gstin_for_state(attrs, self.instance)


class PurchaseItemSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    material = serializers.PrimaryKeyRelatedField(
        queryset=Material.objects.all(), required=False, allow_null=True
    )
    material_name = serializers.StringRelatedField(source="material", read_only=True)
    pending_quantity = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseItem
        fields = [
            "id",
            "item_type",
            "material",
            "material_name",
            "description",
            "hsn_code",
            "quantity",
            "unit",
            "rate",
            "discount_percent",
            "gst_rate",
            "discount_amount",
            "taxable_amount",
            "cgst_amount",
            "sgst_amount",
            "igst_amount",
            "line_total",
            "received_quantity",
            "pending_quantity",
        ]
        read_only_fields = [
            "discount_amount",
            "taxable_amount",
            "cgst_amount",
            "sgst_amount",
            "igst_amount",
            "line_total",
            "received_quantity",
        ]
        extra_kwargs = {
            "description": {"required": False, "allow_blank": True},
            "unit": {"required": False},
            "gst_rate": {"required": False, "allow_null": True},
            "quantity": {"min_value": Decimal("0.001")},
            "rate": {"min_value": POSITIVE},
            "discount_percent": {"min_value": POSITIVE, "max_value": Decimal("100")},
        }

    def get_pending_quantity(self, obj) -> str:
        return str(obj.quantity - obj.received_quantity) if obj.material_id else "0"


class SupplierPaymentSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    po_number = serializers.CharField(source="purchase.po_number", read_only=True, default=None)
    mode_display = serializers.CharField(source="get_mode_display", read_only=True)

    class Meta:
        model = SupplierPayment
        fields = [
            "id",
            "voucher_number",
            "supplier",
            "supplier_name",
            "purchase",
            "po_number",
            "date",
            "amount",
            "mode",
            "mode_display",
            "reference_number",
            "notes",
            "created_at",
        ]
        read_only_fields = ["voucher_number", "created_at"]
        extra_kwargs = {"amount": {"min_value": Decimal("0.01")}}


class PurchaseListSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    payment_status_display = serializers.CharField(source="get_payment_status_display", read_only=True)
    item_count = serializers.IntegerField(read_only=True, default=None)

    class Meta:
        model = Purchase
        fields = [
            "id",
            "po_number",
            "supplier",
            "supplier_name",
            "supplier_invoice_number",
            "purchase_date",
            "status",
            "status_display",
            "payment_status",
            "payment_status_display",
            "grand_total",
            "amount_paid",
            "balance_due",
            "item_count",
        ]


class PurchaseSerializer(serializers.ModelSerializer):
    items = PurchaseItemSerializer(many=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    supplier_state_code = serializers.CharField(source="supplier.state_code", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    payment_status_display = serializers.CharField(source="get_payment_status_display", read_only=True)
    project_name = serializers.StringRelatedField(source="project", read_only=True)
    payments = SupplierPaymentSerializer(many=True, read_only=True)
    receive_now = serializers.BooleanField(write_only=True, required=False, default=False)
    can_edit = serializers.SerializerMethodField()

    class Meta:
        model = Purchase
        fields = [
            "id",
            "po_number",
            "supplier",
            "supplier_name",
            "supplier_state_code",
            "supplier_invoice_number",
            "supplier_invoice_date",
            "purchase_date",
            "status",
            "status_display",
            "payment_status",
            "payment_status_display",
            "project",
            "project_name",
            "notes",
            "transport_charges",
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
            "amount_paid",
            "balance_due",
            "items",
            "payments",
            "receive_now",
            "can_edit",
            "created_at",
        ]
        read_only_fields = [
            "po_number",
            "status",
            "payment_status",
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
            "amount_paid",
            "balance_due",
            "created_at",
        ]
        extra_kwargs = {"transport_charges": {"min_value": POSITIVE}}

    def get_can_edit(self, obj) -> bool:
        return obj.status == Purchase.Status.ORDERED and not any(
            i.received_quantity > 0 for i in obj.items.all()
        )

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError("Add at least one item.")
        return items


class ReceiveLineSerializer(serializers.Serializer):
    item = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0"))


class ReceiveSerializer(serializers.Serializer):
    lines = ReceiveLineSerializer(many=True)
    date = serializers.DateField(required=False)
    update_purchase_price = serializers.BooleanField(default=True)


class CancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=200, required=False, allow_blank=True)


class SupplierPaymentCreateSerializer(serializers.Serializer):
    supplier = serializers.PrimaryKeyRelatedField(queryset=Supplier.objects.all())
    purchase = serializers.PrimaryKeyRelatedField(
        queryset=Purchase.objects.all(), required=False, allow_null=True
    )
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    date = serializers.DateField()
    mode = serializers.ChoiceField(choices=PaymentMode.choices)
    reference_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
