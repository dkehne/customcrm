from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from accounts.models import Account, AccountType, Contact
from campaigns.models import Campaign
from contracts.models import Contract, ContractType
from core.models import CustomUser
from products.models import (
    AccountProduct,
    Product,
    ProductField,
    ProductPhase,
)


class CRMTestCase(TestCase):
    """Base test class with factory methods for all CRM models."""

    def create_superuser(self, username='admin', password='testpass123', **kwargs):
        defaults = {
            'first_name': 'Admin',
            'last_name': 'Benutzer',
            'role': CustomUser.Role.SUPERUSER,
        }
        defaults.update(kwargs)
        user = CustomUser.objects.create_user(username=username, password=password, **defaults)
        # save() syncs role -> is_superuser, but create_user may not call our save
        user.role = defaults['role']
        user.save()
        return user

    def create_verwalter(self, username='verwalter', password='testpass123', **kwargs):
        defaults = {
            'first_name': 'Max',
            'last_name': 'Mustermann',
            'role': CustomUser.Role.VERWALTER,
        }
        defaults.update(kwargs)
        user = CustomUser.objects.create_user(username=username, password=password, **defaults)
        user.role = defaults['role']
        user.save()
        return user

    def create_account_type(self, name='Landkreis', **kwargs):
        defaults = {'is_archived': False}
        defaults.update(kwargs)
        return AccountType.objects.create(name=name, **defaults)

    def create_account(self, name='Teststadt', owner=None, **kwargs):
        defaults = {
            'is_archived': False,
        }
        defaults.update(kwargs)
        return Account.objects.create(name=name, owner=owner, **defaults)

    def create_contact(self, account, name='Max Mustermann', **kwargs):
        defaults = {
            'email': 'max@teststadt.de',
            'phone': '+49 123 456789',
            'is_primary': False,
            'is_archived': False,
        }
        defaults.update(kwargs)
        return Contact.objects.create(account=account, name=name, **defaults)

    def create_product(self, name='Integreat', **kwargs):
        defaults = {'is_archived': False}
        defaults.update(kwargs)
        return Product.objects.create(name=name, **defaults)

    def create_phase(self, product, name='Erstgespraech', order=0, **kwargs):
        return ProductPhase.objects.create(product=product, name=name, order=order, **kwargs)

    def create_product_field(self, product, name='Go-Live', field_type='date', **kwargs):
        defaults = {'is_archived': False, 'show_on_dashboard': True}
        defaults.update(kwargs)
        return ProductField.objects.create(
            product=product, name=name, field_type=field_type, **defaults,
        )

    def create_account_product(self, account, product, phase=None, **kwargs):
        defaults = {'is_archived': False}
        defaults.update(kwargs)
        return AccountProduct.objects.create(
            account=account, product=product, current_phase=phase, **defaults,
        )

    def create_contract_type(self, name='SLA', **kwargs):
        defaults = {'is_archived': False}
        defaults.update(kwargs)
        return ContractType.objects.create(name=name, **defaults)

    def create_contract(self, account, start_date=None, **kwargs):
        defaults = {
            'gross_annual_price': Decimal('1200.00'),
            'duration_months': 12,
            'is_self_cancelling': False,
            'renewal_interval_months': 12,
            'notice_period_months': 3,
            'is_archived': False,
        }
        defaults.update(kwargs)
        if start_date is None:
            start_date = date.today() - timedelta(days=365)
        return Contract.objects.create(account=account, start_date=start_date, **defaults)

    def create_campaign(self, name='Fruehjahrs-Kampagne', **kwargs):
        defaults = {
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=30),
            'is_archived': False,
        }
        defaults.update(kwargs)
        return Campaign.objects.create(name=name, **defaults)
