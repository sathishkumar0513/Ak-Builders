from django.contrib import admin

from .models import Material, MaterialCategory, PriceHistory, StockMovement


@admin.register(MaterialCategory)
class MaterialCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)


class PriceHistoryInline(admin.TabularInline):
    model = PriceHistory
    extra = 0
    readonly_fields = [f.name for f in PriceHistory._meta.fields]
    can_delete = False


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "brand",
        "category",
        "unit",
        "selling_price",
        "gst_rate",
        "stock_quantity",
        "reorder_level",
    )
    list_filter = ("category", "unit", "gst_rate", "is_active")
    search_fields = ("name", "brand", "hsn_code", "sku")
    readonly_fields = ("stock_quantity",)
    inlines = [PriceHistoryInline]


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "material",
        "movement_type",
        "quantity",
        "balance_after",
        "project",
        "reference_type",
    )
    list_filter = ("movement_type", "date")
    search_fields = ("material__name", "note")
    date_hierarchy = "date"
