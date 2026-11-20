from django.db.models import Prefetch
from django.http import HttpResponse
from django_filters import rest_framework as filters
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.permissions import MANAGEMENT, SALES_AND_ABOVE, RoleBasedPermission
from apps.core.audit import log_action
from apps.core.exceptions import BusinessRuleError
from apps.core.models import AuditLog

from . import documents, services
from .models import Quotation, QuotationItem
from .serializers import (
    ConvertSerializer,
    DuplicateSerializer,
    EmailSerializer,
    QuotationListSerializer,
    QuotationSerializer,
    RejectSerializer,
)


class QuotationFilter(filters.FilterSet):
    date_from = filters.DateFilter(field_name="quotation_date", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="quotation_date", lookup_expr="lte")
    status = filters.MultipleChoiceFilter(choices=Quotation.Status.choices)
    all_revisions = filters.BooleanFilter(method="filter_all_revisions")

    class Meta:
        model = Quotation
        fields = ["customer", "status", "number"]

    def filter_all_revisions(self, qs, name, value):
        return qs  # handled in get_queryset (default: latest revision only)


@extend_schema(tags=["Quotations"])
class QuotationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    GST quotations with revisions. List shows the latest revision of each number
    (?all_revisions=true for every revision). Edit = DRAFT only; otherwise POST {id}/revise/.
    """

    permission_classes = [RoleBasedPermission]
    allowed_roles = {
        "read": SALES_AND_ABOVE,
        "write": SALES_AND_ABOVE,
        "convert": MANAGEMENT,
        "destroy": MANAGEMENT,
    }
    filterset_class = QuotationFilter
    search_fields = ["number", "title", "customer__name", "customer__phone", "items__description"]
    ordering_fields = ["quotation_date", "number", "grand_total", "valid_until", "created_at"]
    ordering = ["-quotation_date", "-id"]
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        qs = Quotation.objects.select_related("customer", "created_by")
        if self.action == "list":
            services.expire_due_quotations()
            if self.request.query_params.get("all_revisions") not in ("true", "1"):
                qs = qs.filter(is_latest=True)
            return qs.distinct()
        return qs.prefetch_related(
            Prefetch("items", queryset=QuotationItem.objects.select_related("material")), "projects"
        )

    def get_serializer_class(self):
        return QuotationListSerializer if self.action == "list" else QuotationSerializer

    def _detail(self, pk):
        return Response(
            QuotationSerializer(self.get_queryset().get(pk=pk), context=self.get_serializer_context()).data
        )

    def create(self, request, *args, **kwargs):
        s = QuotationSerializer(data=request.data, context=self.get_serializer_context())
        s.is_valid(raise_exception=True)
        data = dict(s.validated_data)
        items = data.pop("items")
        q = services.create_quotation(data=data, items=items)
        resp = self._detail(q.pk)
        resp.status_code = status.HTTP_201_CREATED
        return resp

    def partial_update(self, request, *args, **kwargs):
        q = self.get_object()
        s = QuotationSerializer(q, data=request.data, partial=True, context=self.get_serializer_context())
        s.is_valid(raise_exception=True)
        data = dict(s.validated_data)
        items = data.pop("items", None)
        services.update_quotation(quotation=q, data=data, items=items)
        return self._detail(q.pk)

    def destroy(self, request, *args, **kwargs):
        services.soft_delete_quotation(quotation=self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ---- status actions -------------------------------------------------
    @extend_schema(request=None, responses=QuotationSerializer)
    @action(detail=True, methods=["post"])
    def send(self, request, pk=None):
        """Mark as sent to the customer (use after sharing by WhatsApp / hand delivery)."""
        services.mark_sent(quotation=self.get_object())
        return self._detail(pk)

    @extend_schema(request=None, responses=QuotationSerializer)
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        services.approve(quotation=self.get_object())
        return self._detail(pk)

    @extend_schema(request=RejectSerializer, responses=QuotationSerializer)
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        s = RejectSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.reject(quotation=self.get_object(), reason=s.validated_data.get("reason", ""))
        return self._detail(pk)

    @extend_schema(request=None, responses=QuotationSerializer)
    @action(detail=True, methods=["post"])
    def revise(self, request, pk=None):
        """Create the next revision (Rev n+1) as a draft. Returns the new revision."""
        new = services.revise_quotation(quotation=self.get_object())
        resp = self._detail(new.pk)
        resp.status_code = status.HTTP_201_CREATED
        return resp

    @extend_schema(request=DuplicateSerializer, responses=QuotationSerializer)
    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        s = DuplicateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        new = services.duplicate_quotation(
            quotation=self.get_object(), customer=s.validated_data.get("customer")
        )
        resp = self._detail(new.pk)
        resp.status_code = status.HTTP_201_CREATED
        return resp

    @extend_schema(
        request=ConvertSerializer, responses={201: OpenApiResponse(description="{project: {id, code}}")}
    )
    @action(detail=True, methods=["post"])
    def convert(self, request, pk=None):
        """Approved quotation → Project with payment stages (default 30 / 40 / 30)."""
        s = ConvertSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = dict(s.validated_data)
        engineer_id = data.pop("assigned_engineer", None)
        engineer = None
        if engineer_id:
            engineer = User.objects.filter(pk=engineer_id, is_active=True, is_deleted=False).first()
            if engineer is None:
                raise BusinessRuleError("Select a valid active engineer.", field="assigned_engineer")
        project = services.convert_to_project(quotation=self.get_object(), assigned_engineer=engineer, **data)
        return Response(
            {
                "project": {"id": project.id, "code": project.code, "name": project.name},
                "quotation": QuotationSerializer(
                    self.get_queryset().get(pk=pk), context=self.get_serializer_context()
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )

    # ---- documents ------------------------------------------------------
    @extend_schema(responses={(200, "application/pdf"): OpenApiResponse(description="PDF file")})
    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        """PDF with company logo. ?download=1 to force download instead of opening inline."""
        q = self.get_object()
        response = HttpResponse(documents.quotation_pdf(q), content_type="application/pdf")
        disposition = "attachment" if request.query_params.get("download") in ("1", "true") else "inline"
        response["Content-Disposition"] = f'{disposition}; filename="{documents.pdf_filename(q)}"'
        return response

    @extend_schema(responses={200: OpenApiResponse(description="{message, phone, filename}")})
    @action(detail=True, methods=["get"], url_path="share-text")
    def share_text(self, request, pk=None):
        """Ready-made WhatsApp / SMS message for this quotation."""
        q = self.get_object()
        return Response(
            {
                "message": documents.default_share_message(q),
                "phone": q.customer.phone,
                "email": q.customer.email,
                "filename": documents.pdf_filename(q),
            }
        )

    @extend_schema(request=EmailSerializer, responses=QuotationSerializer)
    @action(detail=True, methods=["post"])
    def email(self, request, pk=None):
        """Email the PDF to the customer. A draft is marked as sent automatically."""
        q = self.get_object()
        s = EmailSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            documents.email_quotation(q, **s.validated_data)
        except Exception as exc:  # SMTP problems → readable error, not a 500
            raise BusinessRuleError(f"Email could not be sent: {exc}")
        log_action(
            AuditLog.Action.EXPORT, q, changes={"emailed_to": [None, ", ".join(s.validated_data["to"])]}
        )
        if q.status == Quotation.Status.DRAFT and q.is_latest:
            services.mark_sent(quotation=q)
        return self._detail(pk)
