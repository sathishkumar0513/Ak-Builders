from rest_framework import serializers

from apps.core.serializer_fields import validate_gstin_for_state, validate_indian_mobile
from apps.core.utils import INDIAN_STATES

from .models import Customer


class CustomerSerializer(serializers.ModelSerializer):
    state_name = serializers.SerializerMethodField()
    customer_type_display = serializers.CharField(source="get_customer_type_display", read_only=True)
    outstanding = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True, default=None)
    # raw input like "+91 98765-43210" is accepted and normalised in validate_phone
    phone = serializers.CharField(max_length=20)
    alternate_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    gstin = serializers.CharField(max_length=15, required=False, allow_blank=True)  # checked in validate()

    class Meta:
        model = Customer
        fields = [
            "id",
            "name",
            "customer_type",
            "customer_type_display",
            "contact_person",
            "phone",
            "alternate_phone",
            "email",
            "address",
            "city",
            "state_code",
            "state_name",
            "pincode",
            "gstin",
            "notes",
            "outstanding",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_state_name(self, obj) -> str:
        return INDIAN_STATES.get(obj.state_code, "")

    def validate_name(self, value):
        value = " ".join(value.split())
        if len(value) < 2:
            raise serializers.ValidationError("Enter the customer name.")
        return value

    def validate_phone(self, value):
        value = validate_indian_mobile(value)
        qs = Customer.objects.filter(phone=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        existing = qs.first()
        if existing:
            raise serializers.ValidationError(f"This mobile number already belongs to {existing.name}.")
        return value

    def validate_alternate_phone(self, value):
        return validate_indian_mobile(value, required=False)

    def validate_email(self, value):
        return (value or "").strip().lower()

    def validate(self, attrs):
        attrs = validate_gstin_for_state(attrs, self.instance)
        ctype = attrs.get("customer_type", getattr(self.instance, "customer_type", None))
        if ctype == Customer.CustomerType.COMPANY and not attrs.get(
            "contact_person", getattr(self.instance, "contact_person", "")
        ):
            raise serializers.ValidationError({"contact_person": "Enter a contact person for a company."})
        return attrs
