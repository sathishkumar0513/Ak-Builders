"""User & authentication business logic. Views stay thin and call these functions."""

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.audit import diff, log_action
from apps.core.exceptions import BusinessRuleError
from apps.core.models import AuditLog, CompanySettings

from .models import Role, User

USER_AUDIT_FIELDS = ["username", "email", "first_name", "last_name", "phone", "role_id", "is_active"]


def _user_snapshot(user):
    return {f: (str(getattr(user, f)) if getattr(user, f) is not None else None) for f in USER_AUDIT_FIELDS}


def _guard_super_admin_target(actor, target):
    """Only a Super Admin may change another Super Admin."""
    if target.role_code == Role.SUPER_ADMIN and actor.role_code != Role.SUPER_ADMIN:
        raise BusinessRuleError("Only a Super Admin can change a Super Admin account.")


def _guard_last_super_admin(target, becoming_inactive=False, new_role=None):
    """Never leave the system without an active Super Admin."""
    if target.role_code != Role.SUPER_ADMIN:
        return
    losing = becoming_inactive or (new_role is not None and new_role.code != Role.SUPER_ADMIN)
    if not losing:
        return
    others = User.objects.filter(role__code=Role.SUPER_ADMIN, is_active=True, is_deleted=False).exclude(
        pk=target.pk
    )
    if not others.exists():
        raise BusinessRuleError("This is the last active Super Admin. Create another Super Admin first.")


def revoke_all_tokens(user):
    """Blacklist every refresh token of a user (logs them out on all devices)."""
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


def tokens_for(user):
    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role_code
    refresh["name"] = user.get_full_name() or user.username
    return {"refresh": str(refresh), "access": str(refresh.access_token)}


@transaction.atomic
def create_user(*, actor, data):
    password = data.pop("password")
    user = User(**data)
    user.set_password(password)
    user.must_change_password = True  # temporary password set by admin
    user.is_staff = user.role.code in (Role.SUPER_ADMIN, Role.ADMIN)
    user.save()
    log_action(
        AuditLog.Action.CREATE,
        user,
        changes={k: [None, v] for k, v in _user_snapshot(user).items()},
        user=actor,
    )
    return user


@transaction.atomic
def update_user(*, actor, user, data):
    _guard_super_admin_target(actor, user)
    new_role = data.get("role")
    if user.pk == actor.pk and new_role is not None and new_role != user.role:
        raise BusinessRuleError("You cannot change your own role.")
    if user.pk == actor.pk and data.get("is_active") is False:
        raise BusinessRuleError("You cannot deactivate your own account.")
    _guard_last_super_admin(user, becoming_inactive=data.get("is_active") is False, new_role=new_role)

    before = _user_snapshot(user)
    for field, value in data.items():
        setattr(user, field, value)
    user.is_staff = user.role_code in (Role.SUPER_ADMIN, Role.ADMIN)
    user.save()
    changes = diff(before, _user_snapshot(user))
    if changes:
        log_action(AuditLog.Action.UPDATE, user, changes=changes, user=actor)
    if changes.get("is_active") and not user.is_active:
        revoke_all_tokens(user)
    return user


def set_active(*, actor, user, active: bool):
    return update_user(actor=actor, user=user, data={"is_active": active})


@transaction.atomic
def soft_delete_user(*, actor, user):
    _guard_super_admin_target(actor, user)
    if user.pk == actor.pk:
        raise BusinessRuleError("You cannot delete your own account.")
    _guard_last_super_admin(user, becoming_inactive=True)
    user.is_active = False
    user.is_deleted = True
    user.save(update_fields=["is_active", "is_deleted", "updated_at"])
    revoke_all_tokens(user)
    log_action(AuditLog.Action.DELETE, user, user=actor)


@transaction.atomic
def admin_reset_password(*, actor, user, new_password):
    _guard_super_admin_target(actor, user)
    user.set_password(new_password)
    user.must_change_password = True
    user.save(update_fields=["password", "must_change_password", "updated_at"])
    revoke_all_tokens(user)
    log_action(AuditLog.Action.PASSWORD, user, changes={"reset_by_admin": [None, actor.username]}, user=actor)


@transaction.atomic
def change_own_password(*, user, new_password):
    user.set_password(new_password)
    user.must_change_password = False
    user.save(update_fields=["password", "must_change_password", "updated_at"])
    revoke_all_tokens(user)  # log out other devices
    log_action(AuditLog.Action.PASSWORD, user, changes={"changed_by_user": [None, True]}, user=user)
    return tokens_for(user)  # keep this device logged in


def send_password_reset_email(email: str):
    """Silently does nothing when the email is unknown (prevents account discovery)."""
    user = User.objects.filter(email__iexact=email.strip(), is_active=True, is_deleted=False).first()
    if not user:
        return
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password/{uid}/{token}"
    company = CompanySettings.load().name
    hours = settings.PASSWORD_RESET_TIMEOUT // 3600
    send_mail(
        subject=f"{company} – reset your password",
        message=(
            f"Hello {user.get_full_name() or user.username},\n\n"
            f"We received a request to reset your {company} password.\n"
            f"Open this link to choose a new password (valid for {hours} hours):\n\n{link}\n\n"
            "If you did not request this, you can ignore this email."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
    log_action(AuditLog.Action.PASSWORD, user, changes={"reset_link_sent": [None, True]}, user=None)


@transaction.atomic
def reset_password_with_token(*, user, new_password):
    user.set_password(new_password)
    user.must_change_password = False
    user.save(update_fields=["password", "must_change_password", "updated_at"])
    revoke_all_tokens(user)
    log_action(AuditLog.Action.PASSWORD, user, changes={"reset_via_email": [None, True]}, user=user)
