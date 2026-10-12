from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Cell, Warehouse


class CellTests(TestCase):
    def setUp(self):
        self.wh = Warehouse.objects.create(name='Тестовый склад', code='tst1')

    def test_warehouse_code_uppercased(self):
        self.assertEqual(self.wh.code, 'TST1')

    def test_address_built_from_parts(self):
        cell = Cell.objects.create(warehouse=self.wh, floor=1, zone='a', rack='12', shelf='4', position='c')
        self.assertEqual(cell.address, '1.A.12.4.C')

    def test_manual_address_kept(self):
        cell = Cell.objects.create(warehouse=self.wh, address='buf-1')
        self.assertEqual(cell.address, 'BUF-1')

    def test_barcode_generated_and_stable(self):
        cell = Cell.objects.create(warehouse=self.wh, zone='A', rack='1')
        cell.refresh_from_db()
        self.assertEqual(cell.barcode, f'C{cell.pk:07d}')
        cell.rack = '2'
        cell.save()
        cell.refresh_from_db()
        self.assertEqual(cell.address, 'A.2')
        self.assertEqual(cell.barcode, f'C{cell.pk:07d}')

    def test_duplicate_address_in_same_warehouse_rejected(self):
        Cell.objects.create(warehouse=self.wh, zone='A', rack='1')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Cell.objects.create(warehouse=self.wh, zone='A', rack='1')

    def test_same_address_in_other_warehouse_allowed(self):
        other = Warehouse.objects.create(name='Другой склад', code='TST2')
        Cell.objects.create(warehouse=self.wh, zone='A', rack='1')
        Cell.objects.create(warehouse=other, zone='A', rack='1')
        self.assertEqual(Cell.objects.count(), 2)

    def test_cyrillic_rejected(self):
        cell = Cell(warehouse=self.wh, zone='А', rack='1')  # кириллическая «А»
        with self.assertRaises(ValidationError):
            cell.full_clean()

    def test_empty_address_rejected(self):
        cell = Cell(warehouse=self.wh)
        with self.assertRaises(ValidationError):
            cell.full_clean()
