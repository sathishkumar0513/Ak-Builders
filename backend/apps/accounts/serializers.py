from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth import password_validation
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Role, User


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "code", "name", "description"]


class UserSerializer(serializers.ModelSerializer):
    """Read representation used everywhere (login response, /me, user list)."""

    full_name = serializers.SerializerMethodField()
    role_code = serializers.CharField(read_only=True)
    role_name = serializers.CharField(source="role.name", read_only=True, default=None)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "role",
            "role_code",
            "role_name",
            "is_active",
            "must_change_password",
            "last_login",
            "date_joined",
            "avatar",
        ]
        read_only_fields = fields

    def get_full_name(self, obj) -> str:
        return obj.get_full_name() or obj.username


class _UserWriteBase(serializers.ModelSerializer):
    role = serializers.PrimaryKeyRelatedField(queryset=Role.objects.all())
    phone = serializers.RegexField(
        r"^[6-9]\d{9}$",
        required=False,
        allow_blank=True,
        error_messages={"invalid": "Enter a valid 10-digit mobile number."},
    )

    def validate_email(self, value):
        value = value.strip().lower()
        qs = User.objects.filter(email__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_username(self, value):
        value = value.strip()
        qs = User.objects.filter(username__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("This username is already taken.")
        return value

    def validate_role(self, role):
        actor = self.context["request"].user
        if role.code == Role.SUPER_ADMIN and actor.role_code != Role.SUPER_ADMIN:
            raise serializers.ValidationError("Only a Super Admin can assign the Super Admin role.")
        return role


class UserCreateSerializer(_UserWriteBase):
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name", "phone", "role", "is_active", "password"]

    def validate(self, attrs):
        candidate = User(
            username=attrs.get("username"), email=attrs.get("email"), first_name=attrs.get("first_name", "")
        )
        password_validation.validate_password(attrs["password"], candidate)
        return attrs


class UserUpdateSerializer(_UserWriteBase):
    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name", "phone", "role", "is_active"]
        extra_kwargs = {f: {"required": False} for f in fields}


class ProfileSerializer(serializers.ModelSerializer):
    """What a user may change about themselves (not role, not active flag)."""

    phone = serializers.RegexField(
        r"^[6-9]\d{9}$",
        required=False,
        allow_blank=True,
        error_messages={"invalid": "Enter a valid 10-digit mobile number."},
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone"]

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value


class LoginSerializer(TokenObtainPairSerializer):
    """username may be the username or the email address."""

    default_error_messages = {"no_active_account": "Invalid username/email or password."}

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role_code
        token["name"] = user.get_full_name() or user.username
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user, context=self.context).data
        return data


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        if attrs["new_password"] == attrs["old_password"]:
            raise serializers.ValidationError({"new_password": "New password must be different."})
        try:
            password_validation.validate_password(attrs["new_password"], self.context["request"].user)
        except DjangoValidationError as exc:
            # attach to the field so the form shows it under "New password"
            raise serializers.ValidationError({"new_password": list(exc.messages)})
        return attrs


class AdminSetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        password_validation.validate_password(value, self.context.get("target_user"))
        return value


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        invalid = serializers.ValidationError({"token": "This reset link is invalid or has expired."})
        try:
            pk = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=pk, is_deleted=False, is_active=True)
        except (ValueError, TypeError, OverflowError, User.DoesNotExist):
            raise invalid
        if not default_token_generator.check_token(user, attrs["token"]):
            raise invalid
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        try:
            password_validation.validate_password(attrs["new_password"], user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)})
        attrs["user"] = user
        return attrs
