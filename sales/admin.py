from django.contrib import admin

from .models import Cart, CartItem, Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'kind', 'phone', 'email', 'city', 'discount', 'manager', 'created_at')
    list_filter = ('kind', 'manager')
    search_fields = ('search_text', 'phone_digits')
    fieldsets = (
        (None, {'fields': ('kind', 'last_name', 'first_name', 'middle_name', 'company_name', 'inn')}),
        ('Контакты', {'fields': ('phone', 'email', 'gender')}),
        ('Адрес', {'fields': ('country', 'region', 'city', 'street', 'house', 'flat', 'postcode')}),
        ('Прочее', {'fields': ('vin', 'manager', 'discount', 'created_by', 'created_at')}),
    )
    readonly_fields = ('created_by', 'created_at')


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    raw_id_fields = ('part',)
    readonly_fields = ('added_at',)


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'owner', 'is_open', 'created_at')
    list_filter = ('is_open', 'owner')
    inlines = [CartItemInline]
    raw_id_fields = ('customer',)
