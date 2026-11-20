from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models

from apps.core.models import TimeStampedModel
from apps.core.uploads import avatar_path


class Role(TimeStampedModel):
    """The five business roles. RBAC permission classes (Phase 2) check `code`."""

    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    ACCOUNTANT = "ACCOUNTANT"
    SITE_ENGINEER = "SITE_ENGINEER"
    SALES = "SALES"

    CODE_CHOICES = [
        (SUPER_ADMIN, "Super Admin"),
        (ADMIN, "Admin"),
        (ACCOUNTANT, "Accountant"),
        (SITE_ENGINEER, "Site Engineer"),
        (SALES, "Sales / Staff"),
    ]

    code = models.CharField(max_length=30, unique=True, choices=CODE_CHOICES)
    name = models.CharField(max_length=60)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class User(AbstractUser):
    """Custom user. Login by username or email (Phase 2). last_login is tracked by Django + SimpleJWT."""

    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, blank=True, db_index=True)
    role = models.ForeignKey(Role, on_delete=models.PROTECT, null=True, blank=True, related_name="users")
    avatar = models.ImageField(upload_to=avatar_path, blank=True, null=True)
    must_change_password = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    REQUIRED_FIELDS = ["email"]

    class Meta:
        ordering = ["username"]

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def role_code(self):
        if self.is_superuser and not self.role_id:
            return Role.SUPER_ADMIN
        return self.role.code if self.role_id else None

    def has_role(self, *codes):
        return self.role_code in codes
