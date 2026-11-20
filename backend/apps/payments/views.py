from django.http import HttpResponse
from django_filters import rest_framework as filters
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import FINANCE, MANAGEMENT, RoleBasedPermission
from apps.core.exceptions import BusinessRuleError

from . import documents, services
from .models import AdvanceAdjustment, AdvancePayment, AdvanceRefund, Payment
from .serializers import (
    AdjustmentSerializer,
    AdjustSerializer,
    AdvanceCreateSerializer,
    AdvanceSerializer,
    ChequeSerializer,
    PaymentCreateSerializer,
    PaymentSerializer,
    ReasonSerializer,
    RefundSerializer,
)


def _pdf(content, filename, request):
    r = HttpResponse(content, content_type="application/pdf")
    disposition = "attachment" if request.query_params.get("download") in ("1", "true") else "inline"
    r["Content-Disposition"] = f'{disposition}; filename="{filename}"'
    return r


class DateRangeFilter(filters.FilterSet):
    date_from = filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="date", lookup_expr="lte")


class AdvanceFilter(DateRangeFilter):
    status = filters.MultipleChoiceFilter(choices=AdvancePayment.Status.choices)

    class Meta:
        model = AdvancePayment
        fields = ["customer", "project", "status", "mode"]


@extend_schema(tags=["Advances"])
class AdvanceViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    """Advance receipts: adjusted against invoices (automatically or manually) or refunded."""

    permission_classes = [RoleBasedPermission]
    allowed_roles = {"read": FINANCE, "write": FINANCE, "cancel": MANAGEMENT}
    filterset_class = AdvanceFilter
    search_fields = [
        "receipt_number",
        "customer__name",
        "customer__phone",
        "reference_number",
        "project__code",
    ]
    ordering_fields = ["date", "amount", "receipt_number"]
    ordering = ["-date", "-id"]

    def get_queryset(self):
        return AdvancePayment.objects.select_related(
            "customer", "project", "quotation", "received_by"
        ).prefetch_related("refunds")

    def get_serializer_class(self):
        return AdvanceCreateSerializer if self.action == "create" else AdvanceSerializer

    def create(self, request, *args, **kwargs):
        s = AdvanceCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        adv = services.record_advance(**s.validated_data, received_by=request.user)
        return Response(AdvanceSerializer(adv).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=AdjustSerializer, responses=AdvanceSerializer)
    @action(detail=True, methods=["post"])
    def adjust(self, request, pk=None):
        s = AdjustSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.adjust_advance(advance=self.get_object(), **s.validated_data)
        return Response(AdvanceSerializer(self.get_queryset().get(pk=pk)).data)

    @extend_schema(request=RefundSerializer, responses=AdvanceSerializer)
    @action(detail=True, methods=["post"])
    def refund(self, request, pk=None):
        s = RefundSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.refund_advance(advance=self.get_object(), **s.validated_data)
        return Response(AdvanceSerializer(self.get_queryset().get(pk=pk)).data)

    @extend_schema(request=ReasonSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        s = ReasonSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.cancel_advance(advance=self.get_object(), reason=s.validated_data["reason"])
        return Response({"detail": "Advance cancelled."})

    @extend_schema(responses={(200, "application/pdf"): OpenApiResponse(description="PDF")})
    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        a = self.get_object()
        return _pdf(
            documents.advance_receipt_pdf(a), documents.filename("Advance-Receipt", a.receipt_number), request
        )

    @action(detail=True, methods=["get"], url_path=r"refunds/(?P<refund_id>\d+)/pdf")
    def refund_pdf(self, request, pk=None, refund_id=None):
        r = AdvanceRefund.objects.filter(advance=self.get_object(), pk=refund_id).first()
        if not r:
            raise BusinessRuleError("Refund not found.")
        return _pdf(documents.refund_pdf(r), documents.filename("Refund", r.refund_number), request)

    @action(detail=True, methods=["get"], url_path="share-text")
    def share_text(self, request, pk=None):
        a = self.get_object()
        return Response(
            {
                "message": documents.receipt_message(a, "advance"),
                "phone": a.customer.phone,
                "filename": documents.filename("Advance-Receipt", a.receipt_number),
            }
        )


@extend_schema(tags=["Advances"])
class AdvanceAdjustmentViewSet(mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """DELETE removes an adjustment (Admin) — the amount goes back to the advance and the invoice balance."""

    queryset = AdvanceAdjustment.objects.select_related("advance", "invoice")
    serializer_class = AdjustmentSerializer
    permission_classes = [RoleBasedPermission]
    allowed_roles = MANAGEMENT

    def perform_destroy(self, instance):
        services.remove_adjustment(adjustment=instance)


class PaymentFilter(DateRangeFilter):
    class Meta:
        model = Payment
        fields = ["customer", "project", "invoice", "mode", "cheque_status", "payment_stage"]


@extend_schema(tags=["Payments"])
class PaymentViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    """Customer payments against invoices or project stages. Cancel (Admin) instead of delete."""

    permission_classes = [RoleBasedPermission]
    allowed_roles = {"read": FINANCE, "write": FINANCE, "cancel": MANAGEMENT}
    filterset_class = PaymentFilter
    search_fields = [
        "receipt_number",
        "customer__name",
        "customer__phone",
        "reference_number",
        "cheque_number",
        "invoice__number",
    ]
    ordering_fields = ["date", "amount", "receipt_number"]
    ordering = ["-date", "-id"]

    def get_queryset(self):
        return Payment.objects.select_related(
            "customer", "project", "invoice", "payment_stage", "received_by"
        )

    def get_serializer_class(self):
        return PaymentCreateSerializer if self.action == "create" else PaymentSerializer

    def create(self, request, *args, **kwargs):
        s = PaymentCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        p = services.record_payment(**s.validated_data, received_by=request.user)
        return Response(PaymentSerializer(p).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=ReasonSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        s = ReasonSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.cancel_payment(payment=self.get_object(), reason=s.validated_data["reason"])
        return Response({"detail": "Receipt cancelled."})

    @extend_schema(request=ChequeSerializer, responses=PaymentSerializer)
    @action(detail=True, methods=["post"])
    def cheque(self, request, pk=None):
        """Mark a cheque as cleared or bounced. A bounce is debited back to the customer."""
        s = ChequeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        p = services.set_cheque_status(
            payment=self.get_object(), status=s.validated_data["status"], on=s.validated_data.get("date")
        )
        return Response(PaymentSerializer(p).data)

    @extend_schema(responses={(200, "application/pdf"): OpenApiResponse(description="PDF")})
    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        p = self.get_object()
        return _pdf(
            documents.payment_receipt_pdf(p), documents.filename("Receipt", p.receipt_number), request
        )

    @action(detail=True, methods=["get"], url_path="share-text")
    def share_text(self, request, pk=None):
        p = self.get_object()
        return Response(
            {
                "message": documents.receipt_message(p),
                "phone": p.customer.phone,
                "filename": documents.filename("Receipt", p.receipt_number),
            }
        )
