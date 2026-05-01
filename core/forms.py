from django import forms
from .models import CustomUser, SiteSettings
from .utils import BootstrapFormMixin


class SiteSettingsForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = ['site_name', 'logo', 'primary_color']
        widgets = {
            'primary_color': forms.TextInput(attrs={'type': 'color'}),
        }


class UserCreateForm(BootstrapFormMixin, forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(), label='Passwort')

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
        widget=forms.PasswordInput(), label='Neues Passwort', required=False,
        help_text='Leer lassen, um das Passwort nicht zu ändern.',
    )

    class Meta:
        model = CustomUser
        fields = ['username', 'first_name', 'last_name', 'role', 'is_active']
        labels = {'is_active': 'Aktiv'}

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user
