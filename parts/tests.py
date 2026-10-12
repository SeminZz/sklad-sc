from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from warehouse.models import Cell, Warehouse

from .models import Brand, CarModel, Category, Part


class PartModelTests(TestCase):
    def setUp(self):
        self.wh = Warehouse.objects.create(name='Склад', code='S1')
        self.other_wh = Warehouse.objects.create(name='Другой', code='S2')
        self.cat = Category.objects.create(name='Генератор')
        self.ford = Brand.objects.create(name='Ford')
        self.opel = Brand.objects.create(name='Opel')
        self.focus = CarModel.objects.create(brand=self.ford, name='Focus 2')

    def test_barcode_and_brand_filled_automatically(self):
        p = Part.objects.create(category=self.cat, car_model=self.focus, warehouse=self.wh, oem=' ab123 ')
        p.refresh_from_db()
        self.assertEqual(p.barcode, f'P{p.pk:07d}')
        self.assertEqual(p.brand, self.ford)
        self.assertEqual(p.oem, 'AB123')

    def test_model_must_match_brand(self):
        p = Part(category=self.cat, brand=self.opel, car_model=self.focus, warehouse=self.wh)
        with self.assertRaises(ValidationError):
            p.full_clean()

    def test_cell_must_be_on_same_warehouse(self):
        cell = Cell.objects.create(warehouse=self.other_wh, zone='A', rack='1')
        p = Part(category=self.cat, warehouse=self.wh, cell=cell)
        with self.assertRaises(ValidationError):
            p.full_clean()

    def test_delete_forbidden(self):
        p = Part.objects.create(category=self.cat, warehouse=self.wh)
        with self.assertRaises(ValidationError):
            p.delete()
        self.assertTrue(Part.objects.filter(pk=p.pk).exists())


class StockPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_demo', parts=300, verbosity=0)
        cls.user = User.objects.create_user('kladovshik', password='x')

    def setUp(self):
        self.client.force_login(self.user)

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('stock')).status_code, 302)
        self.assertEqual(self.client.get(reverse('stock_api')).status_code, 302)

    def test_page_opens(self):
        r = self.client.get(reverse('stock'))
        self.assertContains(r, 'Перетяните сюда заголовок колонки')

    def test_default_hides_sold_and_written_off(self):
        data = self.client.get(reverse('stock_api')).json()
        active = Part.objects.exclude(status__in=['sold', 'written_off']).count()
        self.assertEqual(data['total'], active)
        self.assertFalse({r['status'] for r in data['rows']} & {'sold', 'written_off'})

    def test_filter_by_category_and_search_by_barcode(self):
        part = Part.objects.first()
        data = self.client.get(reverse('stock_api'), {'q': part.barcode, 'status': 'all'}).json()
        self.assertEqual([r['id'] for r in data['rows']], [part.pk])

        cat = Category.objects.get(name='Генератор')
        data = self.client.get(reverse('stock_api'), {'category': cat.pk, 'status': 'all'}).json()
        self.assertEqual(data['total'], Part.objects.filter(category=cat).count())
        self.assertTrue(all(r['category'] == 'Генератор' for r in data['rows']))

    def test_limit(self):
        data = self.client.get(reverse('stock_api'), {'limit': 500, 'status': 'all'}).json()
        self.assertEqual(data['total'], 300)
        self.assertEqual(data['shown'], 300)
        data = self.client.get(reverse('stock_api'), {'limit': 1, 'status': 'all'}).json()
        self.assertEqual(data['shown'], 1)
