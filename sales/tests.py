import json

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from parts.models import Category, Part
from warehouse.models import Warehouse

from .models import Cart, CartItem, Customer, phone_digits


def post(client, url, data):
    return client.post(url, json.dumps(data), content_type='application/json')


class PhoneTests(TestCase):
    def test_phone_normalized(self):
        self.assertEqual(phone_digits('+7 (978) 123-45-67'), '79781234567')
        self.assertEqual(phone_digits('8 978 123 45 67'), '79781234567')
        self.assertEqual(phone_digits('9781234567'), '79781234567')


class CustomerSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('manager', password='x')
        cls.ivanov = Customer.objects.create(last_name='Иванов', first_name='Пётр', phone='+7 978 123-45-67')
        cls.firm = Customer.objects.create(kind=Customer.Kind.COMPANY, company_name='ООО Ромашка', phone='+7 978 765-43-21')

    def setUp(self):
        self.client.force_login(self.user)

    def search(self, q):
        r = self.client.get(reverse('customers_search'), {'q': q})
        return [c['id'] for c in r.json()['customers']]

    def test_by_phone_in_any_format(self):
        for q in ['89781234567', '+7 (978) 123-45-67', '123-45-67', '978 123']:
            self.assertEqual(self.search(q), [self.ivanov.pk], q)

    def test_by_name_any_case(self):
        self.assertEqual(self.search('иванов'), [self.ivanov.pk])
        self.assertEqual(self.search('ИВАНОВ пётр'), [self.ivanov.pk])
        self.assertEqual(self.search('ромашка'), [self.firm.pk])

    def test_nothing_found_and_empty_query(self):
        self.assertEqual(self.search('Сидоров'), [])
        self.assertEqual(self.search(''), [])


class CustomerCreateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('manager', password='x')
        self.client.force_login(self.user)

    def test_create_person(self):
        r = post(self.client, reverse('customer_create'),
                 {'kind': 'person', 'last_name': 'Сидоров', 'first_name': 'Иван', 'phone': '8 978 000 11 22',
                  'discount': '5', 'country': 'Россия'})
        self.assertEqual(r.status_code, 201, r.content)
        c = Customer.objects.get(pk=r.json()['customer']['id'])
        self.assertEqual(c.phone_digits, '79780001122')
        self.assertEqual(c.manager, self.user)  # по умолчанию ответственный — тот, кто создал
        self.assertEqual(c.created_by, self.user)

    def test_requires_name_and_contact(self):
        r = post(self.client, reverse('customer_create'), {'kind': 'person', 'discount': '0'})
        self.assertEqual(r.status_code, 400)
        errors = r.json()['errors']
        self.assertIn('last_name', errors)

        r = post(self.client, reverse('customer_create'), {'kind': 'person', 'last_name': 'Без телефона', 'discount': '0'})
        self.assertIn('phone', r.json()['errors'])

    def test_company_requires_name(self):
        r = post(self.client, reverse('customer_create'), {'kind': 'company', 'phone': '+79780000000', 'discount': '0'})
        self.assertIn('company_name', r.json()['errors'])


class CartTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_demo', parts=50, verbosity=0)
        cls.user = User.objects.create_user('manager', password='x')
        cls.other = User.objects.create_user('other', password='x')
        cls.customer = Customer.objects.create(last_name='Иванов', phone='+79780000001')
        cls.part = Part.objects.filter(status=Part.Status.PLACED).first()

    def setUp(self):
        self.client.force_login(self.user)

    def test_add_creates_cart_and_reuses_it(self):
        r = post(self.client, reverse('cart_add'), {'part_id': self.part.pk, 'customer_id': self.customer.pk})
        self.assertEqual(r.status_code, 200, r.content)
        cart_id = r.json()['cart']['id']
        other_part = Part.objects.filter(status=Part.Status.PLACED).exclude(pk=self.part.pk).first()
        r = post(self.client, reverse('cart_add'), {'part_id': other_part.pk, 'customer_id': self.customer.pk})
        self.assertEqual(r.json()['cart']['id'], cart_id)
        self.assertEqual(len(r.json()['cart']['items']), 2)
        self.assertEqual(Cart.objects.filter(customer=self.customer, is_open=True).count(), 1)

    def test_same_part_not_duplicated(self):
        for _ in range(2):
            r = post(self.client, reverse('cart_add'), {'part_id': self.part.pk, 'customer_id': self.customer.pk})
        self.assertFalse(r.json()['added'])
        self.assertEqual(CartItem.objects.filter(part=self.part).count(), 1)

    def test_sold_part_rejected(self):
        sold = Part.objects.filter(status=Part.Status.SOLD).first()
        r = post(self.client, reverse('cart_add'), {'part_id': sold.pk, 'customer_id': self.customer.pk})
        self.assertEqual(r.status_code, 400)

    def test_warning_when_part_in_other_open_cart(self):
        cart = Cart.objects.create(customer=self.customer, owner=self.other)
        CartItem.objects.create(cart=cart, part=self.part, price=self.part.price)
        r = post(self.client, reverse('cart_add'), {'part_id': self.part.pk, 'customer_id': self.customer.pk})
        self.assertIn('уже лежит в другой корзине', r.json()['warning'])

    def test_carts_are_per_manager_and_close(self):
        post(self.client, reverse('cart_add'), {'part_id': self.part.pk, 'customer_id': self.customer.pk})
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('carts_list')).json()['carts'], [])
        self.client.force_login(self.user)
        cart = self.client.get(reverse('carts_list')).json()['carts'][0]
        r = post(self.client, reverse('cart_close', args=[cart['id']]), {})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get(reverse('carts_list')).json()['carts'], [])
        self.assertFalse(CartItem.objects.filter(cart_id=cart['id']).exists())

    def test_other_manager_cannot_touch_my_cart(self):
        r = post(self.client, reverse('cart_add'), {'part_id': self.part.pk, 'customer_id': self.customer.pk})
        cart_id = r.json()['cart']['id']
        self.client.force_login(self.other)
        self.assertEqual(post(self.client, reverse('cart_clear', args=[cart_id]), {}).status_code, 404)

    def test_stock_page_has_cart_and_dialogs(self):
        r = self.client.get(reverse('stock'))
        self.assertContains(r, 'id="dlg-customer"')
        self.assertContains(r, 'Создание покупателя')
