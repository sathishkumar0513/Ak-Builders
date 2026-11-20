from django.contrib import admin

from .models import AuditLog, CompanySettings, DocumentSequence, TermsTemplate


@admin.register(CompanySettings)
class CompanySettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not CompanySettings.objects.exists()


@admin.register(DocumentSequence)
class DocumentSequenceAdmin(admin.ModelAdmin):
    list_display = ("doc_type", "financial_year", "prefix", "next_number", "padding")


@admin.register(TermsTemplate)
class TermsTemplateAdmin(admin.ModelAdmin):
    list_display = ("title", "applies_to", "is_default")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "user", "action", "model_name", "object_id", "object_repr")
    list_filter = ("action", "model_name")
    search_fields = ("object_repr", "object_id", "user__username")
    date_hierarchy = "timestamp"

    def has_change_permission(self, request, obj=None):
        return False  # audit log is read-only

    def has_delete_permission(self, request, obj=None):
        return False
