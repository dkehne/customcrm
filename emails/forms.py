from django import forms
from accounts.models import Account
from core.utils import BootstrapFormMixin
from .models import UserEmailAddress


class UserEmailAddressForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = UserEmailAddress
        fields = ['email']
        widgets = {'email': forms.EmailInput(attrs={'placeholder': 'name@example.com'})}


class AssignEmailForm(BootstrapFormMixin, forms.Form):
    account = forms.ModelChoiceField(queryset=Account.objects.filter(is_archived=False).order_by('name'), label='Account')
