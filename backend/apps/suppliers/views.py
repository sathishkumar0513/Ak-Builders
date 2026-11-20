from django.db.models import Count, Prefetch
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import FINANCE, MANAGEMENT, RoleBasedPermission
from apps.core.exceptions import BusinessRuleError
from apps.core.mixins import SoftDeleteViewSetMixin

from . import services
from .models import Purchase, PurchaseItem, Supplier, SupplierPayment
from .serializers import (
    CancelSerializer,
    PurchaseListSerializer,
    PurchaseSerializer,
    ReceiveSerializer,
    SupplierPaymentCreateSerializer,
    SupplierPaymentSerializer,
    SupplierSerializer,
)


@extend_schema(tags=["Suppliers"])
class SupplierViewSet(SoftDeleteViewSetMixin, viewsets.ModelViewSet):
    serializer_class = SupplierSerializer
    permission_classes = [RoleBasedPermission]
    allowed_roles = {"read": FINANCE, "write": FINANCE, "destroy": MANAGEMENT, "restore": MANAGEMENT}
    filterset_fields = ["city", "state_code"]
    search_fields = ["name", "phone", "gstin", "city", "contact_person"]
    ordering_fields = ["name", "city", "payable", "total_purchases"]
    ordering = ["name"]
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        return services.annotate_supplier_balances(Supplier.objects.all())

    def perform_destroy(self, instance):
        if instance.payable != 0:
            raise BusinessRuleError(
                f"{instance.name} has a balance of ₹{instance.payable}. Settle it before deleting."
            )
        instance.soft_delete(self.request.user)


class PurchaseFilter(filters.FilterSet):
    date_from = filters.DateFilter(field_name="purchase_date", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="purchase_date", lookup_expr="lte")

    class Meta:
        model = Purchase
        fields = ["supplier", "status", "payment_status", "project"]


@extend_schema(tags=["Purchases"])
class PurchaseViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Purchase orders / bills with GST line items. Receiving goods increases stock.
    Purchases are cancelled, never deleted."""

    permission_classes = [RoleBasedPermission]
    allowed_roles = {"read": FINANCE, "write": FINANCE, "cancel": MANAGEMENT}
    filterset_class = PurchaseFilter
    search_fields = ["po_number", "supplier_invoice_number", "supplier__name", "items__description"]
    ordering_fields = ["purchase_date", "po_number", "grand_total", "balance_due"]
    ordering = ["-purchase_date", "-id"]
    http_method_names = ["get", "post", "patch"]

    def get_queryset(self):
        qs = Purchase.objects.select_related("supplier", "project")
        if self.action == "list":
            return qs.annotate(item_count=Count("items")).distinct()
        return qs.prefetch_related(
            Prefetch("items", queryset=PurchaseItem.objects.select_related("material")),
            Prefetch("payments", queryset=SupplierPayment.objects.order_by("-date")),
        )

    def get_serializer_class(self):
        return PurchaseListSerializer if self.action == "list" else PurchaseSerializer

    def create(self, request, *args, **kwargs):
        s = PurchaseSerializer(data=request.data, context=self.get_serializer_context())
        s.is_valid(raise_exception=True)
        data = dict(s.validated_data)
        items = data.pop("items")
        receive_now = data.pop("receive_now", False)
        purchase = services.create_purchase(data=data, items=items, receive_now=receive_now)
        return Response(
            PurchaseSerializer(self.get_queryset().get(pk=purchase.pk)).data, status=status.HTTP_201_CREATED
        )

    def partial_update(self, request, *args, **kwargs):
        purchase = self.get_object()
        s = PurchaseSerializer(
            purchase, data=request.data, partial=True, context=self.get_serializer_context()
        )
        s.is_valid(raise_exception=True)
        data = dict(s.validated_data)
        items = data.pop("items", None)
        data.pop("receive_now", None)
        services.update_purchase(purchase=purchase, data=data, items=items)
        return Response(PurchaseSerializer(self.get_queryset().get(pk=purchase.pk)).data)

    @extend_schema(request=ReceiveSerializer, responses=PurchaseSerializer)
    @action(detail=True, methods=["post"])
    def receive(self, request, pk=None):
        """Record goods received (full or partial). Stock goes up automatically."""
        s = ReceiveSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.receive_items(purchase=self.get_object(), **s.validated_data)
        return Response(PurchaseSerializer(self.get_queryset().get(pk=pk)).data)

    @extend_schema(request=CancelSerializer, responses=PurchaseSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        s = CancelSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.cancel_purchase(purchase=self.get_object(), reason=s.validated_data.get("reason", ""))
        return Response(PurchaseSerializer(self.get_queryset().get(pk=pk)).data)


class SupplierPaymentFilter(filters.FilterSet):
    date_from = filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="date", lookup_expr="lte")

    class Meta:
        model = SupplierPayment
        fields = ["supplier", "purchase", "mode"]


@extend_schema(tags=["Purchases"])
class SupplierPaymentViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Payments made to suppliers. DELETE cancels a payment (Super Admin / Admin) and restores the balance."""

    permission_classes = [RoleBasedPermission]
    allowed_roles = {"read": FINANCE, "write": FINANCE, "destroy": MANAGEMENT}
    filterset_class = SupplierPaymentFilter
    search_fields = ["voucher_number", "supplier__name", "reference_number", "purchase__po_number"]
    ordering_fields = ["date", "amount"]
    ordering = ["-date", "-id"]

    def get_queryset(self):
        return SupplierPayment.objects.select_related("supplier", "purchase")

    def get_serializer_class(self):
        return SupplierPaymentCreateSerializer if self.action == "create" else SupplierPaymentSerializer

    def create(self, request, *args, **kwargs):
        s = SupplierPaymentCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        payment = services.record_supplier_payment(**s.validated_data, paid_by=request.user)
        return Response(SupplierPaymentSerializer(payment).data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        services.cancel_supplier_payment(payment=instance)
