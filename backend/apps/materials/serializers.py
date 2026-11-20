from decimal import Decimal

from rest_framework import serializers

from apps.accounts.permissions import FINANCE, SUPER_ADMIN

from .models import Material, MaterialCategory, PriceHistory, StockMovement


def can_see_cost(request):
    role = getattr(getattr(request, "user", None), "role_code", None)
    return role == SUPER_ADMIN or role in FINANCE


class MaterialCategorySerializer(serializers.ModelSerializer):
    material_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = MaterialCategory
        fields = ["id", "name", "description", "material_count"]

    def validate_name(self, value):
        value = " ".join(value.split())
        qs = MaterialCategory.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A category with this name already exists.")
        return value


class MaterialSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    unit_display = serializers.CharField(source="get_unit_display", read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    stock_value = serializers.SerializerMethodField()
    opening_stock = serializers.DecimalField(
        max_digits=12, decimal_places=3, write_only=True, required=False, min_value=Decimal("0")
    )
    price_change_reason = serializers.CharField(
        write_only=True, required=False, allow_blank=True, max_length=255
    )

    class Meta:
        model = Material
        fields = [
            "id",
            "category",
            "category_name",
            "name",
            "brand",
            "sku",
            "hsn_code",
            "unit",
            "unit_display",
            "purchase_price",
            "selling_price",
            "gst_rate",
            "stock_quantity",
            "reorder_level",
            "is_low_stock",
            "stock_value",
            "is_active",
            "description",
            "opening_stock",
            "price_change_reason",
            "updated_at",
        ]
        read_only_fields = ["stock_quantity", "updated_at"]
        extra_kwargs = {
            "purchase_price": {"min_value": Decimal("0")},
            "selling_price": {"min_value": Decimal("0")},
            "reorder_level": {"min_value": Decimal("0")},
        }

    def get_stock_value(self, obj) -> str:
        return str((obj.stock_quantity * obj.purchase_price).quantize(Decimal("0.01")))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not can_see_cost(self.context.get("request")):
            data.pop("purchase_price", None)
            data.pop("stock_value", None)
        return data

    def validate_gst_rate(self, value):
        if value not in (
            Decimal("0"),
            Decimal("0.25"),
            Decimal("3"),
            Decimal("5"),
            Decimal("12"),
            Decimal("18"),
            Decimal("28"),
            Decimal("40"),
        ):
            raise serializers.ValidationError("Use a valid GST slab: 0, 0.25, 3, 5, 12, 18, 28 or 40%.")
        return value

    def validate_hsn_code(self, value):
        value = (value or "").strip()
        if value and (not value.isdigit() or len(value) not in (4, 6, 8)):
            raise serializers.ValidationError("HSN code must be 4, 6 or 8 digits.")
        return value

    def validate(self, attrs):
        name = attrs.get("name", getattr(self.instance, "name", ""))
        brand = attrs.get("brand", getattr(self.instance, "brand", ""))
        qs = Material.objects.filter(name__iexact=name.strip(), brand__iexact=(brand or "").strip())
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError({"name": "This material and brand already exist."})
        sp = attrs.get("selling_price", getattr(self.instance, "selling_price", None))
        pp = attrs.get("purchase_price", getattr(self.instance, "purchase_price", None))
        if sp is not None and pp is not None and sp < pp and not self.initial_data.get("allow_below_cost"):
            raise serializers.ValidationError(
                {
                    "selling_price": "Selling price is below purchase price. "
                    "Tick 'allow below cost' to save anyway."
                }
            )
        return attrs


class StockMovementSerializer(serializers.ModelSerializer):
    material_name = serializers.StringRelatedField(source="material", read_only=True)
    unit = serializers.CharField(source="material.unit", read_only=True)
    movement_type_display = serializers.CharField(source="get_movement_type_display", read_only=True)
    signed_quantity = serializers.DecimalField(max_digits=12, decimal_places=3, read_only=True)
    project_name = serializers.StringRelatedField(source="project", read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = StockMovement
        fields = [
            "id",
            "date",
            "material",
            "material_name",
            "unit",
            "movement_type",
            "movement_type_display",
            "quantity",
            "signed_quantity",
            "balance_after",
            "rate",
            "project",
            "project_name",
            "reference_type",
            "reference_id",
            "note",
            "created_at",
            "created_by_name",
        ]

    def get_created_by_name(self, obj) -> str:
        return (obj.created_by.get_full_name() or obj.created_by.username) if obj.created_by_id else ""


class PriceHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = PriceHistory
        fields = [
            "id",
            "changed_at",
            "old_purchase_price",
            "new_purchase_price",
            "old_selling_price",
            "new_selling_price",
            "reason",
            "changed_by_name",
        ]

    def get_changed_by_name(self, obj) -> str:
        return (obj.changed_by.get_full_name() or obj.changed_by.username) if obj.changed_by_id else "System"


class StockAdjustmentSerializer(serializers.Serializer):
    direction = serializers.ChoiceField(choices=[("IN", "Add stock"), ("OUT", "Remove stock")])
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))
    reason = serializers.CharField(max_length=255)
    date = serializers.DateField(required=False)
