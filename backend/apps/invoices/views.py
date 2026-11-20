from datetime import date

from django.db.models import Prefetch
from django.http import HttpResponse
from django_filters import rest_framework as filters
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import FINANCE, MANAGEMENT, RoleBasedPermission
from apps.core.audit import log_action
from apps.core.exceptions import BusinessRuleError
from apps.core.models import AuditLog
from apps.payments.models import PaymentReminder
from apps.quotations.models import Quotation
from apps.quotations.serializers import EmailSerializer

from . import documents, services
from .models import Invoice, InvoiceItem
from .serializers import (
    FromStageSerializer,
    InvoiceCancelSerializer,
    InvoiceListSerializer,
    InvoiceSerializer,
)


class InvoiceFilter(filters.FilterSet):
    date_from = filters.DateFilter(field_name="invoice_date", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="invoice_date", lookup_expr="lte")
    status = filters.MultipleChoiceFilter(choices=Invoice.Status.choices)
    overdue = filters.BooleanFilter(method="filter_overdue")

    class Meta:
        model = Invoice
        fields = ["customer", "project", "status", "payment_stage"]

    def filter_overdue(self, qs, name, value):
        cond = {"status__in": ["UNPAID", "PARTIAL"], "due_date__lt": date.today()}
        return qs.filter(**cond) if value else qs.exclude(**cond)


