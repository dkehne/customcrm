from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from contracts.forms import ContractForm
from contracts.models import Contract, ContractType
from core.test_helpers import CRMTestCase


# ---------------------------------------------------------------------------
# Phase 1: Model Tests
# ---------------------------------------------------------------------------

class ContractModelTest(CRMTestCase):

    def setUp(self):
        self.account = self.create_account()

    def test_initial_end_date(self):
        contract = self.create_contract(self.account, start_date=date(2024, 1, 1), duration_months=12)
        self.assertEqual(contract.initial_end_date(), date(2024, 12, 31))

    def test_initial_end_date_short(self):
        contract = self.create_contract(self.account, start_date=date(2024, 1, 15), duration_months=3)
        self.assertEqual(contract.initial_end_date(), date(2024, 4, 14))

    def test_current_end_date_self_cancelling(self):
        contract = self.create_contract(
            self.account, start_date=date(2020, 1, 1),
            duration_months=12, is_self_cancelling=True,
            renewal_interval_months=12,
        )
        self.assertEqual(contract.current_end_date(), date(2020, 12, 31))

    def test_current_end_date_no_renewal_interval(self):
        contract = self.create_contract(
            self.account, start_date=date(2020, 1, 1),
            duration_months=12, is_self_cancelling=False,
            renewal_interval_months=None,
        )
        self.assertEqual(contract.current_end_date(), date(2020, 12, 31))

    def test_current_end_date_auto_renews_past_today(self):
        contract = self.create_contract(
            self.account, start_date=date(2020, 1, 1),
            duration_months=12, renewal_interval_months=12,
        )
        self.assertGreater(contract.current_end_date(), date.today())

    def test_current_end_date_not_yet_expired(self):
        future = date.today() + timedelta(days=365 * 5)
        contract = self.create_contract(
            self.account, start_date=future,
            duration_months=12, renewal_interval_months=12,
        )
        from dateutil.relativedelta import relativedelta
        expected = future + relativedelta(months=12) - timedelta(days=1)
        self.assertEqual(contract.current_end_date(), expected)

    def test_current_end_date_multiple_renewals(self):
        contract = self.create_contract(
            self.account, start_date=date(2020, 1, 1),
            duration_months=6, renewal_interval_months=6,
        )
        end = contract.current_end_date()
        self.assertGreater(end, date.today())
        # End should be at most 6 months from today
        from dateutil.relativedelta import relativedelta
        self.assertLessEqual(end, date.today() + relativedelta(months=6))

    def test_current_end_date_notice_period_expired(self):
        # Kündigungsfrist für die aktuelle Verlängerungsperiode schon verstrichen
        # → nächste Verlängerung ist bereits fix
        # Wir konstruieren einen Vertrag dessen aktuelle Periode in 2 Monaten endet
        # (Kündigungsfrist 3 Monate → Deadline war vor 1 Monat → bereits verstrichen)
        from dateutil.relativedelta import relativedelta as rd
        current_end = date.today() + rd(months=2)
        start = current_end - rd(months=24) + timedelta(days=1)
        contract = self.create_contract(
            self.account, start_date=start,
            duration_months=24, renewal_interval_months=24,
            notice_period_months=3,
        )
        self.assertEqual(contract.current_end_date(), current_end + rd(months=24))

    def test_current_end_date_notice_period_not_yet_expired(self):
        # Kündigungsfrist noch nicht verstrichen → aktuelles Enddatum bleibt
        # Start weit in der Zukunft, sodass das erste Enddatum noch gilt
        from dateutil.relativedelta import relativedelta as rd
        future_start = date.today() + rd(months=13)
        contract = self.create_contract(
            self.account, start_date=future_start,
            duration_months=12, renewal_interval_months=12,
            notice_period_months=3,
        )
        expected = future_start + rd(months=12) - timedelta(days=1)
        self.assertEqual(contract.current_end_date(), expected)

    def test_str_representation(self):
        contract = self.create_contract(self.account)
        expected = f'Vertrag {contract.pk} \u2013 {self.account.name}'
        self.assertEqual(str(contract), expected)


# ---------------------------------------------------------------------------
# Phase 2: Form Tests
# ---------------------------------------------------------------------------

class ContractFormTest(CRMTestCase):

    def test_archived_contract_types_excluded(self):
        active = self.create_contract_type(name='Aktiv')
        self.create_contract_type(name='Archiviert', is_archived=True)
        form = ContractForm()
        qs = form.fields['contract_type'].queryset
        self.assertIn(active, qs)
        self.assertEqual(qs.count(), 1)

    def test_account_products_filtered_by_account(self):
        product = self.create_product()
        account = self.create_account()
        other_account = self.create_account(name='Andere')
        ap_own = self.create_account_product(account, product)
        ap_other = self.create_account_product(other_account, product)
        form = ContractForm(account=account)
        qs = form.fields['account_product'].queryset
        self.assertIn(ap_own, qs)
        self.assertNotIn(ap_other, qs)


# ---------------------------------------------------------------------------
# Phase 3: View Tests
# ---------------------------------------------------------------------------

class ContractListViewTest(CRMTestCase):

    def test_login_required(self):
        response = self.client.get('/contracts/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_lists_contracts(self):
        self.create_superuser()
        self.client.login(username='admin', password='testpass123')
        account = self.create_account()
        self.create_contract(account)
        response = self.client.get('/contracts/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['contracts']), 1)

    def test_search_by_account_name(self):
        self.create_superuser()
        self.client.login(username='admin', password='testpass123')
        acc1 = self.create_account(name='Muenchen')
        acc2 = self.create_account(name='Berlin')
        self.create_contract(acc1)
        self.create_contract(acc2)
        response = self.client.get('/contracts/?q=Muenchen')
        self.assertEqual(len(response.context['contracts']), 1)
