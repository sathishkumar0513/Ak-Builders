from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.core.middleware import set_current_user


class JWTAuthenticationWithContext(JWTAuthentication):
    """
    Standard SimpleJWT auth + publishes the user to apps.core.middleware so that
    created_by / updated_by / AuditLog.user are filled automatically for API requests.
    Also rejects soft-deleted users even if their token is still valid.
    """

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            user, _token = result
            if getattr(user, "is_deleted", False):
                return None
            set_current_user(user)
        return result