@extend_schema(tags=["Invoices"])
class InvoiceViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """GST tax invoices (AK/2026-27/0001). Advances are adjusted automatically. Cancel instead of delete."""

    permission_classes = [RoleBasedPermission]
    allowed_roles = {"read": FINANCE, "write": FINANCE, "cancel": MANAGEMENT}
    filterset_class = InvoiceFilter
    search_fields = ["number", "billing_name", "customer__phone", "project__code", "items__description"]
    ordering_fields = ["invoice_date", "number", "grand_total", "balance_due", "due_date"]
    ordering = ["-invoice_date", "-id"]
    http_method_names = ["get", "post", "patch"]

    def get_queryset(self):
        qs = Invoice.objects.select_related("customer", "project", "payment_stage", "quotation")
        if self.action == "list":
            return qs.distinct()
        return qs.prefetch_related(Prefetch("items", queryset=InvoiceItem.objects.select_related("material")))

    def get_serializer_class(self):
        return InvoiceListSerializer if self.action in ("list", "overdue") else InvoiceSerializer

    def _detail(self, pk, code=200):
        return Response(
            InvoiceSerializer(self.get_queryset().get(pk=pk), context=self.get_serializer_context()).data,
            status=code,
        )

    def create(self, request, *args, **kwargs):
        s = InvoiceSerializer(data=request.data, context=self.get_serializer_context())
        s.is_valid(raise_exception=True)
        data = dict(s.validated_data)
        items = data.pop("items")
        auto = data.pop("auto_adjust_advance", True)
        inv = services.create_invoice(data=data, items=items, auto_adjust_advance=auto)
        return self._detail(inv.pk, status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        inv = self.get_object()
        s = InvoiceSerializer(inv, data=request.data, partial=True, context=self.get_serializer_context())
        s.is_valid(raise_exception=True)
        data = dict(s.validated_data)
        items = data.pop("items", None)
        data.pop("auto_adjust_advance", None)
        services.update_invoice(invoice=inv, data=data, items=items)
        return self._detail(inv.pk)

    @extend_schema(request=InvoiceCancelSerializer, responses=InvoiceSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Cancel (Admin). Adjusted advances are released; ledger gets a reversal entry."""
        s = InvoiceCancelSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.cancel_invoice(invoice=self.get_object(), reason=s.validated_data["reason"])
        return self._detail(pk)

    @extend_schema(request=FromStageSerializer, responses=InvoiceSerializer)
    @action(detail=False, methods=["post"], url_path="from-stage")
    def from_stage(self, request):
        """Bill a project payment stage: one service line whose total (incl. GST) equals the stage amount."""
        s = FromStageSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        stage = s.validated_data["payment_stage"]
        if stage.invoices.exclude(status="CANCELLED").exists():
            raise BusinessRuleError(f"Stage '{stage.name}' is already invoiced.", field="payment_stage")
        if stage.amount_received > 0:
            raise BusinessRuleError(
                "Payments were taken directly against this stage — invoice manually instead.",
                field="payment_stage",
            )
        project = stage.project
        items = services.stage_invoice_items(stage, s.validated_data["gst_rate"], s.validated_data["sac"])
        inv = services.create_invoice(
            data={
                "customer": project.customer,
                "project": project,
                "payment_stage": stage,
                "quotation": project.quotation,
            },
            items=items,
        )
        return self._detail(inv.pk, status.HTTP_201_CREATED)

    @extend_schema(responses={200: OpenApiResponse(description="Prefill data for the invoice form")})
    @action(detail=False, methods=["get"])
    def prefill(self, request):
        """?quotation=<id> → customer, project and items copied from the quotation."""
        q = (
            Quotation.objects.filter(pk=request.query_params.get("quotation"))
            .select_related("customer")
            .first()
        )
        if not q:
            raise BusinessRuleError("Quotation not found.")
        project = q.projects.first()
        items = [
            {
                **i,
                "material": i["material"].id if i["material"] else None,
                "quantity": str(i["quantity"]),
                "rate": str(i["rate"]),
                "discount_percent": str(i["discount_percent"]),
                "gst_rate": str(i["gst_rate"]),
            }
            for i in services.items_from_quotation(q)
        ]
        return Response(
            {
                "customer": q.customer_id,
                "project": project.id if project else None,
                "quotation": q.id,
                "header_discount": str(q.header_discount),
                "items": items,
                "title": q.title,
            }
        )

    @extend_schema(responses=InvoiceListSerializer(many=True))
    @action(detail=False, methods=["get"])
    def overdue(self, request):
        """Unpaid / part-paid invoices past their due date, with ageing bucket."""
        rows = []
        for inv in services.overdue_queryset().order_by("due_date"):
            d = InvoiceListSerializer(inv).data
            d["days_overdue"] = (date.today() - inv.due_date).days
            d["bucket"] = services.ageing_bucket(inv)
            rows.append(d)
        return Response(
            {
                "count": len(rows),
                "total": str(sum(i.balance_due for i in services.overdue_queryset())),
                "results": rows,
            }
        )

    @extend_schema(responses={(200, "application/pdf"): OpenApiResponse(description="PDF")})
    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        inv = self.get_object()
        response = HttpResponse(documents.invoice_pdf(inv), content_type="application/pdf")
        disposition = "attachment" if request.query_params.get("download") in ("1", "true") else "inline"
        response["Content-Disposition"] = f'{disposition}; filename="{documents.pdf_filename(inv)}"'
        return response

    @action(detail=True, methods=["get"], url_path="share-text")
    def share_text(self, request, pk=None):
        inv = self.get_object()
        reminder = request.query_params.get("reminder") in ("1", "true")
        return Response(
            {
                "message": documents.reminder_message(inv) if reminder else documents.share_message(inv),
                "phone": inv.customer.phone,
                "email": inv.customer.email,
                "filename": documents.pdf_filename(inv),
            }
        )

    @action(detail=True, methods=["post"], url_path="log-reminder")
    def log_reminder(self, request, pk=None):
        """Record that a payment reminder was sent (WhatsApp / SMS / email) — shown in the invoice history."""
        inv = self.get_object()
        channel = request.data.get("channel", "WHATSAPP")
        if channel not in PaymentReminder.Channel.values:
            raise BusinessRuleError("Unknown reminder channel.", field="channel")
        from django.utils import timezone

        PaymentReminder.objects.create(
            customer=inv.customer,
            invoice=inv,
            channel=channel,
            scheduled_for=timezone.now(),
            sent_at=timezone.now(),
            status=PaymentReminder.Status.SENT,
            message=documents.reminder_message(inv),
        )
        return Response({"detail": "Reminder logged."})

    @extend_schema(request=EmailSerializer, responses=InvoiceSerializer)
    @action(detail=True, methods=["post"])
    def email(self, request, pk=None):
        inv = self.get_object()
        s = EmailSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            documents.email_invoice(inv, **s.validated_data)
        except Exception as exc:
            raise BusinessRuleError(f"Email could not be sent: {exc}")
        log_action(
            AuditLog.Action.EXPORT, inv, changes={"emailed_to": [None, ", ".join(s.validated_data["to"])]}
        )
        return self._detail(pk)
