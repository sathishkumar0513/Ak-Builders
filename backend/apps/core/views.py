from django.conf import settings
from django.db import connection
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.accounts.permissions import ALL_ROLES, MANAGEMENT, SALES_AND_ABOVE, SUPER_ADMIN, RoleBasedPermission

from .audit import diff, log_action, snapshot
from .cities import CITIES
from .models import AuditLog, CompanySettings, DocumentSequence, TermsTemplate
from .serializers import (
    AuditLogSerializer,
    CompanySettingsSerializer,
    DocumentSequenceSerializer,
    TermsTemplateSerializer,
)
from .utils import INDIAN_STATES, STATE_CHOICES


@extend_schema(tags=["System"], responses={200: dict})
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """Liveness/readiness check used by Docker and Nginx."""
    with connection.cursor() as cur:
        cur.execute("SELECT 1")
    return Response({"status": "ok", "app": "AK Builders Management System", "database": "ok"})


@extend_schema(tags=["System"], responses={200: dict})
@api_view(["GET"])
def lookups(request):
    """Static choice lists for dropdowns (states, payment modes, units)."""
    from .models import PaymentMode, Unit

    return Response(
        {
            # state name only (the GST code stays the value); home state first, then A–Z
            "states": sorted(
                ({"value": v, "label": label} for v, label in STATE_CHOICES),
                key=lambda s: (s["value"] != settings.COMPANY_STATE_CODE, s["label"]),
            ),
            "payment_modes": [{"value": v, "label": label} for v, label in PaymentMode.choices],
            "units": [{"value": v, "label": label} for v, label in Unit.choices],
        }
    )


class AuditLogFilter(filters.FilterSet):
    date_from = filters.DateFilter(field_name="timestamp", lookup_expr="date__gte")
    date_to = filters.DateFilter(field_name="timestamp", lookup_expr="date__lte")

    class Meta:
        model = AuditLog
        fields = ["action", "model_name", "user", "object_id"]


@extend_schema(tags=["Audit log"])
class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Who created, edited or deleted what, and when. Read-only. Super Admin / Admin."""

    queryset = AuditLog.objects.select_related("user")
    serializer_class = AuditLogSerializer
    permission_classes = [RoleBasedPermission]
    allowed_roles = MANAGEMENT
    filterset_class = AuditLogFilter
    search_fields = ["object_repr", "model_name", "user__username", "user__first_name"]
    ordering_fields = ["timestamp", "action", "model_name"]
    ordering = ["-timestamp"]


@extend_schema(tags=["Settings"])
class CompanySettingsView(RetrieveUpdateAPIView):
    """GET: every logged-in user (name/logo on documents). PATCH: Super Admin/Admin. Logo upload."""

    serializer_class = CompanySettingsSerializer
    permission_classes = [RoleBasedPermission]
    allowed_roles = {"read": ALL_ROLES, "write": MANAGEMENT}
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    http_method_names = ["get", "patch"]

    def get_object(self):
        return CompanySettings.load()

    def perform_update(self, serializer):
        before = snapshot(serializer.instance)
        instance = serializer.save()
        changes = diff(before, snapshot(instance))
        if changes:
            log_action(AuditLog.Action.UPDATE, instance, changes=changes)


@extend_schema(tags=["Settings"])
class DocumentSequenceViewSet(mixins.ListModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Number series (prefix, padding, next number). Editing is Super Admin only."""

    queryset = DocumentSequence.objects.all().order_by("-financial_year", "doc_type")
    serializer_class = DocumentSequenceSerializer
    permission_classes = [RoleBasedPermission]
    allowed_roles = {"read": MANAGEMENT, "write": (SUPER_ADMIN,)}
    pagination_class = None
    filter_backends = []
    http_method_names = ["get", "patch"]

    def perform_update(self, serializer):
        before = snapshot(serializer.instance)
        instance = serializer.save()
        log_action(AuditLog.Action.UPDATE, instance, changes=diff(before, snapshot(instance)))


@extend_schema(tags=["Settings"])
class TermsTemplateViewSet(viewsets.ModelViewSet):
    """Reusable terms & conditions. Setting is_default=true un-sets the previous default of the same type."""

    serializer_class = TermsTemplateSerializer
    permission_classes = [RoleBasedPermission]
    allowed_roles = {"read": SALES_AND_ABOVE, "write": MANAGEMENT}
    filterset_fields = ["applies_to"]
    pagination_class = None
    ordering = ["applies_to", "-is_default", "title"]
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        return TermsTemplate.objects.all()

    def perform_create(self, serializer):
        self._save(serializer)

    def perform_update(self, serializer):
        self._save(serializer)

    def _save(self, serializer):
        obj = serializer.save()
        if obj.is_default:
            TermsTemplate.objects.filter(applies_to=obj.applies_to, is_default=True).exclude(
                pk=obj.pk
            ).update(is_default=False)

    def perform_destroy(self, instance):
        instance.soft_delete(self.request.user)


@extend_schema(tags=["Settings"], responses={200: {"type": "array", "items": {"type": "string"}}})
@api_view(["GET"])
def city_suggestions(request):
    """City names for a state: the built-in list plus every city already used in the system
    (customers, suppliers, company, project sites). ?state=33 (default: the company's state)."""
    from apps.customers.models import Customer
    from apps.projects.models import Project
    from apps.suppliers.models import Supplier

    code = request.query_params.get("state") or settings.COMPANY_STATE_CODE
    if code not in INDIAN_STATES:
        return Response([])
    used = set(Customer.objects.filter(state_code=code).values_list("city", flat=True))
    used |= set(Supplier.objects.filter(state_code=code).values_list("city", flat=True))
    company = CompanySettings.load()
    if company.state_code == code:
        used.add(company.city)
    if code == settings.COMPANY_STATE_CODE:  # project sites have no state; most are local
        used |= set(Project.objects.values_list("site_city", flat=True))
    names = {c.strip(): None for c in [*CITIES.get(code, []), *used] if c and c.strip()}
    return Response(sorted(names, key=str.lower))
