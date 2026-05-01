from django.core.cache import cache
from django.test import TestCase

from core.models import CustomUser, SiteSettings
from core.forms import UserCreateForm, UserEditForm
from core.test_helpers import CRMTestCase


# ---------------------------------------------------------------------------
# Phase 1: Model Tests
# ---------------------------------------------------------------------------

class SiteSettingsModelTest(TestCase):

    def tearDown(self):
        cache.clear()

    def test_singleton_forced_pk_1(self):
        s = SiteSettings(site_name='Test')
        s.save()
        self.assertEqual(s.pk, 1)

    def test_second_save_overwrites(self):
        SiteSettings.objects.create(pk=1, site_name='First')
        s2 = SiteSettings(site_name='Second')
        s2.save()
        self.assertEqual(SiteSettings.objects.count(), 1)
        self.assertEqual(SiteSettings.objects.get(pk=1).site_name, 'Second')

    def test_save_clears_cache(self):
        cache.set('site_settings', 'stale')
        SiteSettings(site_name='New').save()
        self.assertIsNone(cache.get('site_settings'))

    def test_get_settings_creates_default(self):
        self.assertEqual(SiteSettings.objects.count(), 0)
        settings = SiteSettings.get_settings()
        self.assertEqual(settings.pk, 1)
        self.assertEqual(settings.site_name, 'CustomCRM')

    def test_get_settings_caches(self):
        SiteSettings.get_settings()  # populate cache
        with self.assertNumQueries(0):
            SiteSettings.get_settings()

    def test_str_representation(self):
        s = SiteSettings()
        self.assertEqual(str(s), 'Systemeinstellungen')


class CustomUserModelTest(TestCase):

    def test_superuser_role_sets_is_superuser(self):
        user = CustomUser(username='su', role=CustomUser.Role.SUPERUSER)
        user.save()
        self.assertTrue(user.is_superuser)

    def test_verwalter_clears_is_superuser(self):
        user = CustomUser(username='vw', role=CustomUser.Role.VERWALTER)
        user.save()
        self.assertFalse(user.is_superuser)

    def test_role_change_updates_is_superuser(self):
        user = CustomUser.objects.create(username='flip', role=CustomUser.Role.SUPERUSER)
        self.assertTrue(user.is_superuser)
        user.role = CustomUser.Role.VERWALTER
        user.save()
        self.assertFalse(user.is_superuser)

    def test_str_full_name(self):
        user = CustomUser(username='jd', first_name='Jane', last_name='Doe')
        self.assertEqual(str(user), 'Jane Doe')

    def test_str_fallback_username(self):
        user = CustomUser(username='jd')
        self.assertEqual(str(user), 'jd')


class ToggleArchiveTest(CRMTestCase):

    def test_toggle_archives_and_restores(self):
        self.create_superuser()
        self.client.login(username='admin', password='testpass123')
        account = self.create_account()
        self.assertFalse(account.is_archived)
        self.client.get(f'/accounts/{account.pk}/archive/')
        account.refresh_from_db()
        self.assertTrue(account.is_archived)
        self.client.get(f'/accounts/{account.pk}/archive/')
        account.refresh_from_db()
        self.assertFalse(account.is_archived)

    def test_archive_message(self):
        self.create_superuser()
        self.client.login(username='admin', password='testpass123')
        account = self.create_account(name='Musterstadt')
        response = self.client.get(f'/accounts/{account.pk}/archive/', follow=True)
        self.assertContains(response, 'archiviert')


class ConfirmDeleteTest(CRMTestCase):

    def setUp(self):
        self.user = self.create_superuser()
        self.client.login(username='admin', password='testpass123')
        self.account = self.create_account()

    def test_get_request_rejected(self):
        self.account.is_archived = True
        self.account.save()
        response = self.client.get(f'/accounts/{self.account.pk}/delete/', follow=True)
        self.assertContains(response, 'nicht erlaubt')

    def test_non_archived_rejected(self):
        response = self.client.post(
            f'/accounts/{self.account.pk}/delete/',
            {'confirm_username': 'admin'},
            follow=True,
        )
        self.assertContains(response, 'nicht erlaubt')

    def test_wrong_username_rejected(self):
        self.account.is_archived = True
        self.account.save()
        response = self.client.post(
            f'/accounts/{self.account.pk}/delete/',
            {'confirm_username': 'wrong'},
            follow=True,
        )
        self.assertContains(response, 'stimmt nicht')

    def test_successful_delete(self):
        from accounts.models import Account
        self.account.is_archived = True
        self.account.save()
        self.client.post(
            f'/accounts/{self.account.pk}/delete/',
            {'confirm_username': 'admin'},
        )
        self.assertFalse(Account.objects.filter(pk=self.account.pk).exists())


# ---------------------------------------------------------------------------
# Phase 2: Form Tests
# ---------------------------------------------------------------------------

class UserCreateFormTest(TestCase):

    def test_valid_data_creates_user(self):
        form = UserCreateForm(data={
            'username': 'newuser',
            'first_name': 'Neuer',
            'last_name': 'Nutzer',
            'role': CustomUser.Role.VERWALTER,
            'password': 'sicheres_pw_123',
        })
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.username, 'newuser')

    def test_password_is_hashed(self):
        form = UserCreateForm(data={
            'username': 'hashtest',
            'first_name': 'A',
            'last_name': 'B',
            'role': CustomUser.Role.VERWALTER,
            'password': 'klartext',
        })
        user = form.save()
        self.assertTrue(user.check_password('klartext'))
        self.assertNotEqual(user.password, 'klartext')

    def test_required_fields(self):
        form = UserCreateForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)
        self.assertIn('password', form.errors)


