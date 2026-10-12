import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from parts.models import Part
from warehouse.models import TimeStamped


def phone_digits(value):
    """Только цифры телефона, российский номер приводится к виду 7XXXXXXXXXX."""
    digits = re.sub(r'\D', '', value or '')
    if len(digits) == 11 and digits.startswith('8'):
        digits = '7' + digits[1:]
    elif len(digits) == 10 and digits.startswith('9'):
        digits = '7' + digits
    return digits


class Customer(TimeStamped):
    class Kind(models.TextChoices):
        PERSON = 'person', 'Физическое лицо'
        IP = 'ip', 'Индивидуальный предприниматель'
        COMPANY = 'company', 'Юридическое лицо'

    class Gender(models.TextChoices):
        MALE = 'm', 'Мужской'
        FEMALE = 'f', 'Женский'

    kind = models.CharField('тип собственности', max_length=10, choices=Kind.choices, default=Kind.PERSON)
    last_name = models.CharField('фамилия', max_length=60, blank=True)
    first_name = models.CharField('имя', max_length=60, blank=True)
    middle_name = models.CharField('отчество', max_length=60, blank=True)
    company_name = models.CharField('название организации', max_length=200, blank=True)
    inn = models.CharField('ИНН', max_length=12, blank=True)

    phone = models.CharField('телефон', max_length=30, blank=True)
    phone_digits = models.CharField('телефон (цифры)', max_length=20, blank=True, editable=False, db_index=True)
    email = models.EmailField('email', blank=True)
    gender = models.CharField('пол', max_length=1, choices=Gender.choices, blank=True)

    country = models.CharField('страна', max_length=60, blank=True, default='Россия')
    region = models.CharField('область', max_length=100, blank=True)
    city = models.CharField('город', max_length=100, blank=True)
    street = models.CharField('улица', max_length=150, blank=True)
    house = models.CharField('дом', max_length=20, blank=True)
    flat = models.CharField('кв.', max_length=20, blank=True)
    postcode = models.CharField('индекс', max_length=10, blank=True)
    vin = models.CharField('VIN-код', max_length=17, blank=True)

    manager = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='ответственный менеджер',
                                on_delete=models.SET_NULL, null=True, blank=True, related_name='customers')
    discount = models.DecimalField('скидка, %', max_digits=5, decimal_places=2, default=0,
                                   validators=[MinValueValidator(0), MaxValueValidator(100)])
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='создал', on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name='+')

    # Строка для поиска в нижнем регистре: ФИО, организация, телефон, email.
    # Нужна, потому что SQLite не ищет кириллицу без учёта регистра.
    search_text = models.TextField(editable=False, blank=True)

    class Meta:
        verbose_name = 'покупатель'
        verbose_name_plural = 'покупатели'
        ordering = ['-created_at']

    def __str__(self):
        return self.display_name or f'Покупатель №{self.pk}'

    @property
    def display_name(self):
        fio = ' '.join(x for x in [self.last_name, self.first_name, self.middle_name] if x)
        if self.kind != self.Kind.PERSON and self.company_name:
            return self.company_name + (f' ({fio})' if fio else '')
        return fio or self.company_name

    @property
    def address(self):
        parts = [self.postcode, self.region, self.city, self.street,
                 f'д. {self.house}' if self.house else '', f'кв. {self.flat}' if self.flat else '']
        return ', '.join(p for p in parts if p)

    def clean(self):
        if self.kind == self.Kind.PERSON and not (self.last_name or self.first_name):
            raise ValidationError({'last_name': 'Укажите фамилию или имя.'})
        if self.kind != self.Kind.PERSON and not self.company_name:
            raise ValidationError({'company_name': 'Укажите название организации.'})
        if not (self.phone or self.email):
            raise ValidationError({'phone': 'Укажите телефон или email, чтобы с покупателем можно было связаться.'})
        if self.phone and len(phone_digits(self.phone)) < 10:
            raise ValidationError({'phone': 'Похоже, в телефоне не хватает цифр.'})
        if self.vin and len(self.vin.strip()) != 17:
            raise ValidationError({'vin': 'VIN состоит из 17 символов.'})

    def save(self, *args, **kwargs):
        for f in ('last_name', 'first_name', 'middle_name', 'company_name', 'phone', 'email', 'city'):
            setattr(self, f, ' '.join((getattr(self, f) or '').split()))
        self.vin = (self.vin or '').strip().upper()
        self.phone_digits = phone_digits(self.phone)
        self.search_text = ' '.join(x for x in [
            self.last_name, self.first_name, self.middle_name, self.company_name, self.inn,
            self.phone_digits, self.email, self.city, self.vin,
        ] if x).lower()
        super().save(*args, **kwargs)


class Cart(TimeStamped):
    """Корзина покупателя. У менеджера может быть открыто несколько корзин (вкладки внизу «Склада»)."""
    customer = models.ForeignKey(Customer, verbose_name='покупатель', on_delete=models.PROTECT, related_name='carts')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='менеджер', on_delete=models.PROTECT,
                              related_name='carts')
    is_open = models.BooleanField('открыта', default=True)

    class Meta:
        verbose_name = 'корзина'
        verbose_name_plural = 'корзины'
        ordering = ['created_at']
        indexes = [models.Index(fields=['owner', 'is_open'])]

    def __str__(self):
        return f'Корзина №{self.pk}: {self.customer}'


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, verbose_name='корзина', on_delete=models.CASCADE, related_name='items')
    part = models.ForeignKey(Part, verbose_name='деталь', on_delete=models.PROTECT, related_name='cart_items')
    price = models.DecimalField('цена на момент добавления, ₽', max_digits=12, decimal_places=2, null=True, blank=True)
    added_at = models.DateTimeField('добавлено', auto_now_add=True)

    class Meta:
        verbose_name = 'позиция корзины'
        verbose_name_plural = 'позиции корзины'
        ordering = ['added_at']
        constraints = [models.UniqueConstraint(fields=['cart', 'part'], name='uniq_part_per_cart')]

    def __str__(self):
        return str(self.part)
