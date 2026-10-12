"""Заполняет справочник категорий из parts/data/categories.txt.

Существующие категории не трогает, добавляет только недостающие.
Список зафиксирован здесь на момент миграции; новые категории потом
добавляются через админку или новой миграцией.
"""
from pathlib import Path

from django.db import migrations

DATA_FILE = Path(__file__).resolve().parent.parent / 'data' / 'categories.txt'


def read_names():
    names = []
    for line in DATA_FILE.read_text(encoding='utf-8').splitlines():
        line = ' '.join(line.split())
        if line and not line.startswith('#'):
            names.append(line)
    return names


def load(apps, schema_editor):
    Category = apps.get_model('parts', 'Category')
    existing = {n.lower() for n in Category.objects.values_list('name', flat=True)}
    Category.objects.bulk_create(
        [Category(name=n) for n in read_names() if n.lower() not in existing]
    )


class Migration(migrations.Migration):

    dependencies = [
        ('parts', '0002_category_name_255'),
    ]

    operations = [
        migrations.RunPython(load, migrations.RunPython.noop),
    ]
