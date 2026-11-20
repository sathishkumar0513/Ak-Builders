from decimal import Decimal

from rest_framework import serializers

from apps.projects.models import Project

from .models import Expense


class ExpenseSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(), allow_null=True, required=False
    )
    project_code = serializers.CharField(source="project.code", read_only=True, default=None)
    project_name = serializers.CharField(source="project.name", read_only=True, default=None)
    category_display = serializers.CharField(source="get_category_display", read_only=True)
    mode_display = serializers.CharField(source="get_mode_display", read_only=True)
    created_by_name = serializers.StringRelatedField(source="created_by", read_only=True)
    approved_by_name = serializers.StringRelatedField(source="approved_by", read_only=True)
    is_approved = serializers.BooleanField(read_only=True)
    bill_attachment = serializers.FileField(required=False, allow_null=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))

    class Meta:
        model = Expense
        fields = [
            "id",
            "voucher_number",
            "project",
            "project_code",
            "project_name",
            "category",
            "category_display",
            "date",
            "amount",
            "paid_to",
            "mode",
            "mode_display",
            "reference_number",
            "description",
            "workers_count",
            "work_days",
            "bill_attachment",
            "is_approved",
            "approved_by_name",
            "approved_at",
            "created_by",
            "created_by_name",
            "created_at",
        ]
        read_only_fields = ["voucher_number", "approved_at", "created_by", "created_at"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.bill_attachment:  # relative URL so it works through the Vite/Nginx proxy
            data["bill_attachment"] = instance.bill_attachment.url
        return data


class ExpenseSummarySerializer(serializers.Serializer):
    total = serializers.DecimalField(max_digits=14, decimal_places=2)
    count = serializers.IntegerField()
    pending_approval = serializers.IntegerField()
    by_category = serializers.ListField(child=serializers.DictField())
