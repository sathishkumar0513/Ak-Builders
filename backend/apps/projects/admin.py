from django.contrib import admin

from .models import PaymentStage, ProgressNote, ProgressPhoto, Project, ProjectMaterialIssue


class PaymentStageInline(admin.TabularInline):
    model = PaymentStage
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "customer", "status", "assigned_engineer", "contract_value", "start_date")
    list_filter = ("status", "project_type")
    search_fields = ("code", "name", "customer__name")
    inlines = [PaymentStageInline]


@admin.register(ProjectMaterialIssue)
class ProjectMaterialIssueAdmin(admin.ModelAdmin):
    list_display = ("issue_date", "project", "material", "quantity", "amount")


class ProgressPhotoInline(admin.TabularInline):
    model = ProgressPhoto
    extra = 0


@admin.register(ProgressNote)
class ProgressNoteAdmin(admin.ModelAdmin):
    list_display = ("date", "project", "progress_percent")
    inlines = [ProgressPhotoInline]
