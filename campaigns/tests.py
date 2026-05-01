from datetime import date, timedelta

from django.test import TestCase

from campaigns.forms import CampaignForm
from campaigns.models import AccountCampaign, Campaign, CampaignContact
from core.test_helpers import CRMTestCase


# ---------------------------------------------------------------------------
# Phase 1: Model Tests
# ---------------------------------------------------------------------------

class AccountCampaignModelTest(CRMTestCase):

    def setUp(self):
        self.account = self.create_account()
        self.campaign = self.create_campaign()

    def test_is_external_true(self):
        ac = AccountCampaign.objects.create(account=self.account, campaign=None, name='Extern')
        self.assertTrue(ac.is_external)

    def test_is_external_false(self):
        ac = AccountCampaign.objects.create(account=self.account, campaign=self.campaign)
        self.assertFalse(ac.is_external)

    def test_display_name_external(self):
        ac = AccountCampaign.objects.create(account=self.account, campaign=None, name='Mein Name')
        self.assertEqual(ac.display_name, 'Mein Name')

    def test_display_name_linked(self):
        ac = AccountCampaign.objects.create(account=self.account, campaign=self.campaign)
        self.assertEqual(ac.display_name, self.campaign.name)

    def test_display_start_date_external(self):
        ac = AccountCampaign.objects.create(
            account=self.account, campaign=None, name='E',
            start_date=date(2025, 3, 1),
        )
        self.assertEqual(ac.display_start_date, date(2025, 3, 1))

    def test_display_end_date_linked(self):
        ac = AccountCampaign.objects.create(account=self.account, campaign=self.campaign)
        self.assertEqual(ac.display_end_date, self.campaign.end_date)


class CampaignContactModelTest(CRMTestCase):

    def test_str_representation(self):
        campaign = self.create_campaign()
        account = self.create_account()
        contact = self.create_contact(account)
        cc = CampaignContact.objects.create(
            campaign=campaign, contact=contact, account=account,
            contact_name=contact.name, contact_email=contact.email,
            contact_phone=contact.phone, account_name=account.name,
            bundesland=account.bundesland,
        )
        self.assertEqual(str(cc), f'{contact.name} ({account.name})')

    def test_snapshot_independence(self):
        campaign = self.create_campaign()
        account = self.create_account()
        contact = self.create_contact(account, name='Vorher')
        cc = CampaignContact.objects.create(
            campaign=campaign, contact=contact, account=account,
            contact_name='Vorher', contact_email=contact.email,
            contact_phone='', account_name=account.name,
            bundesland=account.bundesland,
        )
        contact.name = 'Nachher'
        contact.save()
        cc.refresh_from_db()
        self.assertEqual(cc.contact_name, 'Vorher')


# ---------------------------------------------------------------------------
# Phase 2: Form Tests
# ---------------------------------------------------------------------------

class CampaignFormTest(TestCase):

    def test_valid_data(self):
        form = CampaignForm(data={
            'name': 'Testkampagne',
            'start_date': '2025-01-01',
            'end_date': '2025-03-31',
        })
        self.assertTrue(form.is_valid())


# ---------------------------------------------------------------------------
# Phase 3: View Tests
# ---------------------------------------------------------------------------

class CampaignAccessControlTest(CRMTestCase):

    def test_superuser_can_create(self):
        self.create_superuser()
        self.client.login(username='admin', password='testpass123')
        response = self.client.post('/campaigns/create/', {
            'name': 'Neue Kampagne',
            'start_date': '2025-01-01',
            'end_date': '2025-06-30',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Campaign.objects.filter(name='Neue Kampagne').exists())



class CampaignSnapshotTest(CRMTestCase):

    def setUp(self):
        self.user = self.create_superuser()
        self.client.login(username='admin', password='testpass123')
        self.campaign = self.create_campaign(created_by=self.user)
        self.account = self.create_account()
        self.contact = self.create_contact(self.account, is_primary=True)

    def test_add_accounts_creates_snapshots(self):
        response = self.client.post(
            f'/campaigns/{self.campaign.pk}/add-accounts/',
            {'accounts': [str(self.account.pk)]},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CampaignContact.objects.count(), 1)
        cc = CampaignContact.objects.first()
        self.assertEqual(cc.contact_name, self.contact.name)
        self.assertEqual(cc.account_name, self.account.name)

    def test_no_duplicate_snapshots(self):
        self.client.post(
            f'/campaigns/{self.campaign.pk}/add-accounts/',
            {'accounts': [str(self.account.pk)]},
        )
        self.client.post(
            f'/campaigns/{self.campaign.pk}/add-accounts/',
            {'accounts': [str(self.account.pk)]},
        )
        self.assertEqual(CampaignContact.objects.count(), 1)


class CampaignCSVExportTest(CRMTestCase):

    def setUp(self):
        self.user = self.create_superuser()
        self.client.login(username='admin', password='testpass123')

    def test_utf8_sig_encoding(self):
        response = self.client.get('/campaigns/?export=csv')
        self.assertEqual(response.charset, 'utf-8-sig')

    def test_semicolon_delimiter(self):
        account = self.create_account(name='Teststadt')
        self.create_contact(account, is_primary=True)
        response = self.client.get('/campaigns/?export=csv')
        content = response.content.decode('utf-8-sig')
        self.assertIn(';', content)

    def test_campaign_detail_csv_export(self):
        campaign = self.create_campaign(created_by=self.user)
        account = self.create_account()
        contact = self.create_contact(account, is_primary=True)
        CampaignContact.objects.create(
            campaign=campaign, contact=contact, account=account,
            contact_name=contact.name, contact_email=contact.email,
            contact_phone=contact.phone, account_name=account.name,
            bundesland=account.bundesland,
        )
        response = self.client.get(f'/campaigns/{campaign.pk}/?export=csv')
        self.assertEqual(response['Content-Type'], 'text/csv')
        content = response.content.decode('utf-8-sig')
        self.assertIn(contact.name, content)


class CampaignRemoveContactTest(CRMTestCase):

    def setUp(self):
        self.user = self.create_superuser()
        self.client.login(username='admin', password='testpass123')
        self.account = self.create_account()
        self.contact = self.create_contact(self.account, is_primary=True)

    def test_remove_before_end_date_allowed(self):
        campaign = self.create_campaign(
            end_date=date.today() + timedelta(days=30),
            created_by=self.user,
        )
        cc = CampaignContact.objects.create(
            campaign=campaign, contact=self.contact, account=self.account,
            contact_name=self.contact.name, contact_email='', contact_phone='',
            account_name=self.account.name, bundesland='',
        )
        response = self.client.post(f'/campaigns/{campaign.pk}/remove-contact/{cc.pk}/')
        self.assertEqual(response.status_code, 302)
        self.assertFalse(CampaignContact.objects.filter(pk=cc.pk).exists())

    def test_remove_after_end_date_blocked(self):
        campaign = self.create_campaign(
            end_date=date.today() - timedelta(days=1),
            created_by=self.user,
        )
        cc = CampaignContact.objects.create(
            campaign=campaign, contact=self.contact, account=self.account,
            contact_name=self.contact.name, contact_email='', contact_phone='',
            account_name=self.account.name, bundesland='',
        )
        response = self.client.post(f'/campaigns/{campaign.pk}/remove-contact/{cc.pk}/')
        self.assertTrue(CampaignContact.objects.filter(pk=cc.pk).exists())
