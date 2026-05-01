from datetime import date, timedelta

from django.utils import timezone

from accounts.forms import AccountForm, ActivityForm
from accounts.models import Account, Contact, Todo
from core.test_helpers import CRMTestCase


# ---------------------------------------------------------------------------
# Phase 1: Model Tests
# ---------------------------------------------------------------------------

class AccountModelTest(CRMTestCase):

    def test_str(self):
        account = self.create_account(name='Musterstadt')
        self.assertEqual(str(account), 'Musterstadt')

    def test_ordering(self):
        self.create_account(name='Zebra')
        self.create_account(name='Apfel')
        names = list(Account.objects.values_list('name', flat=True))
        self.assertEqual(names, ['Apfel', 'Zebra'])


class ContactModelTest(CRMTestCase):

    def test_ordering_primary_first(self):
        account = self.create_account()
        c1 = self.create_contact(account, name='Zweitens', is_primary=False)
        c2 = self.create_contact(account, name='Erstens', is_primary=True, email='e@e.de')
        contacts = list(account.contacts.all())
        self.assertEqual(contacts[0], c2)

    def test_str(self):
        account = self.create_account()
        contact = self.create_contact(account, name='Erika Mustermann')
        self.assertEqual(str(contact), 'Erika Mustermann')


# ---------------------------------------------------------------------------
# Phase 2: Form Tests
# ---------------------------------------------------------------------------

class AccountFormTest(CRMTestCase):

    def test_archived_account_types_excluded(self):
        active = self.create_account_type(name='Aktiv')
        self.create_account_type(name='Archiviert', is_archived=True)
        form = AccountForm()
        qs = form.fields['account_type'].queryset
        self.assertIn(active, qs)
        self.assertEqual(qs.count(), 1)

    def test_bootstrap_classes_applied(self):
        form = AccountForm()
        self.assertIn('form-control', form.fields['name'].widget.attrs.get('class', ''))


class ActivityFormTest(CRMTestCase):

    def test_activity_type_excludes_task(self):
        form = ActivityForm()
        choices = [c[0] for c in form.fields['activity_type'].choices]
        self.assertNotIn('task', choices)
        self.assertIn('call', choices)

    def test_contacts_filtered_by_account(self):
        acc = self.create_account()
        other_acc = self.create_account(name='Andere')
        c_own = self.create_contact(acc, name='Own')
        c_other = self.create_contact(other_acc, name='Other', email='o@o.de')
        form = ActivityForm(account=acc)
        qs = form.fields['contact'].queryset
        self.assertIn(c_own, qs)
        self.assertNotIn(c_other, qs)

    def test_no_account_gives_empty_contacts(self):
        form = ActivityForm()
        self.assertEqual(form.fields['contact'].queryset.count(), 0)


# ---------------------------------------------------------------------------
# Phase 3: View Tests
# ---------------------------------------------------------------------------

