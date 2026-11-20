"""
Automatic audit trail for every model that inherits BaseModel.
Captures create / update (with field diff) / soft delete.
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .audit import diff, log_action, snapshot
from .models import AuditLog, BaseModel


def _is_audited(sender, instance=None):
    if instance is not None and getattr(instance, "_skip_audit", False):
        return False  # e.g. stock balance updates — StockMovement is the record of those
    return issubclass(sender, BaseModel) and not sender._meta.abstract


@receiver(pre_save)
def _audit_pre_save(sender, instance, **kwargs):
    if not _is_audited(sender, instance) or instance._state.adding or kwargs.get("raw"):
        return
    try:
        old = sender.all_objects.get(pk=instance.pk)
        instance._audit_before = snapshot(old)
    except sender.DoesNotExist:
        instance._audit_before = None


@receiver(post_save)
def _audit_post_save(sender, instance, created, **kwargs):
    if not _is_audited(sender, instance) or kwargs.get("raw"):
        return
    after = snapshot(instance)
    if created:
        log_action(AuditLog.Action.CREATE, instance, changes={})
        return
    before = getattr(instance, "_audit_before", None) or {}
    changes = diff(before, after)
    if not changes:
        return
    if "is_deleted" in changes:
        action = AuditLog.Action.DELETE if instance.is_deleted else AuditLog.Action.RESTORE
    else:
        action = AuditLog.Action.UPDATE
    log_action(action, instance, changes=changes)
