from django.contrib import admin

from .models import Invoice, InvoiceItem


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "customer",
        "invoice_date",
        "grand_total",
        "advance_adjusted",
        "amount_paid",
        "balance_due",
        "status",
    )
    list_filter = ("status",)
    search_fields = ("number", "customer__name", "customer__phone")
    date_hierarchy = "invoice_date"
    inlines = [InvoiceItemInline]
