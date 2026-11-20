from django.contrib import admin

from .models import Purchase, PurchaseItem, Supplier, SupplierPayment


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "city", "gstin")
    search_fields = ("name", "phone", "gstin")


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 0


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ("po_number", "supplier", "purchase_date", "status", "grand_total", "balance_due")
    list_filter = ("status", "payment_status")
    search_fields = ("po_number", "supplier_invoice_number", "supplier__name")
    inlines = [PurchaseItemInline]


@admin.register(SupplierPayment)
class SupplierPaymentAdmin(admin.ModelAdmin):
    list_display = ("voucher_number", "supplier", "date", "amount", "mode")