class UserEditFormTest(TestCase):

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='edit_me', password='old_pass',
            first_name='Alt', last_name='Name', role=CustomUser.Role.VERWALTER,
        )

    def test_empty_password_keeps_old(self):
        form = UserEditForm(data={
            'username': 'edit_me',
            'first_name': 'Neu',
            'last_name': 'Name',
            'role': CustomUser.Role.VERWALTER,
            'is_active': True,
            'password': '',
        }, instance=self.user)
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertTrue(user.check_password('old_pass'))

    def test_new_password_is_set(self):
        form = UserEditForm(data={
            'username': 'edit_me',
            'first_name': 'Neu',
            'last_name': 'Name',
            'role': CustomUser.Role.VERWALTER,
            'is_active': True,
            'password': 'new_pass',
        }, instance=self.user)
        user = form.save()
        self.assertTrue(user.check_password('new_pass'))
        self.assertFalse(user.check_password('old_pass'))

    def test_role_change(self):
        form = UserEditForm(data={
            'username': 'edit_me',
            'first_name': 'A',
            'last_name': 'B',
            'role': CustomUser.Role.SUPERUSER,
            'is_active': True,
            'password': '',
        }, instance=self.user)
        user = form.save()
        self.assertEqual(user.role, CustomUser.Role.SUPERUSER)
        self.assertTrue(user.is_superuser)


# ---------------------------------------------------------------------------
# Phase 3: View Tests
# ---------------------------------------------------------------------------

class LoginViewTest(CRMTestCase):

    def test_get_shows_form(self):
        response = self.client.get('/login/')
        self.assertEqual(response.status_code, 200)

    def test_valid_login_redirects(self):
        self.create_superuser()
        response = self.client.post('/login/', {
            'username': 'admin',
            'password': 'testpass123',
        })
        self.assertEqual(response.status_code, 302)

    def test_invalid_login_shows_error(self):
        response = self.client.post('/login/', {
            'username': 'nobody',
            'password': 'wrong',
        })
        self.assertEqual(response.status_code, 200)

    def test_authenticated_user_redirected(self):
        self.create_superuser()
        self.client.login(username='admin', password='testpass123')
        response = self.client.get('/login/')
        self.assertEqual(response.status_code, 302)


class DashboardViewTest(CRMTestCase):

    def test_login_required(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_superuser_template(self):
        self.create_superuser()
        self.client.login(username='admin', password='testpass123')
        response = self.client.get('/')
        self.assertTemplateUsed(response, 'core/dashboard_superuser.html')

    def test_verwalter_template(self):
        self.create_verwalter()
        self.client.login(username='verwalter', password='testpass123')
        response = self.client.get('/')
        self.assertTemplateUsed(response, 'core/dashboard_verwalter.html')


class TodoListViewTest(CRMTestCase):

    def test_shows_only_assigned_todos(self):
        from datetime import date
        from accounts.models import Todo
        owner = self.create_verwalter()
        other = self.create_verwalter(username='other')
        acc_own = self.create_account(name='Own', owner=owner)
        acc_other = self.create_account(name='Other', owner=other)
        Todo.objects.create(account=acc_own, title='Meine Aufgabe', due_date=date.today(), assigned_to=owner)
        Todo.objects.create(account=acc_other, title='Fremde Aufgabe', due_date=date.today(), assigned_to=other)
        self.client.login(username='verwalter', password='testpass123')
        response = self.client.get('/aufgaben/')
        self.assertContains(response, 'Meine Aufgabe')
        self.assertNotContains(response, 'Fremde Aufgabe')

    def test_splits_upcoming_and_other(self):
        from datetime import date, timedelta
        from accounts.models import Todo
        owner = self.create_verwalter()
        acc = self.create_account(owner=owner)
        Todo.objects.create(account=acc, title='Bald', due_date=date.today() + timedelta(days=3), assigned_to=owner)
        Todo.objects.create(account=acc, title='Spaeter', due_date=date.today() + timedelta(days=30), assigned_to=owner)
        self.client.login(username='verwalter', password='testpass123')
        response = self.client.get('/aufgaben/')
        self.assertIn('Bald', [t.title for t in response.context['upcoming_todos']])
        self.assertIn('Spaeter', [t.title for t in response.context['other_todos']])


class SettingsAccessTest(CRMTestCase):

    def test_superuser_can_access(self):
        self.create_superuser()
        self.client.login(username='admin', password='testpass123')
        response = self.client.get('/settings/users/')
        self.assertEqual(response.status_code, 200)

    def test_verwalter_denied(self):
        self.create_verwalter()
        self.client.login(username='verwalter', password='testpass123')
        response = self.client.get('/settings/users/')
        self.assertEqual(response.status_code, 302)

    def test_user_creation(self):
        self.create_superuser()
        self.client.login(username='admin', password='testpass123')
        response = self.client.post('/settings/users/create/', {
            'username': 'created_user',
            'first_name': 'Erster',
            'last_name': 'Nutzer',
            'role': CustomUser.Role.VERWALTER,
            'password': 'pw_123_sicher',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(CustomUser.objects.filter(username='created_user').exists())
