"""Тестовые данные для разработки: склады, ячейки, справочники и детали.

Запуск:  python manage.py seed_demo            (2000 деталей)
         python manage.py seed_demo --parts 20000

Все данные выдуманные. На рабочей базе не запускать.
"""
import random
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from parts.models import Brand, CarModel, Category, Part
from warehouse.models import Cell, Warehouse

CATEGORIES = ['Генератор', 'Стартер', 'Компрессор кондиционера', 'ТНВД', 'Турбина', 'Рулевая рейка',
              'Насос ГУР', 'Блок ABS', 'Форсунка', 'Дроссельная заслонка', 'Коробка передач', 'Фара']

CARS = {
    'Ford': ['Focus 2', 'Focus 3', 'Fiesta 5', 'Mondeo 4', 'Kuga'],
    'Opel': ['Astra H', 'Vectra C', 'Zafira A', 'Zafira B', 'Insignia'],
    'Volkswagen': ['Golf 3', 'Golf 5', 'Passat B6', 'Polo', 'Touran'],
    'Toyota': ['Corolla E150', 'Camry XV40', 'RAV4', 'Avensis'],
    'Renault': ['Scenic 2', 'Megane 2', 'Logan', 'Duster'],
    'Mazda': ['Mazda 6 GG', 'Mazda 3 BK', 'Millenia', 'CX-7'],
    'Hyundai': ['Sonata 5', 'Solaris', 'Tucson', 'Santa Fe'],
    'Honda': ['Accord 5', 'Accord 7', 'Civic', 'CR-V'],
    'Mitsubishi': ['Colt 6', 'Lancer 9', 'Outlander', 'Pajero 4'],
    'BMW': ['3 E90', '5 E60', 'X5 E70'],
}
ENGINES = ['N30', 'Z16XEP', 'Z18XER', 'Y22DTR', 'A16XER', 'CFNA', 'BSE', 'BKD', '1ZZ-FE', '2AZ-FE',
           'K4M', 'F4R', 'LF-17', 'G4FC', 'N47D20', 'M54B25', '4G15', '4B12', 'D4EA', 'QQDB']

WAREHOUSES = [
    ('Склад-1 Хранение', 'SKL1', Warehouse.Kind.WAREHOUSE),
    ('Склад-2 Хранение', 'SKL2', Warehouse.Kind.WAREHOUSE),
    ('СЦ Приёмка', 'SC1', Warehouse.Kind.SC),
    ('Транзит', 'TRN', Warehouse.Kind.TRANSIT),
]

STATUS_WEIGHTS = [
    (Part.Status.PLACED, 70), (Part.Status.RESERVED, 6), (Part.Status.READY, 5), (Part.Status.PHOTO, 4),
    (Part.Status.WASHING, 3), (Part.Status.ACCEPTED, 3), (Part.Status.SOLD, 7), (Part.Status.WRITTEN_OFF, 2),
]


class Command(BaseCommand):
    help = 'Создать тестовые данные (склады, ячейки, справочники, детали)'

    def add_arguments(self, parser):
        parser.add_argument('--parts', type=int, default=2000, help='сколько деталей создать')
        parser.add_argument('--seed', type=int, default=42)

    @transaction.atomic
    def handle(self, *args, **opts):
        rnd = random.Random(opts['seed'])

        warehouses = []
        for name, code, kind in WAREHOUSES:
            wh, _ = Warehouse.objects.get_or_create(code=code, defaults={'name': name, 'kind': kind})
            warehouses.append(wh)

        cells = {}
        for wh in warehouses:
            if not wh.cells.exists():
                for zone in 'ABC':
                    for rack in range(1, 13):
                        for shelf in range(1, 5):
                            Cell.objects.create(warehouse=wh, floor=1, zone=zone, rack=str(rack), shelf=str(shelf))
            cells[wh.pk] = list(wh.cells.all())

        categories = [Category.objects.get_or_create(name=n)[0] for n in CATEGORIES]
        models = []
        for brand_name, model_names in CARS.items():
            brand, _ = Brand.objects.get_or_create(name=brand_name)
            for m in model_names:
                models.append(CarModel.objects.get_or_create(brand=brand, name=m)[0])

        statuses = [s for s, _ in STATUS_WEIGHTS]
        weights = [w for _, w in STATUS_WEIGHTS]
        storage = [w for w in warehouses if w.kind != Warehouse.Kind.SC]
        sc = next(w for w in warehouses if w.kind == Warehouse.Kind.SC)
        in_sc = {Part.Status.ACCEPTED, Part.Status.WASHING, Part.Status.PHOTO, Part.Status.READY}

        n = opts['parts']
        for i in range(n):
            status = rnd.choices(statuses, weights)[0]
            wh = sc if status in in_sc else rnd.choice(storage)
            car = rnd.choice(models)
            price = Decimal(rnd.randrange(1500, 60000, 50))
            Part.objects.create(
                category=rnd.choice(categories),
                brand_id=car.brand_id,
                car_model=car,
                year=rnd.randint(1995, 2022),
                engine_code=rnd.choice(ENGINES),
                oem=f'{rnd.randint(100, 999)}{rnd.choice("ABCDEFGHJK")}{rnd.randint(10000, 99999)}',
                condition=rnd.choice(Part.Condition.values),
                price=price,
                min_price=(price * Decimal('0.8')).quantize(Decimal('1')),
                warehouse=wh,
                cell=rnd.choice(cells[wh.pk]) if status != Part.Status.ACCEPTED else None,
                status=status,
            )
            if (i + 1) % 1000 == 0:
                self.stdout.write(f'  создано {i + 1} из {n}')

        self.stdout.write(self.style.SUCCESS(f'Готово: {n} деталей, {len(warehouses)} склада, '
                                             f'{len(categories)} категорий, {len(models)} моделей.'))
