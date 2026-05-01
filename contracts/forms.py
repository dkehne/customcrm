from django import forms
from django.utils.translation import gettext_lazy as _
from core.utils import BootstrapFormMixin
from .models import Contract, ContractDocument, ContractType


class ContractForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Contract
        fields = [
            'account_product', 'gross_annual_price', 'contract_type',
            'start_date', 'duration_months', 'is_self_cancelling',
            'renewal_interval_months', 'notice_period_months',
        ]
        widgets = {
            'gross_annual_price': forms.NumberInput(attrs={'step': '0.01'}),
            'start_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, account=None, **kwargs):
        super().__init__(*args, **kwargs)
        ct_qs = ContractType.objects.filter(is_archived=False, is_active=True)
        if self.instance and self.instance.pk and self.instance.contract_type_id:
            ct_qs = ct_qs | ContractType.objects.filter(pk=self.instance.contract_type_id)
        self.fields['contract_type'].queryset = ct_qs
        if account:
            from products.models import AccountProduct
            self.fields['account_product'].queryset = AccountProduct.objects.filter(
                account=account, is_archived=False
            ).select_related('product')

    def clean(self):
        cleaned_data = super().clean()
        duration = cleaned_data.get('duration_months')
        if duration is not None and duration <= 0:
            self.add_error('duration_months', _('Laufzeit muss mindestens 1 Monat betragen.'))
        if cleaned_data.get('is_self_cancelling') and cleaned_data.get('renewal_interval_months'):
            self.add_error(
                'renewal_interval_months',
                _('Bei festem Enddatum ist kein Verlängerungsintervall möglich.'),
            )
        return cleaned_data


class ContractDocumentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ContractDocument
        fields = ['file']
        widgets = {'file': forms.ClearableFileInput(attrs={'accept': '.pdf'})}


class ContractTypeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ContractType
        fields = ['name']