class AccountListViewTest(CRMTestCase):

    def test_login_required(self):
        response = self.client.get('/accounts/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_superuser_sees_all(self):
        su = self.create_superuser()
        other = self.create_verwalter()
        self.create_account(name='Su-Account', owner=su)
        self.create_account(name='Other-Account', owner=other)
        self.client.login(username='admin', password='testpass123')
        response = self.client.get('/accounts/')
        self.assertEqual(len(response.context['accounts']), 2)

    def test_verwalter_sees_only_own(self):
        vw = self.create_verwalter()
        self.create_superuser()
        self.create_account(name='Own', owner=vw)
        self.create_account(name='Other', owner=None)
        self.client.login(username='verwalter', password='testpass123')
        response = self.client.get('/accounts/')
        self.assertEqual(len(response.context['accounts']), 1)
        self.assertEqual(response.context['accounts'][0].name, 'Own')

    def test_search_filter(self):
        self.create_superuser()
        self.client.login(username='admin', password='testpass123')
        self.create_account(name='Muenchen')
        self.create_account(name='Berlin')
        response = self.client.get('/accounts/?q=Muenchen&owner=')
        self.assertEqual(len(response.context['accounts']), 1)


class AccountCRUDViewTest(CRMTestCase):

    def setUp(self):
        self.user = self.create_superuser()
        self.client.login(username='admin', password='testpass123')

    def test_create(self):
        at = self.create_account_type()
        response = self.client.post('/accounts/create/', {
            'name': 'Neue Stadt',
            'account_type': at.pk,
            'notes': '',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Account.objects.filter(name='Neue Stadt').exists())

    def test_edit(self):
        account = self.create_account(name='Alt')
        response = self.client.post(f'/accounts/{account.pk}/edit/', {
            'name': 'Neu',
            'notes': '',
        })
        self.assertEqual(response.status_code, 302)
        account.refresh_from_db()
        self.assertEqual(account.name, 'Neu')

    def test_detail(self):
        account = self.create_account()
        response = self.client.get(f'/accounts/{account.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['account'], account)

    def test_archive(self):
        account = self.create_account()
        self.client.get(f'/accounts/{account.pk}/archive/')
        account.refresh_from_db()
        self.assertTrue(account.is_archived)

    def test_assign_owner(self):
        account = self.create_account(owner=None)
        self.client.get(f'/accounts/{account.pk}/assign/')
        account.refresh_from_db()
        self.assertEqual(account.owner, self.user)


class ContactViewTest(CRMTestCase):

    def setUp(self):
        self.user = self.create_superuser()
        self.client.login(username='admin', password='testpass123')
        self.account = self.create_account()

    def test_add(self):
        response = self.client.post(
            f'/accounts/{self.account.pk}/contacts/add/',
            {'name': 'Neuer Kontakt', 'email': 'n@k.de', 'phone': '', 'gender': '', 'position': '', 'is_primary': False},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Contact.objects.filter(name='Neuer Kontakt').exists())

    def test_edit(self):
        contact = self.create_contact(self.account, name='Alt')
        response = self.client.post(
            f'/accounts/contacts/{contact.pk}/edit/',
            {'name': 'Neu', 'email': '', 'phone': '', 'gender': '', 'position': '', 'is_primary': False},
        )
        self.assertEqual(response.status_code, 302)
        contact.refresh_from_db()
        self.assertEqual(contact.name, 'Neu')

    def test_archive(self):
        contact = self.create_contact(self.account)
        self.client.get(f'/accounts/contacts/{contact.pk}/archive/')
        contact.refresh_from_db()
        self.assertTrue(contact.is_archived)


class TodoViewTest(CRMTestCase):

    def setUp(self):
        self.user = self.create_superuser()
        self.client.login(username='admin', password='testpass123')
        self.account = self.create_account()

    def test_add(self):
        response = self.client.post(
            f'/accounts/{self.account.pk}/todos/add/',
            {'title': 'Neue Aufgabe', 'description': '', 'due_date': ''},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Todo.objects.filter(title='Neue Aufgabe').exists())

    def test_complete_sets_completed_at(self):
        todo = Todo.objects.create(account=self.account, title='Test')
        self.client.post(f'/accounts/todos/{todo.pk}/complete/')
        todo.refresh_from_db()
        self.assertTrue(todo.is_completed)
        self.assertIsNotNone(todo.completed_at)

    def test_delete_completed_todo(self):
        todo = Todo.objects.create(account=self.account, title='Delete me')
        # confirm_delete requires is_archived=True; Todo has no is_archived,
        # but confirm_delete falls back to getattr(obj, 'is_archived', True)
        # which defaults to True when attr is missing, so POST + username works.
        self.client.post(
            f'/accounts/todos/{todo.pk}/delete/',
            {'confirm_username': 'admin'},
        )
        self.assertFalse(Todo.objects.filter(pk=todo.pk).exists())
