from django.contrib import admin

from .models import (
    AdvanceAdjustment,
    AdvancePayment,
    AdvanceRefund,
    CustomerLedgerEntry,
    Payment,
    PaymentReminder,
)


@admin.register(AdvancePayment)
class AdvancePaymentAdmin(admin.ModelAdmin):
    list_display = (
        "receipt_number",
        "customer",
        "date",
        "amount",
        "adjusted_amount",
        "refunded_amount",
        "status",
    )
    list_filter = ("status", "mode")
    search_fields = ("receipt_number", "customer__name")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("receipt_number", "customer", "invoice", "date", "amount", "mode", "cheque_status")
    list_filter = ("mode", "cheque_status")
    search_fields = ("receipt_number", "customer__name", "reference_number")
    date_hierarchy = "date"


@admin.register(CustomerLedgerEntry)
class CustomerLedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("date", "customer", "entry_type", "reference_number", "debit", "credit")
    list_filter = ("entry_type",)
    search_fields = ("customer__name", "reference_number")


admin.site.register(AdvanceAdjustment)
admin.site.register(AdvanceRefund)
admin.site.register(PaymentReminder)
