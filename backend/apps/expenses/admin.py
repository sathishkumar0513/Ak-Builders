from django.contrib import admin

from .models import Expense


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("voucher_number", "date", "category", "project", "amount", "paid_to", "mode")
    list_filter = ("category", "mode")
    search_fields = ("voucher_number", "paid_to", "description")
    date_hierarchy = "date"
