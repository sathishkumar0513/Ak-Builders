from django.contrib import admin

from .models import Quotation, QuotationItem


class QuotationItemInline(admin.TabularInline):
    model = QuotationItem
    extra = 0


@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ("number", "revision", "customer", "quotation_date", "status", "grand_total", "is_latest")
    list_filter = ("status", "is_latest")
    search_fields = ("number", "customer__name", "customer__phone", "title")
    inlines = [QuotationItemInline]
