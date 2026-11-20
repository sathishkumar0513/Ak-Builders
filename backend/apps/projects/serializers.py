from decimal import Decimal

from rest_framework import serializers

from apps.accounts.models import User
from apps.customers.models import Customer
from apps.materials.models import Material
from apps.quotations.models import Quotation

from .models import PaymentStage, ProgressNote, ProgressPhoto, Project, ProjectMaterialIssue


class PaymentStageSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    balance = serializers.SerializerMethodField()
    invoices = serializers.SerializerMethodField()

    class Meta:
        model = PaymentStage
        fields = [
            "id",
            "name",
            "percentage",
            "amount",
            "due_date",
            "amount_received",
            "balance",
            "status",
            "status_display",
            "sort_order",
            "invoices",
        ]

    def get_balance(self, obj) -> str:
        return str(obj.amount - obj.amount_received)

    def get_invoices(self, obj) -> list:
        return [
            {"id": i.id, "number": i.number, "status": i.status, "balance_due": str(i.balance_due)}
            for i in obj.invoices.exclude(status="CANCELLED")
        ]


class StageInputSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    name = serializers.CharField(max_length=150)
    percentage = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal("0.01"))
    due_date = serializers.DateField(required=False, allow_null=True)


class StagesSerializer(serializers.Serializer):
    stages = StageInputSerializer(many=True)


class ProjectListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    engineer_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    project_type_display = serializers.CharField(source="get_project_type_display", read_only=True)

    class Meta:
        model = Project
        fields = [
            "id",
            "code",
            "name",
            "customer",
            "customer_name",
            "project_type",
            "project_type_display",
            "status",
            "status_display",
            "assigned_engineer",
            "engineer_name",
            "start_date",
            "expected_end_date",
            "contract_value",
            "progress_percent",
            "site_city",
        ]

    def get_engineer_name(self, obj) -> str | None:
        e = obj.assigned_engineer
        return (e.get_full_name() or e.username) if e else None


class ProjectSerializer(ProjectListSerializer):
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    quotation = serializers.PrimaryKeyRelatedField(
        queryset=Quotation.objects.all(), required=False, allow_null=True
    )
    assigned_engineer = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True), required=False, allow_null=True
    )
    customer_detail = serializers.SerializerMethodField()
    quotation_number = serializers.SerializerMethodField()
    payment_stages = PaymentStageSerializer(many=True, read_only=True)
    stages = StageInputSerializer(many=True, write_only=True, required=False)

    class Meta(ProjectListSerializer.Meta):
        fields = ProjectListSerializer.Meta.fields + [
            "quotation",
            "quotation_number",
            "customer_detail",
            "site_address",
            "site_pincode",
            "actual_end_date",
            "description",
            "payment_stages",
            "stages",
            "created_at",
        ]
        read_only_fields = ["code", "created_at"]
        extra_kwargs = {
            "contract_value": {"min_value": Decimal("0")},
            "progress_percent": {"min_value": Decimal("0"), "max_value": Decimal("100")},
        }

    def get_customer_detail(self, obj) -> dict:
        c = obj.customer
        return {"id": c.id, "name": c.name, "phone": c.phone, "address": c.address}

    def get_quotation_number(self, obj) -> str | None:
        return f"{obj.quotation.number} Rev {obj.quotation.revision}" if obj.quotation_id else None


class MaterialIssueSerializer(serializers.ModelSerializer):
    material = serializers.PrimaryKeyRelatedField(queryset=Material.objects.all())
    material_name = serializers.StringRelatedField(source="material", read_only=True)
    unit = serializers.CharField(source="material.unit", read_only=True)
    issued_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ProjectMaterialIssue
        fields = [
            "id",
            "material",
            "material_name",
            "unit",
            "issue_date",
            "quantity",
            "rate",
            "amount",
            "is_return",
            "received_by_name",
            "vehicle_number",
            "notes",
            "issued_by_name",
            "created_at",
        ]
        read_only_fields = ["rate", "amount", "created_at"]
        extra_kwargs = {"quantity": {"min_value": Decimal("0.001")}, "issue_date": {"required": False}}

    def get_issued_by_name(self, obj) -> str:
        u = obj.issued_by
        return (u.get_full_name() or u.username) if u else ""

    def to_representation(self, instance):
        data = super().to_representation(instance)
        from apps.materials.serializers import can_see_cost

        if not can_see_cost(self.context.get("request")):
            data.pop("rate", None)
            data.pop("amount", None)
        return data


class ProgressPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgressPhoto
        fields = ["id", "image", "caption"]

    def to_representation(self, instance):
        return {
            "id": instance.id,
            "image": instance.image.url if instance.image else None,
            "caption": instance.caption,
        }


class ProgressNoteSerializer(serializers.ModelSerializer):
    photos = ProgressPhotoSerializer(many=True, read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ProgressNote
        fields = [
            "id",
            "date",
            "note",
            "progress_percent",
            "workers_on_site",
            "photos",
            "created_by_name",
            "created_at",
        ]
        extra_kwargs = {
            "date": {"required": False},
            "progress_percent": {"min_value": Decimal("0"), "max_value": Decimal("100")},
        }

    def get_created_by_name(self, obj) -> str:
        u = obj.created_by
        return (u.get_full_name() or u.username) if u else ""
