from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class Product(models.Model):
    name = models.CharField(max_length=200, verbose_name=_('Name'))
    is_archived = models.BooleanField(default=False, verbose_name=_('Archiviert'))

    class Meta:
        verbose_name = _('Produkt')
        verbose_name_plural = _('Produkte')
        ordering = ['name']

    def __str__(self):
        return self.name


class ProductPhase(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='phases',
        verbose_name=_('Produkt'),
    )
    name = models.CharField(max_length=200, verbose_name=_('Name'))
    order = models.PositiveIntegerField(default=0, verbose_name=_('Reihenfolge'))
    is_final_phase = models.BooleanField(
        default=False, verbose_name=_('Endphase (Aktiv/Verloren/Beendet)'),
    )

    class Meta:
        verbose_name = _('Produktphase')
        verbose_name_plural = _('Produktphasen')
        ordering = ['product', 'order']

    def __str__(self):
        return f'{self.product.name} – {self.name}'


class ProductField(models.Model):
    class FieldType(models.TextChoices):
        DATE = 'date', _('Datum')
        INTEGER = 'integer', _('Ganzzahl')
        BOOLEAN = 'boolean', _('Ja/Nein')

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='fields',
        verbose_name=_('Produkt'),
    )
    name = models.CharField(max_length=200, verbose_name=_('Name'))
    field_type = models.CharField(
        max_length=10, choices=FieldType.choices, verbose_name=_('Feldtyp'),
    )
    is_archived = models.BooleanField(default=False, verbose_name=_('Archiviert'))
    show_on_dashboard = models.BooleanField(default=True, verbose_name=_('Im Dashboard anzeigen'))

    class Meta:
        verbose_name = _('Produktfeld')
        verbose_name_plural = _('Produktfelder')
        ordering = ['product', 'name']

    def __str__(self):
        return f'{self.product.name} – {self.name}'


class AccountProduct(models.Model):
    class EndedReason(models.TextChoices):
        PRICE = 'price', _('Preis')
        COMPETITOR = 'competitor', _('Wechsel zu Wettbewerber')
        PERFORMANCE = 'performance', _('Leistung nicht gepasst')
        INTERNAL = 'internal', _('Interner Grund beim Partner')
        OTHER = 'other', _('Sonstiges (bitte Notiz schreiben)')

    account = models.ForeignKey(
        'accounts.Account', on_delete=models.CASCADE,
        related_name='account_products', verbose_name=_('Account'),
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE,
        related_name='account_products', verbose_name=_('Produkt'),
    )
    current_phase = models.ForeignKey(
        ProductPhase, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name=_('Aktuelle Phase'),
    )
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('Verantwortlicher'),
        related_name='responsible_products',
    )
    lead_account_product = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name=_('Leit-Account-Produkt (Produktverbund)'),
        related_name='partner_products',
    )
    primary_contacts = models.ManyToManyField(
        'accounts.Contact', blank=True, verbose_name=_('Hauptansprechpersonen'),
        related_name='primary_for_products',
    )
    ended_at = models.DateField(null=True, blank=True, verbose_name=_('Beendet zum'))
    ended_reason = models.CharField(
        max_length=20, choices=EndedReason.choices,
        null=True, blank=True, verbose_name=_('Beendigungsgrund'),
    )
    is_archived = models.BooleanField(default=False, verbose_name=_('Archiviert'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Account-Produkt')
        verbose_name_plural = _('Account-Produkte')
        unique_together = [('account', 'product')]

    def clean(self):
        if not self.lead_account_product_id:
            return
        # Prevent self-reference
        if self.pk and self.lead_account_product_id == self.pk:
            raise ValidationError(
                {'lead_account_product': _('Ein Produkt kann nicht sich selbst als Leit-Produkt haben.')}
            )
        # Detect cycles by traversing the chain
        visited = {self.pk} if self.pk else set()
        lead = self.lead_account_product
        while lead is not None:
            if lead.pk in visited:
                raise ValidationError(
                    {'lead_account_product': _('Kreisreferenz im Produktverbund nicht erlaubt.')}
                )
            visited.add(lead.pk)
            lead = lead.lead_account_product

    def __str__(self):
        return f'{self.account.name} – {self.product.name}'

    def get_responsible(self):
        """
        Returns the responsible user for this product assignment.
        - If explicitly set, returns the responsible user
        - If account has only one active product, returns the account owner
        - Otherwise returns None
        """
        if self.responsible:
            return self.responsible
        active_products_count = self.account.account_products.filter(is_archived=False).count()
        if active_products_count == 1:
            return self.account.owner
        return None


class AccountProductFieldValue(models.Model):
    account_product = models.ForeignKey(
        AccountProduct, on_delete=models.CASCADE,
        related_name='field_values', verbose_name=_('Account-Produkt'),
    )
    field = models.ForeignKey(
        ProductField, on_delete=models.CASCADE, verbose_name=_('Feld'),
    )
    value_text = models.CharField(max_length=500, blank=True, default='')
    value_int = models.IntegerField(null=True, blank=True)
    value_bool = models.BooleanField(null=True, blank=True)
    value_date = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = _('Feldwert')
        verbose_name_plural = _('Feldwerte')
        unique_together = ['account_product', 'field']

    def get_value(self):
        if self.field.field_type == ProductField.FieldType.DATE:
            return self.value_date
        elif self.field.field_type == ProductField.FieldType.INTEGER:
            return self.value_int
        elif self.field.field_type == ProductField.FieldType.BOOLEAN:
            return self.value_bool
        return self.value_text

    def __str__(self):
        return f'{self.field.name}: {self.get_value()}'
