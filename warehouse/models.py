from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

# Коды и части адреса только латиница, цифры и дефис.
# Защита от путаницы кириллической «А» и латинской «A»: на вид одинаковы,
# а для базы и сканера это разные символы.
latin_code_validator = RegexValidator(
    r'^[A-Z0-9-]+$',
    'Только заглавные латинские буквы, цифры и дефис (без кириллицы).',
)
address_part_validator = RegexValidator(
    r'^[A-Za-z0-9-]*$',
    'Только латинские буквы, цифры и дефис (без кириллицы).',
)


class TimeStamped(models.Model):
    created_at = models.DateTimeField('создано', auto_now_add=True)
    updated_at = models.DateTimeField('изменено', auto_now=True)

    class Meta:
        abstract = True


class Warehouse(TimeStamped):
    class Kind(models.TextChoices):
        WAREHOUSE = 'warehouse', 'Склад хранения'
        SC = 'sc', 'Сортировочный центр'
        TRANSIT = 'transit', 'Транзит'

    name = models.CharField('название', max_length=100, unique=True)
    code = models.CharField(
        'код', max_length=20, unique=True, validators=[latin_code_validator],
        help_text='Короткий код латиницей, например SKL1. Используется в отчётах и бирках.',
    )
    kind = models.CharField('тип', max_length=20, choices=Kind.choices, default=Kind.WAREHOUSE)
    city = models.CharField('город', max_length=100, blank=True)
    address = models.CharField('адрес', max_length=255, blank=True)
    is_active = models.BooleanField('активен', default=True)
    notes = models.TextField('примечание', blank=True)

    class Meta:
        verbose_name = 'склад'
        verbose_name_plural = 'склады'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.code = (self.code or '').strip().upper()
        super().save(*args, **kwargs)


class Cell(TimeStamped):
    class CellType(models.TextChoices):
        SHELF = 'shelf', 'Полка'
        PALLET = 'pallet', 'Паллетное место'
        FLOOR = 'floor', 'Напольное хранение'
        BULKY = 'bulky', 'Крупногабарит'
        BUFFER = 'buffer', 'Буфер / зона приёмки'

    warehouse = models.ForeignKey(
        Warehouse, verbose_name='склад', on_delete=models.PROTECT, related_name='cells',
    )

    # Части адреса. Из них собирается адрес вида 1.A.12.4.C
    floor = models.PositiveSmallIntegerField('этаж', null=True, blank=True)
    zone = models.CharField('зона', max_length=10, blank=True, validators=[address_part_validator])
    rack = models.CharField('стеллаж', max_length=10, blank=True, validators=[address_part_validator])
    shelf = models.CharField('ярус', max_length=10, blank=True, validators=[address_part_validator])
    position = models.CharField('место', max_length=10, blank=True, validators=[address_part_validator])

    address = models.CharField(
        'адрес ячейки', max_length=60, blank=True,
        help_text='Собирается автоматически из этажа, зоны, стеллажа, яруса и места. '
                  'Вручную указывается, только если части не заполнены (например BUF-1).',
    )
    barcode = models.CharField(
        'штрихкод', max_length=32, unique=True, null=True, blank=True, editable=False,
        help_text='Создаётся автоматически и не меняется, даже если поменять адрес.',
    )

    cell_type = models.CharField('тип ячейки', max_length=20, choices=CellType.choices, default=CellType.SHELF)
    capacity = models.PositiveIntegerField('вместимость, шт.', null=True, blank=True)
    max_weight_kg = models.DecimalField('макс. вес, кг', max_digits=8, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField('активна', default=True)
    notes = models.TextField('примечание', blank=True)

    class Meta:
        verbose_name = 'ячейка'
        verbose_name_plural = 'ячейки'
        ordering = ['warehouse__name', 'address']
        constraints = [
            models.UniqueConstraint(fields=['warehouse', 'address'], name='uniq_cell_address_per_warehouse'),
        ]

    def __str__(self):
        return f'{self.warehouse.code} {self.address}' if self.warehouse_id else self.address

    def build_address(self):
        parts = [str(self.floor) if self.floor is not None else '', self.zone, self.rack, self.shelf, self.position]
        return '.'.join(p.strip().upper() for p in parts if p and p.strip())

    def _normalize(self):
        for field in ('zone', 'rack', 'shelf', 'position'):
            setattr(self, field, (getattr(self, field) or '').strip().upper())
        # Если заданы части адреса, адрес всегда собирается из них (чтобы не расходились).
        # Ручной адрес используется, только когда части не заполнены.
        self.address = self.build_address() or (self.address or '').strip().upper()

    def clean(self):
        self._normalize()
        if not self.address:
            raise ValidationError('Укажите адрес ячейки или хотя бы одну его часть (этаж, зона, стеллаж, ярус, место).')
        address_part_validator(self.address.replace('.', ''))

    def save(self, *args, **kwargs):
        self._normalize()
        super().save(*args, **kwargs)
        if not self.barcode:
            # Штрихкод по номеру записи: стабильный, только латиница и цифры (Code128).
            self.barcode = f'C{self.pk:07d}'
            Cell.objects.filter(pk=self.pk).update(barcode=self.barcode)
