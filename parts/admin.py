from django import forms
from django.contrib import admin
from django.urls import reverse

from .models import Brand, CarModel, Category, Part
from .views import brand_groups


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ('name',)


class CarModelInline(admin.TabularInline):
    model = CarModel
    extra = 1


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'name_ru', 'country', 'is_popular', 'models_count')
    list_filter = ('is_popular', 'country')
    search_fields = ('name', 'name_ru')
    inlines = [CarModelInline]

    @admin.display(description='моделей')
    def models_count(self, obj):
        return obj.models.count()


@admin.register(CarModel)
class CarModelAdmin(admin.ModelAdmin):
    list_display = ('name', 'name_ru', 'brand', 'year_from', 'year_to')
    list_filter = ('brand__is_popular',)
    search_fields = ('name', 'name_ru', 'brand__name', 'brand__name_ru')
    list_select_related = ('brand',)


class PartAdminForm(forms.ModelForm):
    """Модель можно выбрать только после марки, и в списке только модели этой марки."""

    class Meta:
        model = Part
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        brand_field = self.fields['brand']
        brand_field.choices = [('', '---------')] + brand_groups()

        brand_id = self.data.get(self.add_prefix('brand')) if self.is_bound else self.instance.brand_id
        brand_id = int(brand_id) if str(brand_id or '').isdigit() else None
        model_field = self.fields['car_model']
        model_field.queryset = CarModel.objects.filter(brand_id=brand_id).order_by('name')
        # В админке виджет обёрнут (кнопки «добавить/изменить»), атрибут ставим самому списку
        select = getattr(model_field.widget, 'widget', model_field.widget)
        select.attrs['data-models-url'] = reverse('models_api')
        model_field.help_text = 'Сначала выберите марку: в списке только её модели.'


@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    form = PartAdminForm
    list_display = ('barcode', 'category', 'brand', 'car_model', 'generation', 'year', 'engine_code', 'warehouse', 'cell',
                    'status', 'price')
    list_filter = ('status', 'warehouse', 'category', 'condition')
    search_fields = ('barcode', 'oem', 'engine_code', 'car_model__name', 'brand__name')
    list_select_related = ('category', 'brand', 'car_model', 'warehouse', 'cell')
    autocomplete_fields = ('category', 'cell')
    list_per_page = 100
    fieldsets = (
        (None, {'fields': ('barcode', 'status', 'category')}),
        ('Автомобиль', {'fields': ('brand', 'car_model', 'generation', 'year', 'engine_code', 'oem')}),
        ('Состояние', {'fields': ('condition', 'defects', 'description')}),
        ('Цена', {'fields': ('price', 'min_price')}),
        ('Хранение', {'fields': ('warehouse', 'cell')}),
        ('Служебное', {'fields': ('created_by', 'created_at', 'updated_at')}),
    )
    readonly_fields = ('barcode', 'created_by', 'created_at', 'updated_at')

    class Media:
        js = ('js/brand_model.js', 'js/admin_part.js')

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return False
