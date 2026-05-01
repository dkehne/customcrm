from django.contrib.auth.models import AbstractUser
from django.core.cache import cache
from django.db import models


class SiteSettings(models.Model):
    """Singleton model for site-wide branding settings."""

    site_name = models.CharField(
        max_length=100,
        default='CustomCRM',
        verbose_name='Systemname',
        help_text='Name des Systems, wird in der Navigation und im Titel angezeigt',
    )
    logo = models.ImageField(
        upload_to='branding/',
        blank=True,
        null=True,
        verbose_name='Logo',
        help_text='Logo im PNG-Format (rechteckig empfohlen, max. 200px Höhe)',
    )
    primary_color = models.CharField(
        max_length=7,
        default='#CED51E',
        verbose_name='Primärfarbe',
        help_text='Hauptfarbe im Hex-Format (z.B. #CED51E)',
    )

    # Configurable Labels
    account_label_singular = models.CharField(
        max_length=50, default='Konto',
        verbose_name='Account-Bezeichnung (Einzahl)',
        help_text='z.B. "Kommune", "Organisation", "Kunde"',
    )
    account_label_plural = models.CharField(
        max_length=50, default='Konten',
        verbose_name='Account-Bezeichnung (Mehrzahl)',
        help_text='z.B. "Kommunen", "Organisationen", "Kunden"',
    )
    product_label_singular = models.CharField(
        max_length=50, default='Produkt',
        verbose_name='Produkt-Bezeichnung (Einzahl)',
        help_text='z.B. "Produkt", "Service", "Leistung"',
    )
    product_label_plural = models.CharField(
        max_length=50, default='Produkte',
        verbose_name='Produkt-Bezeichnung (Mehrzahl)',
        help_text='z.B. "Produkte", "Services", "Leistungen"',
    )
    contact_label_singular = models.CharField(
        max_length=50, default='Kontakt',
        verbose_name='Kontakt-Bezeichnung (Einzahl)',
    )
    contact_label_plural = models.CharField(
        max_length=50, default='Kontakte',
        verbose_name='Kontakt-Bezeichnung (Mehrzahl)',
    )

    # Module Toggles
    contracts_enabled = models.BooleanField(
        default=True,
        verbose_name='Verträge aktiviert',
        help_text='Wenn deaktiviert, werden Vertrags-Menüpunkte und -Widgets ausgeblendet',
    )
    campaigns_enabled = models.BooleanField(
        default=True,
        verbose_name='Kampagnen aktiviert',
        help_text='Wenn deaktiviert, werden Kampagnen-Menüpunkte ausgeblendet',
    )

    class Meta:
        verbose_name = 'Systemeinstellungen'
        verbose_name_plural = 'Systemeinstellungen'

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
        SUPERUSER = 'superuser', 'Superuser'
        VERWALTER = 'verwalter', 'Verwalter'

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.VERWALTER)
    default_dashboard_product = models.ForeignKey(
        'products.Product', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='Standard-Dashboard-Produkt',
        related_name='default_for_users',
    )

    class Meta:
        verbose_name = 'Benutzer'
        verbose_name_plural = 'Benutzer'

    def save(self, *args, **kwargs):
        self.is_superuser = self.role == self.Role.SUPERUSER
        super().save(*args, **kwargs)

    def __str__(self):
        return self.get_full_name() or self.username
