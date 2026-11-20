from rest_framework import serializers

from .exceptions import BusinessRuleError
from .models import AuditLog, CompanySettings, DocumentSequence
from .uploads import validate_image_upload
from .utils import INDIAN_STATES


class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    action_display = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "timestamp",
            "user",
            "user_name",
            "action",
            "action_display",
            "model_name",
            "object_id",
            "object_repr",
            "changes",
            "ip_address",
        ]

    def get_user_name(self, obj) -> str:
        if not obj.user_id:
            return "System / anonymous"
        return obj.user.get_full_name() or obj.user.username


class CompanySettingsSerializer(serializers.ModelSerializer):
    gstin = serializers.RegexField(
        r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$",
        required=False,
        allow_blank=True,
        error_messages={"invalid": "Enter a valid 15-character GSTIN."},
    )
    bank_ifsc = serializers.RegexField(
        r"^[A-Z]{4}0[A-Z0-9]{6}$",
        required=False,
        allow_blank=True,
        error_messages={"invalid": "Enter a valid 11-character IFSC code."},
    )
    pincode = serializers.RegexField(
        r"^\d{6}$",
        required=False,
        allow_blank=True,
        error_messages={"invalid": "Enter a valid 6-digit pincode."},
    )
    remove_logo = serializers.BooleanField(write_only=True, required=False)

    class Meta:
        model = CompanySettings
        exclude = ["created_by", "updated_by", "created_at"]
        read_only_fields = ["updated_at"]

    def validate_state_code(self, value):
        if value not in INDIAN_STATES:
            raise serializers.ValidationError("Unknown state code.")
        return value

    def validate(self, attrs):
        if "state_code" in attrs:
            attrs["state"] = INDIAN_STATES[attrs["state_code"]]
        gstin = attrs.get("gstin")
        code = attrs.get("state_code", getattr(self.instance, "state_code", None))
        if gstin and code and gstin[:2] != code:
            raise serializers.ValidationError({"gstin": "GSTIN state code does not match the company state."})
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Relative URL (/media/...) works from a phone on the LAN and behind Nginx alike
        data["logo"] = instance.logo.url if instance.logo else None
        return data

    def validate_logo(self, value):
        try:
            validate_image_upload(value, field="logo", max_mb=2)
        except BusinessRuleError as e:
            raise serializers.ValidationError(e.message) from e
        return value

    def update(self, instance, validated_data):
        if validated_data.pop("remove_logo", False):
            instance.logo.delete(save=False)
            instance.logo = None
        return super().update(instance, validated_data)


class DocumentSequenceSerializer(serializers.ModelSerializer):
    doc_type_display = serializers.CharField(source="get_doc_type_display", read_only=True)
    preview = serializers.SerializerMethodField()

    class Meta:
        model = DocumentSequence
        fields = [
            "id",
            "doc_type",
            "doc_type_display",
            "financial_year",
            "prefix",
            "padding",
            "next_number",
            "preview",
        ]
        read_only_fields = ["doc_type", "financial_year"]

    def get_preview(self, obj) -> str:
        return f"{obj.prefix}/{obj.financial_year}/{str(obj.next_number).zfill(obj.padding)}"

    def validate_next_number(self, value):
        if self.instance and value < self.instance.next_number:
            raise serializers.ValidationError(
                f"Cannot go below {self.instance.next_number} — numbers already issued would repeat."
            )
        return value

    def validate_padding(self, value):
        if not 1 <= value <= 8:
            raise serializers.ValidationError("Use between 1 and 8 digits.")
        return value

    def validate_prefix(self, value):
        value = value.strip().strip("/")
        if not value:
            raise serializers.ValidationError("Prefix is required.")
        return value


class TermsTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import TermsTemplate

        model = TermsTemplate
        fields = ["id", "title", "applies_to", "content", "is_default", "updated_at"]
        read_only_fields = ["updated_at"]
