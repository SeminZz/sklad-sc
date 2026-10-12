from django.contrib import admin

from .models import Brand, CarModel, Category, Part


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ('name',)


class CarModelInline(admin.TabularInline):
    model = CarModel
    extra = 1


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    search_fields = ('name',)
    inlines = [CarModelInline]


@admin.register(CarModel)
class CarModelAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand')
    list_filter = ('brand',)
    search_fields = ('name', 'brand__name')


@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ('barcode', 'category', 'brand', 'car_model', 'year', 'engine_code', 'warehouse', 'cell',
                    'status', 'price')
    list_filter = ('status', 'warehouse', 'category', 'condition')
    search_fields = ('barcode', 'oem', 'engine_code', 'car_model__name', 'brand__name')
    list_select_related = ('category', 'brand', 'car_model', 'warehouse', 'cell')
    autocomplete_fields = ('category', 'brand', 'car_model', 'cell')
    list_per_page = 100
    fieldsets = (
        (None, {'fields': ('barcode', 'status', 'category')}),
        ('Автомобиль', {'fields': ('brand', 'car_model', 'year', 'engine_code', 'oem')}),
        ('Состояние', {'fields': ('condition', 'defects', 'description')}),
        ('Цена', {'fields': ('price', 'min_price')}),
        ('Хранение', {'fields': ('warehouse', 'cell')}),
        ('Служебное', {'fields': ('created_by', 'created_at', 'updated_at')}),
    )
    readonly_fields = ('barcode', 'created_by', 'created_at', 'updated_at')

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return False
