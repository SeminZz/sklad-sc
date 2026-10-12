"""Заполняет справочник марок и моделей из parts/data/cars.json.

Источник: бесплатная база cars-base.ru (https://github.com/blanzh/carsBase).
Уже существующие марки и модели (совпадение без учёта регистра) не дублируются:
у них только дозаполняются пустые поля.
"""
import json
from pathlib import Path

from django.db import migrations

DATA_FILE = Path(__file__).resolve().parent.parent / 'data' / 'cars.json'


def load(apps, schema_editor):
    Brand = apps.get_model('parts', 'Brand')
    CarModel = apps.get_model('parts', 'CarModel')
    data = json.loads(DATA_FILE.read_text(encoding='utf-8'))

    brands = {b.name.lower(): b for b in Brand.objects.all()}
    for item in data:
        brand = brands.get(item['name'].lower())
        if brand is None:
            brand = Brand.objects.create(
                name=item['name'], name_ru=item['name_ru'], country=item['country'], is_popular=item['popular'],
            )
        else:
            brand.name_ru = brand.name_ru or item['name_ru']
            brand.country = brand.country or item['country']
            brand.is_popular = brand.is_popular or item['popular']
            brand.save()

        existing = {m.name.lower(): m for m in CarModel.objects.filter(brand=brand)}
        new = []
        for name, name_ru, year_from, year_to in item['models']:
            model = existing.get(name.lower())
            if model is None:
                new.append(CarModel(brand=brand, name=name, name_ru=name_ru, year_from=year_from, year_to=year_to))
            elif not model.name_ru:
                model.name_ru = name_ru
                model.year_from = model.year_from or year_from
                model.year_to = model.year_to or year_to
                model.save()
        CarModel.objects.bulk_create(new)


class Migration(migrations.Migration):

    dependencies = [
        ('parts', '0004_brand_model_details'),
    ]

    operations = [
        migrations.RunPython(load, migrations.RunPython.noop),
    ]
