import re

from rest_framework import serializers

from .utils import INDIAN_STATES

GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


def normalize_phone(value: str) -> str:
    """'+91 98765-43210' → '9876543210'."""
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits


def validate_indian_mobile(value: str, required=True) -> str:
    value = normalize_phone(value)
    if not value and not required:
        return ""
    if not re.fullmatch(r"[6-9]\d{9}", value):
        raise serializers.ValidationError("Enter a valid 10-digit mobile number.")
    return value


def validate_gstin_for_state(attrs, instance=None, gstin_field="gstin", state_field="state_code"):
    """Uppercases GSTIN and checks its first two digits match the party's state code."""
    gstin = attrs.get(gstin_field, getattr(instance, gstin_field, "") if instance else "")
    if gstin_field in attrs:
        gstin = (attrs[gstin_field] or "").strip().upper()
        attrs[gstin_field] = gstin
    if not gstin:
        return attrs
    if not GSTIN_RE.match(gstin):
        raise serializers.ValidationError({gstin_field: "Enter a valid 15-character GSTIN."})
    state = attrs.get(state_field, getattr(instance, state_field, None) if instance else None)
    if state and gstin[:2] != state:
        raise serializers.ValidationError(
            {
                gstin_field: f"GSTIN starts with {gstin[:2]} but the state is {state} "
                f"({INDIAN_STATES.get(state, '?')})."
            }
        )
    return attrs
