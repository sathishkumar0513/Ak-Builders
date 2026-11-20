"""
Shared building blocks for every table:
- TimeStampedModel: created_at / updated_at / created_by / updated_by
- SoftDeleteModel: is_deleted flag with a manager that hides deleted rows
- BaseModel: both of the above (use this for business tables)

Also holds company-wide tables: CompanySettings, DocumentSequence, TermsTemplate, AuditLog.
"""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from .fields import MoneyField
from .middleware import get_current_user
from .uploads import logo_path


# ---------------------------------------------------------------------------
# Choices shared across apps
# ---------------------------------------------------------------------------
class PaymentMode(models.TextChoices):
    CASH = "CASH", "Cash"
    UPI = "UPI", "UPI"
    BANK_TRANSFER = "BANK", "Bank Transfer"
    CHEQUE = "CHEQUE", "Cheque"
    CARD = "CARD", "Card"


class Unit(models.TextChoices):
    BAG = "bag", "Bag"
    KG = "kg", "Kg"
    TON = "ton", "Ton"
    PIECE = "piece", "Piece"
    SQFT = "sqft", "Sq.ft"
    CFT = "cft", "Cu.ft"
    LOAD = "load", "Load"
    METER = "meter", "Meter"
    LITRE = "litre", "Litre"
    BOX = "box", "Box"
    NOS = "nos", "Nos"
    LUMPSUM = "ls", "Lump sum"
    DAY = "day", "Day"


# ---------------------------------------------------------------------------
# Abstract base models
# ---------------------------------------------------------------------------
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        editable=False,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        editable=False,
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        user = get_current_user()
        if user is not None:
            if self._state.adding and not self.created_by_id:
                self.created_by = user
            self.updated_by = user
        super().save(*args, **kwargs)


class ActiveManager(models.Manager):
    """Default manager: hides soft-deleted rows."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class SoftDeleteModel(models.Model):
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True, editable=False)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        editable=False,
    )

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def soft_delete(self, user=None):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = user or get_current_user()
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "updated_at"])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "updated_at"])


class BaseModel(TimeStampedModel, SoftDeleteModel):
    class Meta:
        abstract = True


# ---------------------------------------------------------------------------
# Company settings (single row)
# ---------------------------------------------------------------------------
class CompanySettings(TimeStampedModel):
    name = models.CharField(max_length=200, default="AK Builders")
    tagline = models.CharField(max_length=200, blank=True)
    logo = models.ImageField(upload_to=logo_path, blank=True, null=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, default="Tamil Nadu")
    state_code = models.CharField(max_length=2, default="33")
    pincode = models.CharField(max_length=10, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    gstin = models.CharField(max_length=15, blank=True)
    pan = models.CharField(max_length=10, blank=True)

    bank_name = models.CharField(max_length=100, blank=True)
    bank_account_name = models.CharField(max_length=150, blank=True)
    bank_account_number = models.CharField(max_length=30, blank=True)
    bank_ifsc = models.CharField(max_length=11, blank=True)
    bank_branch = models.CharField(max_length=100, blank=True)
    upi_id = models.CharField(max_length=100, blank=True)

    default_gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("18.00"))
    quotation_validity_days = models.PositiveIntegerField(default=15)
    invoice_due_days = models.PositiveIntegerField(default=7)
    financial_year_start_month = models.PositiveSmallIntegerField(default=4)  # April

    # Notification hooks (SMS / WhatsApp / email providers wired in later phases)
    notify_email_enabled = models.BooleanField(default=False)
    notify_sms_enabled = models.BooleanField(default=False)
    notify_whatsapp_enabled = models.BooleanField(default=False)
    whatsapp_api_url = models.URLField(blank=True)
    sms_sender_id = models.CharField(max_length=20, blank=True)

    class Meta:
        verbose_name = "Company settings"
        verbose_name_plural = "Company settings"

    def __str__(self):
        return self.name

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1  # singleton
        super().save(*args, **kwargs)


class DocumentSequence(models.Model):
    """
    Number series per document type and financial year, e.g. AK/2026-27/0001.
    Incremented with SELECT ... FOR UPDATE inside transaction.atomic()
    (see apps.core.numbering.next_document_number).
    """

    class DocType(models.TextChoices):
        QUOTATION = "QUOTATION", "Quotation"
        INVOICE = "INVOICE", "Invoice"
        ADVANCE_RECEIPT = "ADVANCE", "Advance receipt"
        PAYMENT_RECEIPT = "RECEIPT", "Payment receipt"
        PURCHASE_ORDER = "PO", "Purchase order"
        PROJECT = "PROJECT", "Project"
        EXPENSE = "EXPENSE", "Expense voucher"
        REFUND = "REFUND", "Advance refund"
        SUPPLIER_PAYMENT = "SUPPAY", "Supplier payment"

    doc_type = models.CharField(max_length=20, choices=DocType.choices)
    financial_year = models.CharField(max_length=7)  # "2026-27"
    prefix = models.CharField(max_length=20)  # "AK/INV"
    padding = models.PositiveSmallIntegerField(default=4)
    next_number = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["doc_type", "financial_year"], name="uniq_sequence_per_fy")
        ]

    def __str__(self):
        return f"{self.get_doc_type_display()} {self.financial_year} → {self.next_number}"


class TermsTemplate(BaseModel):
    class AppliesTo(models.TextChoices):
        QUOTATION = "QUOTATION", "Quotation"
        INVOICE = "INVOICE", "Invoice"
        RECEIPT = "RECEIPT", "Receipt"

    title = models.CharField(max_length=150)
    applies_to = models.CharField(max_length=20, choices=AppliesTo.choices)
    content = models.TextField()
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.title


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------
class AuditLog(models.Model):
    class Action(models.TextChoices):
        CREATE = "CREATE", "Created"
        UPDATE = "UPDATE", "Updated"
        DELETE = "DELETE", "Deleted"
        RESTORE = "RESTORE", "Restored"
        LOGIN = "LOGIN", "Logged in"
        LOGIN_FAILED = "LOGIN_FAIL", "Login failed"
        LOGOUT = "LOGOUT", "Logged out"
        PASSWORD = "PASSWORD", "Password changed/reset"
        STATUS = "STATUS", "Status changed"
        EXPORT = "EXPORT", "Exported"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_logs"
    )
    action = models.CharField(max_length=10, choices=Action.choices, db_index=True)
    model_name = models.CharField(max_length=100, db_index=True)  # "quotations.Quotation"
    object_id = models.CharField(max_length=64, blank=True, db_index=True)
    object_repr = models.CharField(max_length=255, blank=True)
    changes = models.JSONField(default=dict, blank=True)  # {"field": [old, new]}
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [models.Index(fields=["model_name", "object_id"])]

    def __str__(self):
        return f"{self.timestamp:%d/%m/%Y %H:%M} {self.user} {self.action} {self.model_name}#{self.object_id}"


__all__ = [
    "MoneyField",
    "PaymentMode",
    "Unit",
    "TimeStampedModel",
    "SoftDeleteModel",
    "BaseModel",
    "CompanySettings",
    "DocumentSequence",
    "TermsTemplate",
    "AuditLog",
]
