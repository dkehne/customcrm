from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone


class AccountType(models.Model):
    name = models.CharField(max_length=200, verbose_name='Name')
    is_archived = models.BooleanField(default=False, verbose_name='Archiviert')

    class Meta:
        verbose_name = 'Account-Typ'
        verbose_name_plural = 'Account-Typen'
        ordering = ['name']

    def __str__(self):
        return self.name


class Account(models.Model):
    name = models.CharField(max_length=300, verbose_name='Name')
    auto_id = models.AutoField(primary_key=True)
    account_type = models.ForeignKey(
        AccountType, on_delete=models.PROTECT, verbose_name='Account-Typ',
        null=True, blank=True,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='Besitzer',
        related_name='owned_accounts',
    )
    notes = models.TextField(blank=True, default='', verbose_name='Notizen')
    is_archived = models.BooleanField(default=False, verbose_name='Archiviert')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Account'
        verbose_name_plural = 'Accounts'
        ordering = ['name']

    def __str__(self):
        return self.name


class Contact(models.Model):
    GENDER_CHOICES = [
        ('m', 'Männlich'),
        ('w', 'Weiblich'),
        ('d', 'Divers'),
    ]

    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name='contacts',
        verbose_name='Account',
    )
    name = models.CharField(max_length=300, verbose_name='Name')
    email = models.EmailField(blank=True, verbose_name='E-Mail')
    phone = models.CharField(max_length=50, blank=True, verbose_name='Telefon')
    gender = models.CharField(
        max_length=1, choices=GENDER_CHOICES, blank=True, verbose_name='Geschlecht',
    )
    position = models.CharField(max_length=200, blank=True, verbose_name='Position')
    anrede = models.CharField(max_length=200, blank=True, default='', verbose_name='Anrede')
    is_primary = models.BooleanField(default=False, verbose_name='Hauptansprechperson')
    is_archived = models.BooleanField(default=False, verbose_name='Archiviert')

    class Meta:
        verbose_name = 'Kontakt'
        verbose_name_plural = 'Kontakte'
        ordering = ['-is_primary', 'name']

    def __str__(self):
        return self.name


class Activity(models.Model):
    ACTIVITY_TYPES = [
        ('call', 'Telefonanruf'),
        ('email', 'E-Mail'),
        ('meeting', 'Termin'),
        ('task', 'Aufgabe'),
    ]

    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name='activities',
        verbose_name='Account',
    )
    activity_type = models.CharField(
        max_length=10, choices=ACTIVITY_TYPES, verbose_name='Typ',
    )
    subject = models.CharField(max_length=300, verbose_name='Betreff')
    description = models.TextField(blank=True, verbose_name='Beschreibung')
    date = models.DateTimeField(verbose_name='Datum')
    contact = models.ForeignKey(
        Contact, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Kontakt',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        verbose_name='Erstellt von',
    )
    inbound_email = models.OneToOneField(
        'emails.InboundEmail', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='activity',
        verbose_name='Eingehende E-Mail',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Aktivität'
        verbose_name_plural = 'Aktivitäten'
        ordering = ['-date']

    def __str__(self):
        return self.subject


class Todo(models.Model):
    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name='todos',
        verbose_name='Account',
    )
    title = models.CharField(max_length=300, verbose_name='Titel')
    description = models.TextField(blank=True, default='', verbose_name='Beschreibung')
    due_date = models.DateField(null=True, blank=True, verbose_name='Fälligkeitsdatum')
    attachment = models.FileField(
        upload_to='todo_attachments/%Y/%m/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])],
        null=True, blank=True, verbose_name='PDF-Anhang',
    )
    is_completed = models.BooleanField(default=False, verbose_name='Erledigt')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Erledigt am')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        verbose_name='Erstellt von',
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_todos', verbose_name='Zugewiesen an',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Aufgabe'
        verbose_name_plural = 'Aufgaben'
        ordering = ['due_date', 'created_at']

    def __str__(self):
        return self.title


