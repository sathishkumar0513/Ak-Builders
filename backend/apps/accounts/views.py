from django.conf import settings
from django_filters import rest_framework as filters
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.core.audit import log_action
from apps.core.models import AuditLog

from . import lockout, services
from .models import Role, User
from .permissions import ALL_ROLES, MANAGEMENT, RoleBasedPermission
from .serializers import (
    AdminSetPasswordSerializer,
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    LogoutSerializer,
    ProfileSerializer,
    ResetPasswordSerializer,
    RoleSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)

AUTH_TAG = ["Auth"]


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
@extend_schema(tags=AUTH_TAG)
class LoginView(TokenObtainPairView):
    """POST {username, password} → {access, refresh, user}. `username` may be an email. Rate-limited."""

    serializer_class = LoginSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request, *args, **kwargs):
        attempted = str(request.data.get("username", ""))[:150]
        if lockout.is_locked(attempted):
            minutes = getattr(settings, "LOGIN_LOCKOUT_MINUTES", 15)
            return Response(
                {"detail": f"Too many wrong passwords. This account is locked for {minutes} minutes."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        try:
            response = super().post(request, *args, **kwargs)
        except Exception:
            if lockout.register_failure(attempted) == getattr(settings, "LOGIN_MAX_FAILURES", 5):
                log_action(
                    AuditLog.Action.LOGIN_FAILED,
                    model_name="accounts.User",
                    object_repr=f"Account locked: {attempted}",
                    changes={"locked": [False, True]},
                )
            log_action(
                AuditLog.Action.LOGIN_FAILED,
                model_name="accounts.User",
                object_repr=f"Attempted: {attempted}",
                changes={"username": [None, attempted]},
            )
            raise
        user = User.objects.get(pk=response.data["user"]["id"])
        lockout.clear(attempted)
        log_action(AuditLog.Action.LOGIN, user, user=user)
        return response


@extend_schema(tags=AUTH_TAG)
class RefreshView(TokenRefreshView):
    """POST {refresh} → {access, refresh}. The old refresh token is blacklisted (rotation)."""


@extend_schema(
    tags=AUTH_TAG, request=LogoutSerializer, responses={205: OpenApiResponse(description="Logged out")}
)
class LogoutView(generics.GenericAPIView):
    serializer_class = LogoutSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
        except TokenError:
            pass  # already expired/blacklisted — logging out is still fine
        log_action(AuditLog.Action.LOGOUT, request.user, user=request.user)
        return Response(status=status.HTTP_205_RESET_CONTENT)


@extend_schema(tags=AUTH_TAG)
class MeView(generics.RetrieveUpdateAPIView):
    """GET current user · PATCH own name / email / phone."""

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch"]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        return ProfileSerializer if self.request.method == "PATCH" else UserSerializer

    def update(self, request, *args, **kwargs):
        super().update(request, *args, **kwargs)
        return Response(UserSerializer(request.user, context={"request": request}).data)


@extend_schema(tags=AUTH_TAG, request=ChangePasswordSerializer)
class ChangePasswordView(generics.GenericAPIView):
    serializer_class = ChangePasswordSerializer
    """Returns a fresh token pair; other devices are logged out."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        tokens = services.change_own_password(
            user=request.user, new_password=serializer.validated_data["new_password"]
        )
        return Response(
            {
                "detail": "Password changed successfully.",
                **tokens,
                "user": UserSerializer(request.user, context={"request": request}).data,
            }
        )


@extend_schema(tags=AUTH_TAG, request=ForgotPasswordSerializer)
class ForgotPasswordView(generics.GenericAPIView):
    serializer_class = ForgotPasswordSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.send_password_reset_email(serializer.validated_data["email"])
        return Response({"detail": "If this email is registered, a password reset link has been sent."})


@extend_schema(tags=AUTH_TAG, request=ResetPasswordSerializer)
class ResetPasswordView(generics.GenericAPIView):
    serializer_class = ResetPasswordSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.reset_password_with_token(
            user=serializer.validated_data["user"], new_password=serializer.validated_data["new_password"]
        )
        return Response({"detail": "Password has been reset. You can now log in."})


# ---------------------------------------------------------------------------
# Users & roles (Admin)
# ---------------------------------------------------------------------------
class UserFilter(filters.FilterSet):
    role = filters.CharFilter(field_name="role__code")

    class Meta:
        model = User
        fields = ["role", "is_active"]


@extend_schema(tags=["Users"])
class UserViewSet(viewsets.ModelViewSet):
    """User management — Super Admin and Admin only. Delete = soft delete."""

    permission_classes = [RoleBasedPermission]
    allowed_roles = {"default": MANAGEMENT, "lookup": ALL_ROLES}
    filterset_class = UserFilter
    search_fields = ["username", "email", "first_name", "last_name", "phone"]
    ordering_fields = ["username", "first_name", "email", "last_login", "date_joined", "is_active"]
    ordering = ["username"]
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        return User.objects.filter(is_deleted=False).select_related("role")

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        if self.action == "partial_update":
            return UserUpdateSerializer
        return UserSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.create_user(actor=request.user, data=dict(serializer.validated_data))
        return Response(
            UserSerializer(user, context=self.get_serializer_context()).data, status=status.HTTP_201_CREATED
        )

    def partial_update(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = self.get_serializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = services.update_user(actor=request.user, user=user, data=dict(serializer.validated_data))
        return Response(UserSerializer(user, context=self.get_serializer_context()).data)

    def destroy(self, request, *args, **kwargs):
        services.soft_delete_user(actor=request.user, user=self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(responses={200: OpenApiResponse(description="[{id, name, role_code}]")})
    @action(detail=False, methods=["get"])
    def lookup(self, request):
        """Active users for pickers (e.g. assign a site engineer). ?role=SITE_ENGINEER"""
        qs = (
            User.objects.filter(is_active=True, is_deleted=False)
            .select_related("role")
            .order_by("first_name")
        )
        role = request.query_params.get("role")
        if role:
            qs = qs.filter(role__code=role)
        return Response(
            [{"id": u.id, "name": u.get_full_name() or u.username, "role_code": u.role_code} for u in qs]
        )

    @extend_schema(request=None, responses=UserSerializer)
    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        user = services.set_active(actor=request.user, user=self.get_object(), active=True)
        return Response(UserSerializer(user).data)

    @extend_schema(request=None, responses=UserSerializer)
    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        user = services.set_active(actor=request.user, user=self.get_object(), active=False)
        return Response(UserSerializer(user).data)

    @extend_schema(
        request=AdminSetPasswordSerializer, responses={200: OpenApiResponse(description="Password reset")}
    )
    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        user = self.get_object()
        serializer = AdminSetPasswordSerializer(data=request.data, context={"target_user": user})
        serializer.is_valid(raise_exception=True)
        services.admin_reset_password(
            actor=request.user, user=user, new_password=serializer.validated_data["new_password"]
        )
        return Response({"detail": "Temporary password set. The user must change it at next login."})


@extend_schema(tags=["Users"])
class RoleViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [RoleBasedPermission]
    allowed_roles = MANAGEMENT
    pagination_class = None
    filter_backends = []
