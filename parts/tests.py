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
        self.cat, _ = Category.objects.get_or_create(name='Генератор')
        self.ford, _ = Brand.objects.get_or_create(name='Ford')
        self.opel, _ = Brand.objects.get_or_create(name='Opel')
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

        # из поля с подсказками категория приходит названием, регистр не важен
        data = self.client.get(reverse('stock_api'), {'category': 'генератор', 'status': 'all'}).json()
        self.assertEqual(data['total'], Part.objects.filter(category=cat).count())


    def test_limit(self):
        data = self.client.get(reverse('stock_api'), {'limit': 500, 'status': 'all'}).json()
        self.assertEqual(data['total'], 300)
        self.assertEqual(data['shown'], 300)
        data = self.client.get(reverse('stock_api'), {'limit': 1, 'status': 'all'}).json()
        self.assertEqual(data['shown'], 1)


class CategoriesLoadedTests(TestCase):
    def test_full_list_loaded_by_migration(self):
        self.assertGreaterEqual(Category.objects.count(), 809)
        self.assertTrue(Category.objects.filter(name='Фильтр паров топлива').exists())


class BrandsModelsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('admin', 'admin@example.com', 'x')
        cls.ford = Brand.objects.get(name='Ford')
        cls.opel = Brand.objects.get(name='Opel')

    def setUp(self):
        self.client.force_login(self.user)

    def test_reference_loaded_by_migration(self):
        self.assertGreaterEqual(Brand.objects.count(), 400)
        self.assertGreaterEqual(CarModel.objects.count(), 4900)
        focus = CarModel.objects.get(brand=self.ford, name='Focus')
        self.assertEqual(focus.name_ru, 'Фокус')
        self.assertTrue(self.ford.is_popular)
        self.assertTrue(Brand.objects.filter(name='Lada (ВАЗ)').exists())

    def test_models_api_returns_only_selected_brand(self):
        data = self.client.get(reverse('models_api'), {'brand': self.ford.pk}).json()
        ids = {m['id'] for m in data['models']}
        self.assertEqual(ids, set(CarModel.objects.filter(brand=self.ford).values_list('id', flat=True)))
        self.assertIn('Focus', {m['name'] for m in data['models']})
        self.assertNotIn('Vectra', {m['name'] for m in data['models']})

    def test_models_api_without_brand_is_empty(self):
        self.assertEqual(self.client.get(reverse('models_api')).json(), {'models': []})

    def test_admin_form_offers_only_models_of_brand(self):
        from .admin import PartAdminForm
        form = PartAdminForm()
        self.assertEqual(form.fields['car_model'].queryset.count(), 0)  # марка не выбрана
        form = PartAdminForm(data={'brand': str(self.ford.pk)})
        qs = form.fields['car_model'].queryset
        self.assertTrue(qs.exists())
        self.assertFalse(qs.exclude(brand=self.ford).exists())

    def test_admin_form_rejects_model_of_other_brand(self):
        from .admin import PartAdminForm
        wh = Warehouse.objects.create(name='Склад', code='S1')
        vectra = CarModel.objects.get(brand=self.opel, name='Vectra')
        form = PartAdminForm(data={
            'brand': str(self.ford.pk), 'car_model': str(vectra.pk), 'category': Category.objects.first().pk,
            'warehouse': wh.pk, 'status': 'accepted', 'condition': 'used_good',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('car_model', form.errors)

    def test_admin_add_page_opens(self):
        r = self.client.get(reverse('admin:parts_part_add'))
        self.assertContains(r, 'Популярные')
        self.assertContains(r, 'js/admin_part.js')
