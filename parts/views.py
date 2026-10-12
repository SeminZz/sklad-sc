from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse

from warehouse.models import Warehouse

from .models import Brand, CarModel, Category, Part

LIMIT_CHOICES = [500, 1000, 5000, 20000]
DEFAULT_LIMIT = 5000
# По умолчанию показываем то, что физически есть: без проданных и списанных
INACTIVE_STATUSES = [Part.Status.SOLD, Part.Status.WRITTEN_OFF]


@login_required
def stock(request):
    context = {
        'categories': Category.objects.all(),
        'brands': Brand.objects.all(),
        'car_models': list(CarModel.objects.values('id', 'name', 'brand_id').order_by('name')),
        'warehouses': Warehouse.objects.filter(is_active=True),
        'statuses': Part.Status.choices,
        'limits': LIMIT_CHOICES,
        'default_limit': DEFAULT_LIMIT,
        'admin_part_url': reverse('admin:parts_part_change', args=[0]),
    }
    return render(request, 'parts/stock.html', context)


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def find_category_id(value):
    """Номер категории по номеру или названию (регистр не важен). Нет такой — None."""
    if value.isdigit():
        return int(value)
    found = Category.objects.filter(name=value).values_list('id', flat=True).first()
    if found:
        return found
    # SQLite не умеет сравнивать кириллицу без учёта регистра, поэтому сверяем в Python:
    # справочник небольшой (около тысячи строк).
    wanted = value.lower()
    for pk, name in Category.objects.values_list('id', 'name'):
        if name.lower() == wanted:
            return pk
    return None


def filter_parts(params):
    qs = Part.objects.all()

    q = (params.get('q') or '').strip()
    if q:
        cond = (Q(barcode__iexact=q) | Q(oem__icontains=q) | Q(engine_code__icontains=q)
                | Q(description__icontains=q))
        if q.isdigit():
            cond |= Q(pk=int(q))
        qs = qs.filter(cond)

    # Категория приходит названием (поле с подсказками) или номером
    category = ' '.join((params.get('category') or '').split())
    if category:
        qs = qs.filter(category_id=find_category_id(category))

    for param, field in (('brand', 'brand_id'),
                         ('car_model', 'car_model_id'), ('warehouse', 'warehouse_id')):
        value = _int(params.get(param))
        if value:
            qs = qs.filter(**{field: value})

    engine = (params.get('engine') or '').strip()
    if engine:
        qs = qs.filter(Q(engine_code__icontains=engine) | Q(oem__icontains=engine))

    status = params.get('status') or 'active'
    if status == 'active':
        qs = qs.exclude(status__in=INACTIVE_STATUSES)
    elif status != 'all':
        qs = qs.filter(status=status)

    return qs


@login_required
def stock_api(request):
    limit = _int(request.GET.get('limit')) or DEFAULT_LIMIT
    limit = min(max(limit, 1), max(LIMIT_CHOICES))

    qs = filter_parts(request.GET)
    total = qs.count()
    status_labels = dict(Part.Status.choices)
    condition_labels = dict(Part.Condition.choices)

    rows = qs.values(
        'id', 'barcode', 'year', 'engine_code', 'oem', 'condition', 'price', 'min_price', 'status',
        'category__name', 'brand__name', 'car_model__name',
        'warehouse__name', 'warehouse__kind', 'cell__address', 'created_at',
    )[:limit]

    data = [{
        'id': r['id'],
        'barcode': r['barcode'],
        'warehouse': r['warehouse__name'],
        'warehouse_kind': r['warehouse__kind'],
        'cell': r['cell__address'] or '',
        'category': r['category__name'],
        'brand': r['brand__name'] or '',
        'car_model': r['car_model__name'] or '',
        'year': r['year'],
        'engine': r['engine_code'],
        'oem': r['oem'],
        'condition': condition_labels.get(r['condition'], r['condition']),
        'price': float(r['price']) if r['price'] is not None else None,
        'min_price': float(r['min_price']) if r['min_price'] is not None else None,
        'status': r['status'],
        'status_label': status_labels.get(r['status'], r['status']),
        'created': r['created_at'].strftime('%d.%m.%Y') if r['created_at'] else '',
    } for r in rows]

    return JsonResponse({'total': total, 'shown': len(data), 'rows': data})
