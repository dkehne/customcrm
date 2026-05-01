from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models

from accounts.models import Account, Contact


class Campaign(models.Model):
    name = models.CharField(max_length=300, verbose_name='Name')
    start_date = models.DateField(verbose_name='Startdatum')
    end_date = models.DateField(verbose_name='Enddatum')
    product = models.ForeignKey(
        'products.Product', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='Produkt',
        related_name='campaigns',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        verbose_name='Erstellt von',
    )
    is_archived = models.BooleanField(default=False, verbose_name='Archiviert')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Kampagne'
        verbose_name_plural = 'Kampagnen'
        ordering = ['-start_date']

    def __str__(self):
        return self.name


class CampaignContact(models.Model):
    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name='campaign_contacts',
        verbose_name='Kampagne',
    )
    contact = models.ForeignKey(
        Contact, on_delete=models.SET_NULL, null=True,
        verbose_name='Kontakt',
    )
    account = models.ForeignKey(
        Account, on_delete=models.SET_NULL, null=True,
        verbose_name='Account',
    )
    # Snapshot fields
    contact_name = models.CharField(max_length=300, verbose_name='Name')
    contact_salutation = models.CharField(max_length=200, blank=True, default='', verbose_name='Anrede')
    contact_email = models.EmailField(blank=True, verbose_name='E-Mail')
    contact_phone = models.CharField(max_length=50, blank=True, verbose_name='Telefon')
    account_name = models.CharField(max_length=300, verbose_name='Account')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Kampagnen-Kontakt'
        verbose_name_plural = 'Kampagnen-Kontakte'
        unique_together = ['campaign', 'contact']
        ordering = ['account_name', 'contact_name']

    def __str__(self):
        return f'{self.contact_name} ({self.account_name})'


class AccountCampaign(models.Model):
    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name='account_campaigns',
        verbose_name='Account',
    )
    campaign = models.ForeignKey(
        Campaign, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='account_campaign_links', verbose_name='Kampagne',
    )
    name = models.CharField(max_length=300, blank=True, verbose_name='Name')
    start_date = models.DateField(null=True, blank=True, verbose_name='Startdatum')
    end_date = models.DateField(null=True, blank=True, verbose_name='Enddatum')
    attachment = models.FileField(
        upload_to='campaign_attachments/%Y/%m/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])],
        null=True, blank=True, verbose_name='Anhang',
    )
    is_successful = models.BooleanField(default=False, verbose_name='Erfolgreich')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Account-Kampagne'
        verbose_name_plural = 'Account-Kampagnen'
        ordering = ['-created_at']

    def __str__(self):
        return self.display_name

    @property
    def is_external(self):
        return self.campaign is None

    @property
    def display_name(self):
        return self.name if self.is_external else self.campaign.name

    @property
    def display_start_date(self):
        return self.start_date if self.is_external else self.campaign.start_date

    @property
    def display_end_date(self):
        return self.end_date if self.is_external else self.campaign.end_date
