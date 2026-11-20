from django.contrib import admin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "city", "customer_type", "gstin", "is_deleted")
    list_filter = ("customer_type", "city", "is_deleted")
    search_fields = ("name", "phone", "alternate_phone", "email", "gstin")

    def get_queryset(self, request):
        return Customer.all_objects.all()
