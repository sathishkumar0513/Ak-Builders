from django.db.models import Count, F, Q
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import ALL_ROLES, FINANCE, MANAGEMENT, RoleBasedPermission
from apps.core.exceptions import BusinessRuleError
from apps.core.mixins import SoftDeleteViewSetMixin

from . import services
from .models import Material, MaterialCategory, PriceHistory, StockMovement
from .serializers import (
    MaterialCategorySerializer,
    MaterialSerializer,
    PriceHistorySerializer,
    StockAdjustmentSerializer,
    StockMovementSerializer,
)


@extend_schema(tags=["Materials"])
class MaterialCategoryViewSet(viewsets.ModelViewSet):
    serializer_class = MaterialCategorySerializer
    permission_classes = [RoleBasedPermission]
    allowed_roles = {"read": ALL_ROLES, "write": MANAGEMENT}
    pagination_class = None
    search_fields = ["name"]
    ordering = ["name"]
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        return MaterialCategory.objects.annotate(
            material_count=Count("materials", filter=Q(materials__is_deleted=False))
        )

    def perform_destroy(self, instance):
        if instance.material_count:
            raise BusinessRuleError(
                f"Move or delete the {instance.material_count} materials in this category first."
            )
        instance.soft_delete(self.request.user)


class MaterialFilter(filters.FilterSet):
    low_stock = filters.BooleanFilter(method="filter_low_stock")
    min_stock = filters.NumberFilter(field_name="stock_quantity", lookup_expr="gte")

    class Meta:
        model = Material
        fields = ["category", "unit", "is_active", "gst_rate", "brand"]

    def filter_low_stock(self, qs, name, value):
        cond = Q(stock_quantity__lte=F("reorder_level"))
        return qs.filter(cond) if value else qs.exclude(cond)


@extend_schema(tags=["Materials"])
class MaterialViewSet(SoftDeleteViewSetMixin, viewsets.ModelViewSet):
    """Material master. Stock can only change through purchases, site issues or stock adjustments."""

    serializer_class = MaterialSerializer
    permission_classes = [RoleBasedPermission]
    allowed_roles = {
        "read": ALL_ROLES,
        "write": FINANCE,
        "destroy": MANAGEMENT,
        "restore": MANAGEMENT,
        "adjust_stock": MANAGEMENT,
        "price_history": FINANCE,
    }
    filterset_class = MaterialFilter
    search_fields = ["name", "brand", "hsn_code", "sku", "category__name"]
    ordering_fields = [
        "name",
        "brand",
        "stock_quantity",
        "selling_price",
        "purchase_price",
        "category__name",
        "updated_at",
    ]
    ordering = ["category__name", "name"]
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        return Material.objects.select_related("category")

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("price_change_reason", None)
        opening = data.pop("opening_stock", None)
        serializer.instance = services.create_material(data=data, opening_stock=opening)

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("opening_stock", None)
        reason = data.pop("price_change_reason", "")
        serializer.instance = services.update_material(
            material=serializer.instance, data=data, price_reason=reason
        )

    def perform_destroy(self, instance):
        if instance.stock_quantity > 0:
            raise BusinessRuleError(
                f"{instance} still has {instance.stock_quantity.normalize():f} {instance.unit} in stock. "
                "Adjust stock to zero first, or mark it inactive instead."
            )
        instance.soft_delete(self.request.user)

    @extend_schema(request=StockAdjustmentSerializer, responses=StockMovementSerializer)
    @action(detail=True, methods=["post"], url_path="adjust-stock")
    def adjust_stock(self, request, pk=None):
        """Manual correction (damage, count mismatch, opening balance). Reason is mandatory."""
        material = self.get_object()
        s = StockAdjustmentSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        movement = services.adjust_stock(material=material, **s.validated_data)
        return Response(StockMovementSerializer(movement).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses=StockMovementSerializer(many=True))
    @action(detail=True, methods=["get"])
    def movements(self, request, pk=None):
        qs = StockMovement.objects.filter(material=self.get_object()).select_related(
            "material", "project", "created_by"
        )
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(StockMovementSerializer(page, many=True).data)

    @extend_schema(responses=PriceHistorySerializer(many=True))
    @action(detail=True, methods=["get"], url_path="price-history")
    def price_history(self, request, pk=None):
        qs = PriceHistory.objects.filter(material=self.get_object()).select_related("changed_by")
        return Response(PriceHistorySerializer(qs, many=True).data)

    @action(detail=False, methods=["get"], url_path="low-stock")
    def low_stock(self, request):
        """Active materials at or below their reorder level (for alerts and the dashboard)."""
        qs = services.low_stock_queryset()
        return Response({"count": qs.count(), "results": self.get_serializer(qs, many=True).data})


class StockMovementFilter(filters.FilterSet):
    date_from = filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="date", lookup_expr="lte")

    class Meta:
        model = StockMovement
        fields = ["material", "movement_type", "project", "reference_type"]


@extend_schema(tags=["Materials"])
class StockMovementViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Stock ledger across all materials (read-only)."""

    serializer_class = StockMovementSerializer
    permission_classes = [RoleBasedPermission]
    allowed_roles = ALL_ROLES
    filterset_class = StockMovementFilter
    search_fields = ["material__name", "material__brand", "note"]
    ordering_fields = ["date", "created_at"]
    ordering = ["-date", "-id"]

    def get_queryset(self):
        return StockMovement.objects.select_related("material", "project", "created_by")
