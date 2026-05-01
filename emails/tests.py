from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import Activity
from emails.forms import AssignEmailForm
from emails.management.commands.fetch_emails import Command as FetchEmailsCommand
from emails.models import InboundEmail, UserEmailAddress, UserInboundAddress
from core.test_helpers import CRMTestCase


# ---------------------------------------------------------------------------
# Email Parsing Tests
# ---------------------------------------------------------------------------

class EmailParsingTest(TestCase):

    def setUp(self):
        self.cmd = FetchEmailsCommand()

    def _make_raw(self, headers, body='Test'):
        raw = ''.join(f'{k}: {v}\r\n' for k, v in headers.items())
        raw += f'\r\n{body}'
        return raw.encode()

    def test_quoted_display_name_with_comma(self):
        """'Mustermann, Anna' <a.mustermann@example-kreis.de> must not be split into garbage."""
        raw = self._make_raw({
            'Message-ID': '<test1@example.com>',
            'From': 'sender@example.com',
            'To': '"Mustermann, Anna" <a.mustermann@example-kreis.de>',
            'Subject': 'Test',
            'Date': 'Mon, 1 Jan 2024 10:00:00 +0000',
        })
        parsed = self.cmd._parse_email(raw)
        self.assertIn('a.mustermann@example-kreis.de', parsed['all_recipients'])
        self.assertNotIn('mustermann', parsed['all_recipients'])
        self.assertNotIn('anna', parsed['all_recipients'])

    def test_multiple_recipients_with_quoted_comma_name(self):
        """Multiple recipients including a quoted-comma display name are all parsed correctly."""
        raw = self._make_raw({
            'Message-ID': '<test2@example.com>',
            'From': 'sender@example.com',
            'To': '"Mustermann, Anna" <a.mustermann@example-kreis.de>, b.schmidt@example-org.de',
            'Subject': 'Test',
            'Date': 'Mon, 1 Jan 2024 10:00:00 +0000',
        })
        parsed = self.cmd._parse_email(raw)
        self.assertIn('a.mustermann@example-kreis.de', parsed['all_recipients'])
        self.assertIn('b.schmidt@example-org.de', parsed['all_recipients'])
        self.assertEqual(len(parsed['all_recipients']), 2)


# ---------------------------------------------------------------------------
# _match_user Tests
# ---------------------------------------------------------------------------

@override_settings(INBOUND_EMAIL_DOMAIN='mail.example.com')
class MatchUserTest(CRMTestCase):

    def setUp(self):
        self.cmd = FetchEmailsCommand()
        self.user = self.create_verwalter()
        self.inbound_addr = UserInboundAddress.objects.create(user=self.user)
        UserEmailAddress.objects.create(user=self.user, email='user@example.com')

    def test_token_match_with_registered_sender(self):
        """Token-Match + registrierter Absender → User wird erkannt."""
        recipients = [self.inbound_addr.address.lower()]
        result = self.cmd._match_user(recipients, 'user@example.com')
        self.assertEqual(result, self.user)

    def test_token_match_with_unregistered_sender_rejected(self):
        """Token-Match, aber Absender nicht in 'Meine E-Mail-Adressen' → abgelehnt."""
        recipients = [self.inbound_addr.address.lower()]
        result = self.cmd._match_user(recipients, 'unknown@external.com')
        self.assertIsNone(result)

    def test_sender_fallback_match(self):
        """Kein Token in Empfänger, aber Absender registriert → User wird erkannt."""
        recipients = ['someone@example.com']
        result = self.cmd._match_user(recipients, 'user@example.com')
        self.assertEqual(result, self.user)

    def test_no_match_returns_none(self):
        """Weder Token noch registrierter Absender → None."""
        recipients = ['nobody@example.com']
        result = self.cmd._match_user(recipients, 'stranger@external.com')
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Phase 1: Model Tests
# ---------------------------------------------------------------------------

