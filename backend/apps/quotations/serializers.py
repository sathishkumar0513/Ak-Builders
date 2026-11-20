from decimal import Decimal

from rest_framework import serializers

from apps.customers.models import Customer
from apps.materials.models import Material

from .models import Quotation, QuotationItem

POS = Decimal("0")


class QuotationItemSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    material = serializers.PrimaryKeyRelatedField(
        queryset=Material.objects.all(), required=False, allow_null=True
    )
    unit_display = serializers.CharField(source="get_unit_display", read_only=True)

    class Meta:
        model = QuotationItem
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


class QuotationListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_phone = serializers.CharField(source="customer.phone", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Quotation
        fields = [
            "id",
            "number",
            "revision",
            "is_latest",
            "customer",
            "customer_name",
            "customer_phone",
            "title",
            "quotation_date",
            "valid_until",
            "status",
            "status_display",
            "grand_total",
            "created_at",
        ]


class QuotationSerializer(serializers.ModelSerializer):
    items = QuotationItemSerializer(many=True)
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    customer_detail = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    revisions = serializers.SerializerMethodField()
    project = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    allowed_actions = serializers.SerializerMethodField()

    class Meta:
        model = Quotation
        fields = [
            "id",
            "number",
            "revision",
            "is_latest",
            "previous_revision",
            "customer",
            "customer_detail",
            "title",
            "site_address",
            "quotation_date",
            "valid_until",
            "status",
            "status_display",
            "header_discount",
            "terms_and_conditions",
            "notes",
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
            "sent_at",
            "approved_at",
            "rejection_reason",
            "items",
            "revisions",
            "project",
            "created_by_name",
            "created_at",
            "updated_at",
            "allowed_actions",
        ]
        read_only_fields = [
            "number",
            "revision",
            "is_latest",
            "previous_revision",
            "status",
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
            "sent_at",
            "approved_at",
            "rejection_reason",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "quotation_date": {"required": False},
            "valid_until": {"required": False},
            "header_discount": {"min_value": POS},
        }

    def get_customer_detail(self, obj) -> dict:
        c = obj.customer
        return {
            "id": c.id,
            "name": c.name,
            "phone": c.phone,
            "email": c.email,
            "address": c.address,
            "city": c.city,
            "state_code": c.state_code,
            "gstin": c.gstin,
        }

    def get_revisions(self, obj) -> list:
        qs = Quotation.objects.filter(number=obj.number).order_by("revision")
        return [
            {
                "id": r.id,
                "revision": r.revision,
                "status": r.status,
                "grand_total": str(r.grand_total),
                "quotation_date": r.quotation_date,
                "is_latest": r.is_latest,
            }
            for r in qs
        ]

    def get_project(self, obj) -> dict | None:
        p = obj.projects.first()
        return {"id": p.id, "code": p.code, "name": p.name} if p else None

    def get_created_by_name(self, obj) -> str:
        return (obj.created_by.get_full_name() or obj.created_by.username) if obj.created_by_id else ""

    def get_allowed_actions(self, obj) -> list:
        S = Quotation.Status
        if not obj.is_latest:
            return []
        actions = {
            S.DRAFT: ["edit", "send", "approve", "reject", "delete"],
            S.SENT: ["send", "approve", "reject", "revise"],
            S.APPROVED: ["convert", "reject", "revise"],
            S.REJECTED: ["revise", "delete"],
            S.EXPIRED: ["revise", "delete"],
            S.CONVERTED: [],
        }[obj.status]
        return actions + ["pdf", "share", "duplicate"]

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError("Add at least one item.")
        return items

    def validate(self, attrs):
        qd, vu = attrs.get("quotation_date"), attrs.get("valid_until")
        if qd and vu and vu < qd:
            raise serializers.ValidationError(
                {"valid_until": "Valid-until date cannot be before the quotation date."}
            )
        return attrs


class RejectSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True)


class StageSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    percentage = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal("0.01"))


class ConvertSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    project_type = serializers.ChoiceField(
        choices=[
            ("NEW", "New construction"),
            ("RENOVATION", "Renovation"),
            ("SUPPLY", "Material supply only"),
        ],
        required=False,
    )
    start_date = serializers.DateField(required=False, allow_null=True)
    expected_end_date = serializers.DateField(required=False, allow_null=True)
    assigned_engineer = serializers.IntegerField(required=False, allow_null=True)
    stages = StageSerializer(many=True, required=False)


class EmailSerializer(serializers.Serializer):
    to = serializers.ListField(child=serializers.EmailField(), min_length=1)
    cc = serializers.ListField(child=serializers.EmailField(), required=False)
    subject = serializers.CharField(max_length=200, required=False, allow_blank=True)
    message = serializers.CharField(required=False, allow_blank=True)


class DuplicateSerializer(serializers.Serializer):
    customer = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(), required=False, allow_null=True
    )
