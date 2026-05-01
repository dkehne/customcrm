from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from django.core.validators import FileExtensionValidator
from django.db import models


class ContractType(models.Model):
    name = models.CharField(max_length=200, verbose_name='Name')
    is_active = models.BooleanField(default=True, verbose_name='Aktiv')
    is_archived = models.BooleanField(default=False, verbose_name='Archiviert')

    class Meta:
        verbose_name = 'Vertragstyp'
        verbose_name_plural = 'Vertragstypen'
        ordering = ['name']

    def __str__(self):
        return self.name


class Contract(models.Model):
    account = models.ForeignKey(
        'accounts.Account', on_delete=models.CASCADE,
        related_name='contracts', verbose_name='Account',
    )
    account_product = models.ForeignKey(
        'products.AccountProduct', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='contracts',
        verbose_name='Account-Produkt',
    )
    gross_annual_price = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name='Bruttojahrespreis (€)',
    )
    contract_type = models.ForeignKey(
        ContractType, on_delete=models.PROTECT, verbose_name='Vertragstyp',
        null=True, blank=True,
    )
    start_date = models.DateField(verbose_name='Startdatum')
    duration_months = models.PositiveIntegerField(verbose_name='Laufzeit (Monate)')
    is_self_cancelling = models.BooleanField(
        default=False, verbose_name='Festes Enddatum',
    )
    renewal_interval_months = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Verlängerungsintervall (Monate)',
    )
    notice_period_months = models.PositiveIntegerField(
        default=3, verbose_name='Kündigungsfrist (Monate)',
    )
    is_archived = models.BooleanField(default=False, verbose_name='Archiviert')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Vertrag'
        verbose_name_plural = 'Verträge'
        ordering = ['-start_date']

    def initial_end_date(self):
        return self.start_date + relativedelta(months=self.duration_months) - timedelta(days=1)

    def current_end_date(self):
        end = self.initial_end_date()
        if self.is_self_cancelling or not self.renewal_interval_months:
            return end
        today = date.today()
        while end < today:
            end += relativedelta(months=self.renewal_interval_months)
        # Wenn die Kündigungsfrist für die aktuelle Laufzeit bereits verstrichen ist,
        # ist die nächste Verlängerung schon fix.
        if self.notice_period_months:
            cancellation_deadline = end - relativedelta(months=self.notice_period_months)
            if today > cancellation_deadline:
                end += relativedelta(months=self.renewal_interval_months)
        return end

    def __str__(self):
        return f'Vertrag {self.pk} – {self.account.name}'


class ContractDocument(models.Model):
    contract = models.ForeignKey(
        Contract, on_delete=models.CASCADE, related_name='documents',
        verbose_name='Vertrag',
    )
    file = models.FileField(
        upload_to='contract_documents/%Y/%m/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])],
        verbose_name='PDF-Datei',
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='Hochgeladen am')

    class Meta:
        verbose_name = 'Vertragsdokument'
        verbose_name_plural = 'Vertragsdokumente'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'Dokument {self.pk} – {self.contract}'
