from django.contrib import admin

from .models import Cell, Warehouse

admin.site.site_header = 'Учёт склада и СЦ'
admin.site.site_title = 'Учёт склада и СЦ'
admin.site.index_title = 'Управление'


class CellInline(admin.TabularInline):
    model = Cell
    extra = 1
    fields = ('floor', 'zone', 'rack', 'shelf', 'position', 'address', 'cell_type',
              'capacity', 'max_weight_kg', 'is_active', 'barcode')
    readonly_fields = ('barcode',)
    show_change_link = True


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'kind', 'city', 'cells_count', 'is_active')
    list_filter = ('kind', 'is_active', 'city')
    search_fields = ('name', 'code', 'city', 'address')
    fieldsets = (
        (None, {'fields': ('name', 'code', 'kind', 'is_active')}),
        ('Расположение', {'fields': ('city', 'address')}),
        ('Прочее', {'fields': ('notes', 'created_at', 'updated_at')}),
    )
    readonly_fields = ('created_at', 'updated_at')
    inlines = [CellInline]

    @admin.display(description='ячеек')
    def cells_count(self, obj):
        return obj.cells.count()


@admin.register(Cell)
class CellAdmin(admin.ModelAdmin):
    list_display = ('address', 'warehouse', 'cell_type', 'capacity', 'max_weight_kg', 'barcode', 'is_active')
    list_filter = ('warehouse', 'cell_type', 'is_active', 'floor', 'zone')
    search_fields = ('address', 'barcode', 'rack', 'notes', 'warehouse__code')
    list_select_related = ('warehouse',)
    list_per_page = 100
    fieldsets = (
        (None, {'fields': ('warehouse', 'cell_type', 'is_active')}),
        ('Адрес', {'fields': ('floor', 'zone', 'rack', 'shelf', 'position', 'address', 'barcode')}),
        ('Вместимость', {'fields': ('capacity', 'max_weight_kg')}),
        ('Прочее', {'fields': ('notes', 'created_at', 'updated_at')}),
    )
    readonly_fields = ('barcode', 'created_at', 'updated_at')
