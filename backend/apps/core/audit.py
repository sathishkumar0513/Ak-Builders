"""Helpers to write AuditLog rows. Called from services (Phase 2+) and generic signals below."""

from django.forms.models import model_to_dict

from .middleware import get_current_ip, get_current_user
from .models import AuditLog

SKIP_FIELDS = {"updated_at", "created_at", "password", "last_login"}


def snapshot(instance) -> dict:
    data = model_to_dict(instance)
    return {k: (str(v) if v is not None else None) for k, v in data.items() if k not in SKIP_FIELDS}


def diff(before: dict, after: dict) -> dict:
    return {k: [before.get(k), v] for k, v in after.items() if before.get(k) != v}


def log_action(
    action, instance=None, changes=None, user=None, model_name=None, object_id=None, object_repr=None
):
    return AuditLog.objects.create(
        user=user or get_current_user(),
        action=action,
        model_name=model_name or (instance._meta.label if instance is not None else ""),
        object_id=str(object_id or getattr(instance, "pk", "") or ""),
        object_repr=(object_repr or (str(instance) if instance is not None else ""))[:255],
        changes=changes or {},
        ip_address=get_current_ip(),
    )
