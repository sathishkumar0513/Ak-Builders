"""
Role-based access control (RBAC) used by every API in the project.

Usage on a ViewSet:

    class CustomerViewSet(ModelViewSet):
        permission_classes = [RoleBasedPermission]
        allowed_roles = {
            "read": SALES_AND_ABOVE,          # GET / HEAD / OPTIONS
            "write": MANAGEMENT + (SALES,),    # POST / PUT / PATCH / DELETE
            "destroy": MANAGEMENT,             # a specific action overrides read/write
        }

`allowed_roles` may also be a plain tuple that applies to every action.
Super Admin is always allowed. Users without a role are always denied.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import Role

SUPER_ADMIN = Role.SUPER_ADMIN
ADMIN = Role.ADMIN
ACCOUNTANT = Role.ACCOUNTANT
SITE_ENGINEER = Role.SITE_ENGINEER
SALES = Role.SALES

ALL_ROLES = (SUPER_ADMIN, ADMIN, ACCOUNTANT, SITE_ENGINEER, SALES)
MANAGEMENT = (SUPER_ADMIN, ADMIN)
FINANCE = (SUPER_ADMIN, ADMIN, ACCOUNTANT)
SALES_AND_ABOVE = (SUPER_ADMIN, ADMIN, ACCOUNTANT, SALES)
SITE_TEAM = (SUPER_ADMIN, ADMIN, SITE_ENGINEER)


def role_of(user):
    if not user or not user.is_authenticated:
        return None
    return user.role_code


def allowed_roles_for(view, request):
    spec = getattr(view, "allowed_roles", None)
    if spec is None:
        return ALL_ROLES
    if isinstance(spec, (list, tuple, set)):
        return tuple(spec)
    action = getattr(view, "action", None)
    if action and action in spec:
        return tuple(spec[action])
    key = "read" if request.method in SAFE_METHODS else "write"
    if key in spec:
        return tuple(spec[key])
    return tuple(spec.get("default", ()))


class RoleBasedPermission(BasePermission):
    message = "You do not have permission to perform this action."

    def has_permission(self, request, view):
        role = role_of(request.user)
        if role is None:
            return False
        if role == SUPER_ADMIN:
            return True
        return role in allowed_roles_for(view, request)


def HasRole(*roles):  # noqa: N802 — reads like a class in permission_classes
    """For function views: @permission_classes([HasRole(ADMIN, ACCOUNTANT)])."""

    class _HasRole(BasePermission):
        message = "You do not have permission to perform this action."

        def has_permission(self, request, view):
            role = role_of(request.user)
            return role == SUPER_ADMIN or (role is not None and role in roles)

    _HasRole.__name__ = f"HasRole({','.join(roles)})"
    return _HasRole
