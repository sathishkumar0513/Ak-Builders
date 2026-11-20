from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Role, User


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "description")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "first_name", "role", "is_active", "last_login")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("username", "email", "first_name", "last_name", "phone")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("AK Builders", {"fields": ("phone", "role", "avatar", "must_change_password")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (("AK Builders", {"fields": ("email", "phone", "role")}),)
