from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from accounts.models import Account, Contact


class Campaign(models.Model):
    name = models.CharField(max_length=300, verbose_name=_('Name'))
    start_date = models.DateField(verbose_name=_('Startdatum'))
    end_date = models.DateField(verbose_name=_('Enddatum'))
    product = models.ForeignKey(
        'products.Product', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('Produkt'),
        related_name='campaigns',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        verbose_name=_('Erstellt von'),
    )
    is_archived = models.BooleanField(default=False, verbose_name=_('Archiviert'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Kampagne')
        verbose_name_plural = _('Kampagnen')
        ordering = ['-start_date']

    def __str__(self):
        return self.name


class CampaignContact(models.Model):
    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name='campaign_contacts',
        verbose_name=_('Kampagne'),
    )
    contact = models.ForeignKey(
        Contact, on_delete=models.SET_NULL, null=True,
        verbose_name=_('Kontakt'),
    )
    account = models.ForeignKey(
        Account, on_delete=models.SET_NULL, null=True,
        verbose_name=_('Account'),
    )
    # Snapshot fields
    contact_name = models.CharField(max_length=300, verbose_name=_('Name'))
    contact_salutation = models.CharField(max_length=200, blank=True, default='', verbose_name=_('Anrede'))
    contact_email = models.EmailField(blank=True, verbose_name=_('E-Mail'))
    contact_phone = models.CharField(max_length=50, blank=True, verbose_name=_('Telefon'))
    account_name = models.CharField(max_length=300, verbose_name=_('Account'))
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Kampagnen-Kontakt')
        verbose_name_plural = _('Kampagnen-Kontakte')
        unique_together = ['campaign', 'contact']
        ordering = ['account_name', 'contact_name']

    def __str__(self):
        return f'{self.contact_name} ({self.account_name})'


class AccountCampaign(models.Model):
    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name='account_campaigns',
        verbose_name=_('Account'),
    )
    campaign = models.ForeignKey(
        Campaign, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='account_campaign_links', verbose_name=_('Kampagne'),
    )
    name = models.CharField(max_length=300, blank=True, verbose_name=_('Name'))
    start_date = models.DateField(null=True, blank=True, verbose_name=_('Startdatum'))
    end_date = models.DateField(null=True, blank=True, verbose_name=_('Enddatum'))
    attachment = models.FileField(
        upload_to='campaign_attachments/%Y/%m/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])],
        null=True, blank=True, verbose_name=_('Anhang'),
    )
    is_successful = models.BooleanField(default=False, verbose_name=_('Erfolgreich'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Account-Kampagne')
        verbose_name_plural = _('Account-Kampagnen')
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
