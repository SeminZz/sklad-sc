import json
import re
from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.timezone import localtime
from django.views.decorators.http import require_GET, require_POST

from parts.models import Part

from .models import Cart, CartItem, Customer, phone_digits

CLOSED_PART_STATUSES = {Part.Status.SOLD, Part.Status.WRITTEN_OFF}


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['kind', 'last_name', 'first_name', 'middle_name', 'company_name', 'inn', 'phone', 'email',
                  'gender', 'country', 'region', 'city', 'street', 'house', 'flat', 'postcode', 'vin',
                  'manager', 'discount']


def _json_body(request):
    try:
        return json.loads(request.body or b'{}')
    except ValueError:
        return {}


def customer_json(c):
    return {
        'id': c.pk,
        'name': c.display_name,
        'kind': c.get_kind_display(),
        'phone': c.phone,
        'email': c.email,
        'address': c.address,
        'created': localtime(c.created_at).strftime('%d.%m.%Y') if c.created_at else '',
        'discount': float(c.discount),
        'manager': (c.manager.get_full_name() or c.manager.username) if c.manager else '',
    }


def cart_json(cart):
    items = list(cart.items.select_related('part__category', 'part__brand', 'part__car_model',
                                           'part__warehouse', 'part__cell'))
    total = sum((i.price or Decimal(0)) for i in items)
    discount = cart.customer.discount or Decimal(0)
    return {
        'id': cart.pk,
        'customer': customer_json(cart.customer),
        'items': [{
            'id': i.pk,
            'part_id': i.part_id,
            'barcode': i.part.barcode,
            'category': i.part.category.name,
            'brand': i.part.brand.name if i.part.brand else '',
            'car_model': i.part.car_model.name if i.part.car_model else '',
            'generation': i.part.generation,
            'year': i.part.year,
            'warehouse': i.part.warehouse.name,
            'cell': i.part.cell.address if i.part.cell else '',
            'price': float(i.price) if i.price is not None else None,
        } for i in items],
        'total': float(total),
        'total_with_discount': float((total * (100 - discount) / 100).quantize(Decimal('0.01'))),
    }


# ---------- Покупатели ----------

def search_customers(q):
    qs = Customer.objects.select_related('manager')
    q = ' '.join((q or '').split())
    if not q:
        return qs.none()
    digits = re.sub(r'\D', '', q)
    # Телефон можно вводить как угодно: +7 978 123-45-67, 8978..., 9781234567, 123-45
    if len(digits) >= 4 and re.fullmatch(r'[\d\s()+\-.]+', q):
        variants = {digits, phone_digits(digits)}
        cond = Q()
        for v in variants:
            cond |= Q(phone_digits__contains=v)
        return qs.filter(cond)
    for token in q.lower().split():
        qs = qs.filter(search_text__contains=token)
    return qs


@login_required
@require_GET
def customers_search(request):
    found = search_customers(request.GET.get('q'))[:50]
    return JsonResponse({'customers': [customer_json(c) for c in found]})


@login_required
@require_GET
def customer_form_options(request):
    User = get_user_model()
    managers = User.objects.filter(is_active=True).order_by('last_name', 'username')
    return JsonResponse({
        'kinds': Customer.Kind.choices,
        'genders': Customer.Gender.choices,
        'managers': [(u.pk, u.get_full_name() or u.username) for u in managers],
        'current_user': request.user.pk,
    })


@login_required
@require_POST
def customer_create(request):
    data = _json_body(request)
    form = CustomerForm(data)
    if not form.is_valid():
        return JsonResponse({'errors': {k: [str(e) for e in v] for k, v in form.errors.items()}}, status=400)
    customer = form.save(commit=False)
    customer.created_by = request.user
    if not customer.manager_id:
        customer.manager = request.user
    customer.save()
    return JsonResponse({'customer': customer_json(customer)}, status=201)


# ---------- Корзины ----------

def _my_open_carts(user):
    return Cart.objects.filter(owner=user, is_open=True).select_related('customer__manager')


@login_required
@require_GET
def carts_list(request):
    return JsonResponse({'carts': [cart_json(c) for c in _my_open_carts(request.user)]})


@login_required
@require_POST
def cart_add(request):
    data = _json_body(request)
    part = get_object_or_404(Part, pk=data.get('part_id'))
    if part.status in CLOSED_PART_STATUSES:
        return JsonResponse({'error': f'Деталь {part.barcode} в статусе «{part.get_status_display()}», '
                                      f'её нельзя добавить в корзину.'}, status=400)

    with transaction.atomic():
        if data.get('cart_id'):
            cart = get_object_or_404(_my_open_carts(request.user), pk=data['cart_id'])
        else:
            customer = get_object_or_404(Customer, pk=data.get('customer_id'))
            cart = _my_open_carts(request.user).filter(customer=customer).first()
            if cart is None:
                cart = Cart.objects.create(customer=customer, owner=request.user)
        item, created = CartItem.objects.get_or_create(cart=cart, part=part, defaults={'price': part.price})

    others = (CartItem.objects.filter(part=part, cart__is_open=True).exclude(cart=cart)
              .select_related('cart__customer', 'cart__owner'))
    warning = ''
    if others:
        who = ', '.join(f'{o.cart.customer} (менеджер {o.cart.owner.get_full_name() or o.cart.owner.username})'
                        for o in others)
        warning = f'Эта деталь уже лежит в другой корзине: {who}.'
    return JsonResponse({'cart': cart_json(cart), 'added': created, 'warning': warning})


@login_required
@require_POST
def cart_remove_item(request, cart_id):
    cart = get_object_or_404(_my_open_carts(request.user), pk=cart_id)
    cart.items.filter(pk=_json_body(request).get('item_id')).delete()
    return JsonResponse({'cart': cart_json(cart)})


@login_required
@require_POST
def cart_clear(request, cart_id):
    cart = get_object_or_404(_my_open_carts(request.user), pk=cart_id)
    cart.items.all().delete()
    return JsonResponse({'cart': cart_json(cart)})


@login_required
@require_POST
def cart_close(request, cart_id):
    """Закрыть вкладку корзины. Позиции освобождаются, сама корзина остаётся в истории."""
    cart = get_object_or_404(_my_open_carts(request.user), pk=cart_id)
    cart.items.all().delete()
    cart.is_open = False
    cart.save(update_fields=['is_open', 'updated_at'])
    return JsonResponse({'closed': cart.pk})
