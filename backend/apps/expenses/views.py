from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.accounts.permissions import FINANCE, MANAGEMENT, SITE_ENGINEER, RoleBasedPermission

from . import services
from .models import Expense
from .serializers import ExpenseSerializer, ExpenseSummarySerializer

EXPENSE_TEAM = FINANCE + (SITE_ENGINEER,)


class ExpenseFilter(filters.FilterSet):
    date_from = filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="date", lookup_expr="lte")
    category = filters.MultipleChoiceFilter(choices=Expense.Category.choices)
    approved = filters.BooleanFilter(field_name="approved_at", lookup_expr="isnull", exclude=True)
    overhead = filters.BooleanFilter(field_name="project", lookup_expr="isnull")

    class Meta:
        model = Expense
        fields = ["project", "category", "mode", "created_by"]


@extend_schema(tags=["Expenses"])
class ExpenseViewSet(viewsets.ModelViewSet):
    """Labour, transport, site and office expenses. Site engineers add expenses for their projects;
    the office approves them. Project expenses feed project profit / loss."""

    serializer_class = ExpenseSerializer
    permission_classes = [RoleBasedPermission]
    allowed_roles = {
        "read": EXPENSE_TEAM,
        "write": EXPENSE_TEAM,
        "approve": FINANCE,
        "destroy": MANAGEMENT,
    }
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filterset_class = ExpenseFilter
    search_fields = [
        "voucher_number",
        "paid_to",
        "description",
        "reference_number",
        "project__code",
        "project__name",
    ]
    ordering_fields = ["date", "amount", "voucher_number", "category"]
    ordering = ["-date", "-id"]

    def get_queryset(self):
        qs = Expense.objects.select_related("project", "created_by", "approved_by")
        return services.visible_expenses_for(self.request.user, qs)

    def perform_create(self, serializer):
        serializer.instance = services.create_expense(user=self.request.user, **serializer.validated_data)

    def perform_update(self, serializer):
        services.update_expense(serializer.instance, user=self.request.user, **serializer.validated_data)

    def perform_destroy(self, instance):
        services.delete_expense(instance, user=self.request.user)

    @extend_schema(request=None, responses=ExpenseSerializer)
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        exp = services.approve_expense(self.get_object(), user=request.user)
        return Response(self.get_serializer(exp).data)

    @extend_schema(request=None, responses=ExpenseSerializer)
    @action(detail=True, methods=["post"], url_path="remove-bill")
    def remove_bill(self, request, pk=None):
        exp = self.get_object()
        services.update_expense(exp, user=request.user)  # same edit rules
        exp.bill_attachment = None
        exp.save(update_fields=["bill_attachment", "updated_at"])
        return Response(self.get_serializer(exp).data, status=status.HTTP_200_OK)

    @extend_schema(responses=ExpenseSummarySerializer)
    @action(detail=False, methods=["get"])
    def summary(self, request):
        qs = self.filter_queryset(self.get_queryset())
        return Response(ExpenseSummarySerializer(services.summary(qs)).data)
