from datetime import date

from django.contrib.messages import get_messages
from django.urls import reverse

from core.test_helpers import CRMTestCase
from products.forms import AccountProductForm
from products.models import (
    AccountProduct,
    AccountProductFieldValue,
    ProductField,
)


# ---------------------------------------------------------------------------
# Phase 1: Model Tests
# ---------------------------------------------------------------------------

class AccountProductModelTest(CRMTestCase):

    def setUp(self):
        self.owner = self.create_verwalter()
        self.product = self.create_product()
        self.account = self.create_account(owner=self.owner)

    def test_get_responsible_explicit(self):
        responsible = self.create_verwalter(username='resp')
        ap = self.create_account_product(self.account, self.product, responsible=responsible)
        self.assertEqual(ap.get_responsible(), responsible)

    def test_get_responsible_fallback_single_product(self):
        ap = self.create_account_product(self.account, self.product)
        self.assertEqual(ap.get_responsible(), self.owner)

    def test_get_responsible_none_multiple_products(self):
        product2 = self.create_product(name='Zweites')
        self.create_account_product(self.account, self.product)
        ap2 = self.create_account_product(self.account, product2)
        self.assertIsNone(ap2.get_responsible())

    def test_get_responsible_ignores_archived(self):
        product2 = self.create_product(name='Zweites')
        self.create_account_product(self.account, self.product)
        self.create_account_product(self.account, product2, is_archived=True)
        ap = AccountProduct.objects.get(product=self.product, account=self.account)
        self.assertEqual(ap.get_responsible(), self.owner)

    def test_str_representation(self):
        ap = self.create_account_product(self.account, self.product)
        self.assertEqual(str(ap), f'{self.account.name} \u2013 {self.product.name}')


class AccountProductFieldValueModelTest(CRMTestCase):

    def setUp(self):
        self.account = self.create_account()
        self.product = self.create_product()
        self.ap = self.create_account_product(self.account, self.product)

    def test_get_value_date(self):
        field = self.create_product_field(self.product, name='Go-Live', field_type='date')
        fv = AccountProductFieldValue.objects.create(
            account_product=self.ap, field=field, value_date=date(2025, 6, 1),
        )
        self.assertEqual(fv.get_value(), date(2025, 6, 1))

    def test_get_value_integer(self):
        field = self.create_product_field(self.product, name='Anzahl', field_type='integer')
        fv = AccountProductFieldValue.objects.create(
            account_product=self.ap, field=field, value_int=42,
        )
        self.assertEqual(fv.get_value(), 42)

    def test_get_value_boolean(self):
        field = self.create_product_field(self.product, name='Aktiv', field_type='boolean')
        fv = AccountProductFieldValue.objects.create(
            account_product=self.ap, field=field, value_bool=True,
        )
        self.assertTrue(fv.get_value())

    def test_str_representation(self):
        field = self.create_product_field(self.product, name='Anzahl', field_type='integer')
        fv = AccountProductFieldValue.objects.create(
            account_product=self.ap, field=field, value_int=7,
        )
        self.assertEqual(str(fv), 'Anzahl: 7')


# ---------------------------------------------------------------------------
# Phase 2: Form Tests
# ---------------------------------------------------------------------------

class AccountProductFormTest(CRMTestCase):

    def test_phases_empty_without_product(self):
        form = AccountProductForm()
        self.assertEqual(form.fields['current_phase'].queryset.count(), 0)

    def test_phases_filtered_on_edit(self):
        product = self.create_product()
        other_product = self.create_product(name='Anderes')
        phase = self.create_phase(product, 'Phase 1')
        self.create_phase(other_product, 'Andere Phase')
        account = self.create_account()
        ap = self.create_account_product(account, product, phase=phase)
        form = AccountProductForm(instance=ap)
        self.assertIn(phase, form.fields['current_phase'].queryset)
        self.assertEqual(form.fields['current_phase'].queryset.count(), 1)

    def test_phases_filtered_from_post_data(self):
        product = self.create_product()
        phase = self.create_phase(product, 'Phase 1')
        form = AccountProductForm(data={'product': str(product.pk), 'current_phase': str(phase.pk)})
        self.assertIn(phase, form.fields['current_phase'].queryset)


# ---------------------------------------------------------------------------
# Phase 3: View Tests
# ---------------------------------------------------------------------------

class AccountProductAddViewTest(CRMTestCase):

    def setUp(self):
        self.admin = self.create_superuser()
        self.product = self.create_product()
        self.account = self.create_account(owner=self.admin)
        self.client.force_login(self.admin)
        self.url = reverse('accounts:account_product_add', kwargs={'account_pk': self.account.pk})

    def test_add_product_success(self):
        response = self.client.post(self.url, {'product': self.product.pk})
        self.assertRedirects(response, reverse('accounts:account_detail', kwargs={'pk': self.account.pk}))
        self.assertTrue(AccountProduct.objects.filter(account=self.account, product=self.product, is_archived=False).exists())

    def test_add_archived_duplicate_shows_error_no_500(self):
        ap = self.create_account_product(self.account, self.product, is_archived=True)
        response = self.client.post(self.url, {'product': self.product.pk})
        self.assertFalse(AccountProduct.objects.filter(account=self.account, product=self.product, is_archived=False).exists())
        self.assertEqual(AccountProduct.objects.filter(account=self.account, product=self.product).count(), 1)
        reactivate_url = reverse('accounts:account_product_archive', args=[ap.pk])
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any(reactivate_url in m for m in msgs))

    def test_add_active_duplicate_shows_error_no_500(self):
        ap = self.create_account_product(self.account, self.product, is_archived=False)
        response = self.client.post(self.url, {'product': self.product.pk})
        self.assertEqual(AccountProduct.objects.filter(account=self.account, product=self.product).count(), 1)
        reactivate_url = reverse('accounts:account_product_archive', args=[ap.pk])
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertFalse(any(reactivate_url in m for m in msgs))
