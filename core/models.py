from django.contrib.auth.models import AbstractUser
from django.core.cache import cache
from django.db import models
from django.utils.translation import gettext_lazy as _


class SiteSettings(models.Model):
    """Singleton model for site-wide branding settings."""

    site_name = models.CharField(
        max_length=100,
        default='CustomCRM',
        verbose_name=_('Systemname'),
        help_text=_('Name des Systems, wird in der Navigation und im Titel angezeigt'),
    )
    logo = models.ImageField(
        upload_to='branding/',
        blank=True,
        null=True,
        verbose_name=_('Logo'),
        help_text=_('Logo im PNG-Format (rechteckig empfohlen, max. 200px Höhe)'),
    )
    primary_color = models.CharField(
        max_length=7,
        default='#CED51E',
        verbose_name=_('Primärfarbe'),
        help_text=_('Hauptfarbe im Hex-Format (z.B. #CED51E)'),
    )

    # Configurable Labels
    account_label_singular = models.CharField(
        max_length=50, default='Konto',
        verbose_name=_('Account-Bezeichnung (Einzahl)'),
        help_text=_('z.B. "Kommune", "Organisation", "Kunde"'),
    )
    account_label_plural = models.CharField(
        max_length=50, default='Konten',
        verbose_name=_('Account-Bezeichnung (Mehrzahl)'),
        help_text=_('z.B. "Kommunen", "Organisationen", "Kunden"'),
    )
    product_label_singular = models.CharField(
        max_length=50, default='Produkt',
        verbose_name=_('Produkt-Bezeichnung (Einzahl)'),
        help_text=_('z.B. "Produkt", "Service", "Leistung"'),
    )
    product_label_plural = models.CharField(
        max_length=50, default='Produkte',
        verbose_name=_('Produkt-Bezeichnung (Mehrzahl)'),
        help_text=_('z.B. "Produkte", "Services", "Leistungen"'),
    )
    contact_label_singular = models.CharField(
        max_length=50, default='Kontakt',
        verbose_name=_('Kontakt-Bezeichnung (Einzahl)'),
    )
    contact_label_plural = models.CharField(
        max_length=50, default='Kontakte',
        verbose_name=_('Kontakt-Bezeichnung (Mehrzahl)'),
    )

    # Module Toggles
    contracts_enabled = models.BooleanField(
        default=True,
        verbose_name=_('Verträge aktiviert'),
        help_text=_('Wenn deaktiviert, werden Vertrags-Menüpunkte und -Widgets ausgeblendet'),
    )
    campaigns_enabled = models.BooleanField(
        default=True,
        verbose_name=_('Kampagnen aktiviert'),
        help_text=_('Wenn deaktiviert, werden Kampagnen-Menüpunkte ausgeblendet'),
    )

    class Meta:
        verbose_name = _('Systemeinstellungen')
        verbose_name_plural = _('Systemeinstellungen')

    def __str__(self):
        return 'Systemeinstellungen'

    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        self.pk = 1
        super().save(*args, **kwargs)
        # Clear cache when settings change
        cache.delete('site_settings')

    @classmethod
    def get_settings(cls):
        """Get the singleton settings instance, with caching."""
        settings = cache.get('site_settings')
        if settings is None:
            settings, _ = cls.objects.get_or_create(pk=1)
            cache.set('site_settings', settings, 3600)  # Cache for 1 hour
        return settings


class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        SUPERUSER = 'superuser', _('Superuser')
        VERWALTER = 'verwalter', _('Verwalter')

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.VERWALTER)
    default_dashboard_product = models.ForeignKey(
        'products.Product', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('Standard-Dashboard-Produkt'),
        related_name='default_for_users',
    )

    class Meta:
        verbose_name = _('Benutzer')
        verbose_name_plural = _('Benutzer')

    def save(self, *args, **kwargs):
        self.is_superuser = self.role == self.Role.SUPERUSER
        super().save(*args, **kwargs)

    def __str__(self):
        return self.get_full_name() or self.username
