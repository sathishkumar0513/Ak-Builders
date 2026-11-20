from django.conf import settings
from django.db import models

from apps.core.fields import MoneyField, PercentField, QuantityField
from apps.core.models import BaseModel, TimeStampedModel
from apps.core.uploads import _random_name


class Project(BaseModel):
    class Status(models.TextChoices):
        PLANNED = "PLANNED", "Planned"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        ON_HOLD = "ON_HOLD", "On Hold"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    class ProjectType(models.TextChoices):
        NEW_CONSTRUCTION = "NEW", "New construction"
        RENOVATION = "RENOVATION", "Renovation"
        MATERIAL_SUPPLY = "SUPPLY", "Material supply only"

    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=200, db_index=True)
    project_type = models.CharField(
        max_length=12, choices=ProjectType.choices, default=ProjectType.RENOVATION
    )
    customer = models.ForeignKey("customers.Customer", on_delete=models.PROTECT, related_name="projects")
    quotation = models.ForeignKey(
        "quotations.Quotation", null=True, blank=True, on_delete=models.SET_NULL, related_name="projects"
    )
    site_address = models.TextField()
    site_city = models.CharField(max_length=100, blank=True)
    site_pincode = models.CharField(max_length=6, blank=True)
    start_date = models.DateField(null=True, blank=True, db_index=True)
    expected_end_date = models.DateField(null=True, blank=True)
    actual_end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PLANNED, db_index=True)
    assigned_engineer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_projects",
    )
    contract_value = MoneyField(help_text="Agreed value (usually the approved quotation grand total)")
    progress_percent = PercentField()
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} – {self.name}"


class PaymentStage(TimeStampedModel):
    """Milestone schedule, e.g. 30% advance / 40% on slab / 30% on handover."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        DUE = "DUE", "Due"
        PARTIAL = "PARTIAL", "Partially paid"
        PAID = "PAID", "Paid"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="payment_stages")
    name = models.CharField(max_length=150)
    percentage = PercentField()
    amount = MoneyField()
    due_date = models.DateField(null=True, blank=True, db_index=True)
    amount_received = MoneyField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["project", "sort_order", "id"]

    def __str__(self):
        return f"{self.project.code}: {self.name}"


class ProjectMaterialIssue(BaseModel):
    """Material sent to a site. Creating one decreases stock via a SITE_ISSUE StockMovement."""

    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="material_issues")
    material = models.ForeignKey("materials.Material", on_delete=models.PROTECT, related_name="site_issues")
    issue_date = models.DateField(db_index=True)
    quantity = QuantityField()
    rate = MoneyField(help_text="Cost rate at time of issue (purchase price) for project costing")
    amount = MoneyField()
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    is_return = models.BooleanField(default=False, help_text="True = material returned from site to store")
    received_by_name = models.CharField(max_length=100, blank=True)
    vehicle_number = models.CharField(max_length=20, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-issue_date", "-id"]
        constraints = [models.CheckConstraint(condition=models.Q(quantity__gt=0), name="issue_qty_positive")]


class ProgressNote(BaseModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="progress_notes")
    date = models.DateField(db_index=True)
    note = models.TextField()
    progress_percent = PercentField(null=True, blank=True)
    workers_on_site = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-date", "-id"]


def progress_photo_path(instance, filename):
    return f"projects/{instance.note.project_id}/{instance.note.date:%Y/%m}/{_random_name(filename)}"


class ProgressPhoto(TimeStampedModel):
    note = models.ForeignKey(ProgressNote, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to=progress_photo_path)
    caption = models.CharField(max_length=200, blank=True)
