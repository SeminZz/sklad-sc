from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from warehouse.models import Cell, TimeStamped, Warehouse


class Category(models.Model):
    name = models.CharField('название', max_length=100, unique=True)

    class Meta:
        verbose_name = 'категория'
        verbose_name_plural = 'категории'
        ordering = ['name']

    def __str__(self):
        return self.name


class Brand(models.Model):
    name = models.CharField('марка', max_length=60, unique=True)

    class Meta:
        verbose_name = 'марка авто'
        verbose_name_plural = 'марки авто'
        ordering = ['name']

    def __str__(self):
        return self.name


class CarModel(models.Model):
    brand = models.ForeignKey(Brand, verbose_name='марка', on_delete=models.PROTECT, related_name='models')
    name = models.CharField('модель', max_length=80)

    class Meta:
        verbose_name = 'модель авто'
        verbose_name_plural = 'модели авто'
        ordering = ['brand__name', 'name']
        constraints = [
            models.UniqueConstraint(fields=['brand', 'name'], name='uniq_car_model_per_brand'),
        ]

    def __str__(self):
        return f'{self.brand.name} {self.name}'


class Part(TimeStamped):
    """Одна физическая деталь = одна запись = одна бирка."""

    class Status(models.TextChoices):
        ACCEPTED = 'accepted', 'Принято'
        WASHING = 'washing', 'На мойке'
        PHOTO = 'photo', 'На фото'
        READY = 'ready', 'Готово к размещению'
        PLACED = 'placed', 'Размещено'
        RESERVED = 'reserved', 'В резерве'
        SOLD = 'sold', 'Продано'
        WRITTEN_OFF = 'written_off', 'Списано'

    class Condition(models.TextChoices):
        NEW = 'new', 'Новая'
        USED_GOOD = 'used_good', 'Б/у, хорошее'
        USED_OK = 'used_ok', 'Б/у, удовлетворительное'
        FOR_REPAIR = 'for_repair', 'Под восстановление'

    barcode = models.CharField(
        'бирка (штрихкод)', max_length=32, unique=True, null=True, blank=True, editable=False,
        help_text='Создаётся автоматически при сохранении: P0000123.',
    )
    category = models.ForeignKey(Category, verbose_name='категория', on_delete=models.PROTECT, related_name='parts')
    brand = models.ForeignKey(Brand, verbose_name='марка', on_delete=models.PROTECT, null=True, blank=True,
                              related_name='parts')
    car_model = models.ForeignKey(CarModel, verbose_name='модель', on_delete=models.PROTECT, null=True, blank=True,
                                  related_name='parts')
    year = models.PositiveSmallIntegerField('год', null=True, blank=True)
    engine_code = models.CharField('ДВС / маркировка', max_length=60, blank=True)
    oem = models.CharField('OEM-номер', max_length=60, blank=True)
    condition = models.CharField('состояние', max_length=20, choices=Condition.choices, default=Condition.USED_GOOD)
    defects = models.TextField('дефекты', blank=True)
    description = models.TextField('описание', blank=True)

    price = models.DecimalField('цена, ₽', max_digits=12, decimal_places=2, null=True, blank=True)
    min_price = models.DecimalField('мин. цена, ₽', max_digits=12, decimal_places=2, null=True, blank=True)

    warehouse = models.ForeignKey(Warehouse, verbose_name='склад', on_delete=models.PROTECT, related_name='parts')
    cell = models.ForeignKey(Cell, verbose_name='ячейка', on_delete=models.PROTECT, null=True, blank=True,
                             related_name='parts')
    status = models.CharField('статус', max_length=20, choices=Status.choices, default=Status.ACCEPTED)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='создал', on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name='+')

    class Meta:
        verbose_name = 'деталь'
        verbose_name_plural = 'детали'
        ordering = ['-id']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['oem']),
            models.Index(fields=['engine_code']),
            models.Index(fields=['category', 'brand', 'car_model']),
        ]

    def __str__(self):
        name = ' '.join(str(x) for x in [self.category, self.car_model or self.brand or ''] if x)
        return f'{self.barcode or "—"} {name}'

    def clean(self):
        if self.car_model_id and self.brand_id and self.car_model.brand_id != self.brand_id:
            raise ValidationError({'car_model': 'Модель не относится к выбранной марке.'})
        if self.cell_id and self.warehouse_id and self.cell.warehouse_id != self.warehouse_id:
            raise ValidationError({'cell': 'Ячейка находится на другом складе.'})
        if self.price is not None and self.min_price is not None and self.min_price > self.price:
            raise ValidationError({'min_price': 'Минимальная цена больше обычной.'})

    def save(self, *args, **kwargs):
        if self.car_model_id and not self.brand_id:
            self.brand_id = self.car_model.brand_id
        self.oem = (self.oem or '').strip().upper()
        self.engine_code = (self.engine_code or '').strip().upper()
        super().save(*args, **kwargs)
        if not self.barcode:
            self.barcode = f'P{self.pk:07d}'
            Part.objects.filter(pk=self.pk).update(barcode=self.barcode)

    def delete(self, *args, **kwargs):
        raise ValidationError('Детали не удаляются. Переведите в статус «Списано».')
