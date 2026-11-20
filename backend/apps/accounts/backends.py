from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class UsernameOrEmailBackend(ModelBackend):
    """Log in with either username or email (case-insensitive). Soft-deleted users can never log in."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        if not username or not password:
            return None
        username = username.strip()
        try:
            user = User.objects.get(
                Q(username__iexact=username) | Q(email__iexact=username), is_deleted=False
            )
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            User().set_password(password)  # equalise timing to avoid user enumeration
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def user_can_authenticate(self, user):
        return super().user_can_authenticate(user) and not getattr(user, "is_deleted", False)
