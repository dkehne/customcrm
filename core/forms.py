from django import forms
from django.utils.translation import gettext_lazy as _
from .models import CustomUser, SiteSettings
from .utils import BootstrapFormMixin


class SiteSettingsForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = [
            'site_name', 'logo', 'primary_color',
            'account_label_singular', 'account_label_plural',
            'product_label_singular', 'product_label_plural',
            'contact_label_singular', 'contact_label_plural',
            'contracts_enabled', 'campaigns_enabled',
        ]
        widgets = {
            'primary_color': forms.TextInput(attrs={'type': 'color'}),
        }


class UserCreateForm(BootstrapFormMixin, forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(), label=_('Passwort'))

    class Meta:
        model = CustomUser
        fields = ['username', 'first_name', 'last_name', 'role']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class UserEditForm(BootstrapFormMixin, forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(), label=_('Neues Passwort'), required=False,
        help_text=_('Leer lassen, um das Passwort nicht zu ändern.'),
    )

    class Meta:
        model = CustomUser
        fields = ['username', 'first_name', 'last_name', 'role', 'is_active']
        labels = {'is_active': _('Aktiv')}

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user
