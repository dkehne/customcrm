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
    BUNDESLAND_CHOICES = [
        ('BW', 'Baden-Württemberg'),
        ('BY', 'Bayern'),
        ('BE', 'Berlin'),
        ('BB', 'Brandenburg'),
        ('HB', 'Bremen'),
        ('HH', 'Hamburg'),
        ('HE', 'Hessen'),
        ('MV', 'Mecklenburg-Vorpommern'),
        ('NI', 'Niedersachsen'),
        ('NW', 'Nordrhein-Westfalen'),
        ('RP', 'Rheinland-Pfalz'),
        ('SL', 'Saarland'),
        ('SN', 'Sachsen'),
        ('ST', 'Sachsen-Anhalt'),
        ('SH', 'Schleswig-Holstein'),
        ('TH', 'Thüringen'),
    ]

    name = models.CharField(max_length=300, verbose_name='Name')
    auto_id = models.AutoField(primary_key=True)
    account_type = models.ForeignKey(
        AccountType, on_delete=models.PROTECT, verbose_name='Account-Typ',
        null=True, blank=True,
    )
    bundesland = models.CharField(
        max_length=2, choices=BUNDESLAND_CHOICES, blank=True,
        verbose_name='Bundesland',
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


class SurveySnapshot(models.Model):
    account = models.ForeignKey(
        Account, on_delete=models.CASCADE,
        related_name='survey_snapshots', verbose_name='Account',
    )
    year = models.IntegerField(verbose_name='Jahr')

    # Zufriedenheit normalisiert 1–5 (null = nicht erhoben)
    satisfaction_app               = models.IntegerField(null=True, blank=True, verbose_name='App')
    satisfaction_cms               = models.IntegerField(null=True, blank=True, verbose_name='Redaktionssystem')
    satisfaction_support           = models.IntegerField(null=True, blank=True, verbose_name='Betreuung')
    satisfaction_overall           = models.IntegerField(null=True, blank=True, verbose_name='Gesamt')
    satisfaction_content_quality   = models.IntegerField(null=True, blank=True, verbose_name='Inhaltsqualität')
    satisfaction_content_freshness = models.IntegerField(null=True, blank=True, verbose_name='Aktualität Inhalte')

    weekly_hours    = models.FloatField(null=True, blank=True, verbose_name='Stunden/Woche')
    promotes_online = models.BooleanField(null=True, blank=True, verbose_name='Bewirbt online')

    free_text_positive    = models.TextField(blank=True, default='', verbose_name='Was gefällt')
    free_text_improvement = models.TextField(blank=True, default='', verbose_name='Verbesserungspotenzial')

    respondent_email       = models.CharField(max_length=300, blank=True, default='')
    respondent_name        = models.CharField(max_length=300, blank=True, default='')
    limesurvey_response_id = models.IntegerField(null=True, blank=True)

    class Meta:
        verbose_name = 'Umfrage-Snapshot'
        verbose_name_plural = 'Umfrage-Snapshots'
        ordering = ['year']
        unique_together = [('account', 'year')]

    def __str__(self):
        return f'{self.account} – {self.year}'


class RegionHealthUpload(models.Model):
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        verbose_name='Hochgeladen von',
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='Hochgeladen am')
    filename = models.CharField(max_length=255, verbose_name='Dateiname')
    rows_total = models.IntegerField(verbose_name='Zeilen gesamt')
    rows_matched = models.IntegerField(verbose_name='Zeilen gematchet')

    class Meta:
        verbose_name = 'Region-Health-Upload'
        verbose_name_plural = 'Region-Health-Uploads'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'{self.filename} ({self.uploaded_at:%d.%m.%Y})'


class RegionHealthEntry(models.Model):
    AMPEL_CHOICES = [
        ('green', 'Grün'),
        ('yellow', 'Gelb'),
        ('red', 'Rot'),
    ]

    upload = models.ForeignKey(
        RegionHealthUpload, on_delete=models.CASCADE, related_name='entries',
        verbose_name='Upload',
    )
    account = models.ForeignKey(
        'Account', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='region_health_entries', verbose_name='Account',
    )
    region_name = models.CharField(max_length=300, verbose_name='Region (CSV)')
    broken_links = models.IntegerField(verbose_name='Fehlerhafte Links')
    hix_low_count = models.IntegerField(verbose_name='Seiten mit niedrigem HIX')
    total_pages = models.IntegerField(verbose_name='Seiten gesamt')
    missing_translation_pages = models.IntegerField(verbose_name='Seiten mit fehlenden Übersetzungen')
    outdated_pages = models.IntegerField(verbose_name='Veraltete Seiten')
    mt_budget = models.IntegerField(verbose_name='MT Budget')
    active_languages = models.IntegerField(verbose_name='Aktive Sprachen')
    ampel_score = models.FloatField(verbose_name='Ampel-Score')
    ampel_color = models.CharField(
        max_length=10, choices=AMPEL_CHOICES, verbose_name='Ampelfarbe',
    )

    class Meta:
        verbose_name = 'Region-Health-Eintrag'
        verbose_name_plural = 'Region-Health-Einträge'
        ordering = ['-upload__uploaded_at', 'region_name']

    def __str__(self):
        return self.region_name


class SurveyFeature(models.Model):
    class Kind(models.TextChoices):
        REQUEST  = 'request',  'Feature-Wunsch'
        NOT_USED = 'not_used', 'Bekannt, aber ungenutzt'

    snapshot     = models.ForeignKey(
        SurveySnapshot, on_delete=models.CASCADE,
        related_name='features', verbose_name='Snapshot',
    )
    feature_name = models.CharField(max_length=300, verbose_name='Feature')
    kind         = models.CharField(max_length=10, choices=Kind.choices)

    class Meta:
        verbose_name = 'Survey-Feature'
        ordering = ['feature_name']

    def __str__(self):
        return self.feature_name
