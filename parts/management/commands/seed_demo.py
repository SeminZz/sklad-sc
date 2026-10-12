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

# Самые ходовые категории: на них приходится большая часть тестовых деталей,
# чтобы группировка выглядела как в жизни. Остальные берутся из справочника случайно.
POPULAR_CATEGORIES = [
    'Генератор', 'Стартер', 'Компрессор кондиционера', 'ТНВД', 'Турбина', 'Рейка рулевая',
    'Насос гидроусилителя руля (ГУР)', 'Блок ABS', 'Форсунка топливная', 'Заслонка дроссельная',
    'КПП автомат (автоматическая коробка)', 'Фара левая', 'Фара правая', 'Блок управления двигателем',
    'Двигатель (ДВС)', 'Зеркало наружное левое', 'Бампер передний', 'Дверь передняя левая',
    'Радиатор основной', 'Суппорт передний левый',
]

# Модель берётся из справочника (cars.json), поколение пишется в деталь отдельно
CARS = {
    'Ford': [('Focus', 'II'), ('Focus', 'III'), ('Fiesta', 'V'), ('Mondeo', 'IV'), ('Kuga', 'I')],
    'Opel': [('Astra', 'H'), ('Vectra', 'C'), ('Zafira', 'A'), ('Zafira', 'B'), ('Insignia', 'A')],
    'Volkswagen': [('Golf', 'III'), ('Golf', 'V'), ('Passat', 'B6'), ('Polo', 'V'), ('Touran', 'I')],
    'Toyota': [('Corolla', 'E150'), ('Camry', 'XV40'), ('RAV4', 'III'), ('Avensis', 'II')],
    'Renault': [('Scenic', 'II'), ('Megane', 'II'), ('Logan', 'I'), ('Duster', 'I')],
    'Mazda': [('6', 'GG'), ('3', 'BK'), ('Millenia', ''), ('CX-7', '')],
    'Hyundai': [('Sonata', 'V'), ('Solaris', 'I'), ('Tucson', 'I'), ('Santa Fe', 'II')],
    'Honda': [('Accord', 'V'), ('Accord', 'VII'), ('Civic', 'VIII'), ('CR-V', 'III')],
    'Mitsubishi': [('Colt', 'VI'), ('Lancer', 'IX'), ('Outlander', 'II'), ('Pajero', 'IV')],
    'BMW': [('3 серии', 'E90'), ('5 серии', 'E60'), ('X5', 'E70')],
    'Lada (ВАЗ)': [('2107', ''), ('Priora', 'I'), ('Granta', 'I'), ('Kalina', 'II')],
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

        all_categories = list(Category.objects.all())
        if not all_categories:
            self.stderr.write('Справочник категорий пуст. Сначала выполните: python manage.py migrate')
            return
        popular = [c for c in all_categories if c.name in POPULAR_CATEGORIES] or all_categories
        models = []  # пары (модель, поколение)
        for brand_name, items in CARS.items():
            brand, _ = Brand.objects.get_or_create(name=brand_name)
            for model_name, generation in items:
                model = (CarModel.objects.filter(brand=brand, name__iexact=model_name).first()
                         or CarModel.objects.create(brand=brand, name=model_name))
                models.append((model, generation))

        statuses = [s for s, _ in STATUS_WEIGHTS]
        weights = [w for _, w in STATUS_WEIGHTS]
        storage = [w for w in warehouses if w.kind != Warehouse.Kind.SC]
        sc = next(w for w in warehouses if w.kind == Warehouse.Kind.SC)
        in_sc = {Part.Status.ACCEPTED, Part.Status.WASHING, Part.Status.PHOTO, Part.Status.READY}

        n = opts['parts']
        for i in range(n):
            status = rnd.choices(statuses, weights)[0]
            wh = sc if status in in_sc else rnd.choice(storage)
            car, generation = rnd.choice(models)
            price = Decimal(rnd.randrange(1500, 60000, 50))
            Part.objects.create(
                category=rnd.choice(popular if rnd.random() < 0.85 else all_categories),
                brand_id=car.brand_id,
                car_model=car,
                generation=generation,
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

        # Несколько выдуманных покупателей, чтобы было кого искать в окне «Поиск покупателя»
        from sales.models import Customer, phone_digits
        demo_customers = [
            dict(last_name='Иванов', first_name='Пётр', middle_name='Сергеевич', phone='+7 900 000-00-01', city='Тестовск'),
            dict(last_name='Смирнова', first_name='Анна', phone='8 900 000-00-02', email='anna@example.com'),
            dict(last_name='Кузнецов', first_name='Олег', phone='+7 900 000 00 03', discount=5),
            dict(kind=Customer.Kind.COMPANY, company_name='ООО «Пример Авто»', inn='0000000000',
                 phone='+7 900 000-00-04', discount=10),
            dict(kind=Customer.Kind.IP, company_name='ИП Петров', last_name='Петров', first_name='Илья',
                 phone='+7 900 000-00-05'),
        ]
        for data in demo_customers:
            if not Customer.objects.filter(phone_digits=phone_digits(data['phone'])).exists():
                Customer.objects.create(**data)

        self.stdout.write(self.style.SUCCESS(f'Готово: {n} деталей, {len(warehouses)} склада, '
                                             f'{len(all_categories)} категорий в справочнике, {len(models)} моделей.'))
