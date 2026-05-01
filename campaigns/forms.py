from django import forms
from django.utils.translation import gettext_lazy as _
from core.utils import BootstrapFormMixin
from products.models import Product
from .models import Campaign, AccountCampaign


class CampaignForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ['name', 'start_date', 'end_date', 'product']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'end_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(is_archived=False)
        self.fields['product'].required = False
        self.fields['product'].empty_label = _('Kein Produkt')

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', _('Enddatum darf nicht vor dem Startdatum liegen.'))
        return cleaned_data


class AccountCampaignForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AccountCampaign
        fields = ['name', 'start_date', 'end_date', 'attachment']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'end_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'attachment': forms.ClearableFileInput(attrs={'accept': '.pdf'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', _('Enddatum darf nicht vor dem Startdatum liegen.'))
        return cleaned_data
