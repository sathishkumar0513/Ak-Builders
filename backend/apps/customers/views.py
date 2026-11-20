from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import FINANCE, MANAGEMENT, SALES_AND_ABOVE, RoleBasedPermission
from apps.core.mixins import SoftDeleteViewSetMixin

from .models import Customer
from .serializers import CustomerSerializer
from .services import customer_summary, outstanding_annotation


class CustomerFilter(filters.FilterSet):
    city = filters.CharFilter(lookup_expr="iexact")
    has_gstin = filters.BooleanFilter(method="filter_has_gstin", label="Has GSTIN")

    class Meta:
        model = Customer
        fields = ["customer_type", "city", "state_code"]

    def filter_has_gstin(self, qs, name, value):
        return qs.exclude(gstin="") if value else qs.filter(gstin="")


@extend_schema(tags=["Customers"])
class CustomerViewSet(SoftDeleteViewSetMixin, viewsets.ModelViewSet):
    serializer_class = CustomerSerializer
    permission_classes = [RoleBasedPermission]
    allowed_roles = {
        "read": SALES_AND_ABOVE,
        "write": SALES_AND_ABOVE,
        "destroy": MANAGEMENT,
        "restore": MANAGEMENT,
        "ledger": FINANCE,
        "open_items": FINANCE,
    }
    filterset_class = CustomerFilter
    search_fields = ["name", "phone", "alternate_phone", "email", "gstin", "city", "contact_person"]
    ordering_fields = ["name", "city", "created_at", "outstanding"]
    ordering = ["name"]
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        return Customer.objects.annotate(outstanding=outstanding_annotation())

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        """Totals and recent activity for the customer detail page."""
        return Response(customer_summary(self.get_object()))

    @action(detail=False, methods=["get"])
    def cities(self, request):
        """Distinct cities for the filter dropdown."""
        cities = Customer.objects.exclude(city="").order_by("city").values_list("city", flat=True).distinct()
        return Response(list(cities))

    @action(detail=True, methods=["get"])
    def ledger(self, request, pk=None):
        """Statement with running balance. ?date_from=&date_to= (opening balance carried forward)."""
        from django.utils.dateparse import parse_date

        from apps.payments.ledger import statement

        return Response(
            statement(
                self.get_object(),
                parse_date(request.query_params.get("date_from") or ""),
                parse_date(request.query_params.get("date_to") or ""),
            )
        )

    @action(detail=True, methods=["get"], url_path="open-items")
    def open_items(self, request, pk=None):
        """Unpaid invoices, un-invoiced project stages and unused advances of this customer."""
        from apps.invoices.models import Invoice
        from apps.payments.models import AdvancePayment
        from apps.projects.models import PaymentStage

        c = self.get_object()
        invoices = Invoice.objects.filter(customer=c, status__in=["UNPAID", "PARTIAL"]).order_by(
            "invoice_date"
        )
        stages = PaymentStage.objects.filter(project__customer=c, project__is_deleted=False).exclude(
            status="PAID"
        )
        stages = [
            s for s in stages.select_related("project") if not s.invoices.exclude(status="CANCELLED").exists()
        ]
        advances = AdvancePayment.objects.filter(customer=c, status__in=["OPEN", "PARTIAL"])
        return Response(
            {
                "invoices": [
                    {
                        "id": i.id,
                        "number": i.number,
                        "date": i.invoice_date,
                        "grand_total": str(i.grand_total),
                        "balance_due": str(i.balance_due),
                        "project": i.project_id,
                    }
                    for i in invoices
                ],
                "stages": [
                    {
                        "id": s.id,
                        "name": s.name,
                        "project": s.project_id,
                        "project_code": s.project.code,
                        "amount": str(s.amount),
                        "balance": str(s.amount - s.amount_received),
                    }
                    for s in stages
                ],
                "advances": [
                    {
                        "id": a.id,
                        "receipt_number": a.receipt_number,
                        "date": a.date,
                        "balance": str(a.balance),
                        "project": a.project_id,
                    }
                    for a in advances
                ],
            }
        )
