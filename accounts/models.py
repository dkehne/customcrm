from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class AccountType(models.Model):
    name = models.CharField(max_length=200, verbose_name=_('Name'))
    is_archived = models.BooleanField(default=False, verbose_name=_('Archiviert'))

    class Meta:
        verbose_name = _('Account-Typ')
        verbose_name_plural = _('Account-Typen')
        ordering = ['name']

    def __str__(self):
        return self.name


class Account(models.Model):
    name = models.CharField(max_length=300, verbose_name=_('Name'))
    auto_id = models.AutoField(primary_key=True)
    account_type = models.ForeignKey(
        AccountType, on_delete=models.PROTECT, verbose_name=_('Account-Typ'),
        null=True, blank=True,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('Besitzer'),
        related_name='owned_accounts',
    )
    notes = models.TextField(blank=True, default='', verbose_name=_('Notizen'))
    is_archived = models.BooleanField(default=False, verbose_name=_('Archiviert'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Account')
        verbose_name_plural = _('Accounts')
        ordering = ['name']

    def __str__(self):
        return self.name


class Contact(models.Model):
    GENDER_CHOICES = [
        ('m', _('Männlich')),
        ('w', _('Weiblich')),
        ('d', _('Divers')),
    ]

    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name='contacts',
        verbose_name=_('Account'),
    )
    name = models.CharField(max_length=300, verbose_name=_('Name'))
    email = models.EmailField(blank=True, verbose_name=_('E-Mail'))
    phone = models.CharField(max_length=50, blank=True, verbose_name=_('Telefon'))
    gender = models.CharField(
        max_length=1, choices=GENDER_CHOICES, blank=True, verbose_name=_('Geschlecht'),
    )
    position = models.CharField(max_length=200, blank=True, verbose_name=_('Position'))
    anrede = models.CharField(max_length=200, blank=True, default='', verbose_name=_('Anrede'))
    is_primary = models.BooleanField(default=False, verbose_name=_('Hauptansprechperson'))
    is_archived = models.BooleanField(default=False, verbose_name=_('Archiviert'))

    class Meta:
        verbose_name = _('Kontakt')
        verbose_name_plural = _('Kontakte')
        ordering = ['-is_primary', 'name']

    def __str__(self):
        return self.name


class Activity(models.Model):
    ACTIVITY_TYPES = [
        ('call', _('Telefonanruf')),
        ('email', _('E-Mail')),
        ('meeting', _('Termin')),
        ('task', _('Aufgabe')),
    ]

    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name='activities',
        verbose_name=_('Account'),
    )
    activity_type = models.CharField(
        max_length=10, choices=ACTIVITY_TYPES, verbose_name=_('Typ'),
    )
    subject = models.CharField(max_length=300, verbose_name=_('Betreff'))
    description = models.TextField(blank=True, verbose_name=_('Beschreibung'))
    date = models.DateTimeField(verbose_name=_('Datum'))
    contact = models.ForeignKey(
        Contact, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name=_('Kontakt'),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        verbose_name=_('Erstellt von'),
    )
    inbound_email = models.OneToOneField(
        'emails.InboundEmail', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='activity',
        verbose_name=_('Eingehende E-Mail'),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Aktivität')
        verbose_name_plural = _('Aktivitäten')
        ordering = ['-date']

    def __str__(self):
        return self.subject


class Todo(models.Model):
    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name='todos',
        verbose_name=_('Account'),
    )
    title = models.CharField(max_length=300, verbose_name=_('Titel'))
    description = models.TextField(blank=True, default='', verbose_name=_('Beschreibung'))
    due_date = models.DateField(null=True, blank=True, verbose_name=_('Fälligkeitsdatum'))
    attachment = models.FileField(
        upload_to='todo_attachments/%Y/%m/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])],
        null=True, blank=True, verbose_name=_('PDF-Anhang'),
    )
    is_completed = models.BooleanField(default=False, verbose_name=_('Erledigt'))
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Erledigt am'))
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        verbose_name=_('Erstellt von'),
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_todos', verbose_name=_('Zugewiesen an'),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Aufgabe')
        verbose_name_plural = _('Aufgaben')
        ordering = ['due_date', 'created_at']

    def __str__(self):
        return self.title