@override_settings(INBOUND_EMAIL_DOMAIN='mail.example.com')
class UserInboundAddressModelTest(CRMTestCase):

    def test_address_format(self):
        user = self.create_verwalter()
        addr = UserInboundAddress.objects.create(user=user)
        self.assertEqual(addr.address, f'crm+{addr.token}@mail.example.com')

    def test_str(self):
        user = self.create_verwalter()
        addr = UserInboundAddress.objects.create(user=user)
        self.assertEqual(str(addr), addr.address)


class InboundEmailModelTest(CRMTestCase):

    def test_str_with_subject(self):
        user = self.create_verwalter()
        email = InboundEmail.objects.create(
            user=user, message_id='<abc@example.com>',
            sender_email='test@test.de', subject='Wichtig',
            received_at=timezone.now(),
        )
        self.assertEqual(str(email), 'Wichtig')

    def test_str_fallback_message_id(self):
        user = self.create_verwalter()
        email = InboundEmail.objects.create(
            user=user, message_id='<xyz@example.com>',
            sender_email='test@test.de', subject='',
            received_at=timezone.now(),
        )
        self.assertEqual(str(email), '<xyz@example.com>')


# ---------------------------------------------------------------------------
# Phase 2: Form Tests
# ---------------------------------------------------------------------------

class AssignEmailFormTest(CRMTestCase):

    def test_superuser_sees_all_accounts(self):
        su = self.create_superuser()
        vw = self.create_verwalter()
        acc1 = self.create_account(name='Acc1', owner=su)
        acc2 = self.create_account(name='Acc2', owner=vw)
        form = AssignEmailForm(user=su)
        qs = form.fields['account'].queryset
        self.assertIn(acc1, qs)
        self.assertIn(acc2, qs)

    def test_verwalter_sees_only_own(self):
        su = self.create_superuser()
        vw = self.create_verwalter()
        acc_own = self.create_account(name='Eigener', owner=vw)
        acc_other = self.create_account(name='Anderer', owner=su)
        form = AssignEmailForm(user=vw)
        qs = form.fields['account'].queryset
        self.assertIn(acc_own, qs)
        self.assertNotIn(acc_other, qs)


# ---------------------------------------------------------------------------
# Phase 3: View Tests
# ---------------------------------------------------------------------------

class ProfileViewTest(CRMTestCase):

    def setUp(self):
        self.user = self.create_verwalter()
        self.client.login(username='verwalter', password='testpass123')

    def test_creates_inbound_address(self):
        response = self.client.get('/profil/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(UserInboundAddress.objects.filter(user=self.user).exists())

    def test_set_default_product(self):
        from products.models import Product
        product = Product.objects.create(name='TestProdukt')
        self.client.post('/profil/set-default-product/', {'default_product': product.pk})
        self.user.refresh_from_db()
        self.assertEqual(self.user.default_dashboard_product, product)

    def test_email_address_add(self):
        self.client.post('/profil/email-adressen/add/', {'email': 'neue@adresse.de'})
        self.assertTrue(UserEmailAddress.objects.filter(user=self.user, email='neue@adresse.de').exists())


class AssignEmailViewTest(CRMTestCase):

    def setUp(self):
        self.user = self.create_verwalter()
        self.client.login(username='verwalter', password='testpass123')
        self.account = self.create_account(owner=self.user)
        self.email_obj = InboundEmail.objects.create(
            user=self.user, message_id='<test@test.de>',
            sender_email='sender@test.de', subject='Test Betreff',
            received_at=timezone.now(),
        )

    def test_assign_creates_activity(self):
        self.client.post(
            f'/profil/emails/{self.email_obj.pk}/assign/',
            {'account': self.account.pk},
        )
        self.email_obj.refresh_from_db()
        self.assertEqual(self.email_obj.status, 'resolved')
        self.assertTrue(Activity.objects.filter(
            account=self.account, inbound_email=self.email_obj,
        ).exists())

    def test_unresolved_list(self):
        response = self.client.get('/profil/emails/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['email_list']), 1)
