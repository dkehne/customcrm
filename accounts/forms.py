from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from core.utils import BootstrapFormMixin
from .models import Account, Contact, AccountType, Activity, Todo


class AccountForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Account
        fields = ['name', 'account_type', 'owner', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['account_type'].queryset = AccountType.objects.filter(is_archived=False)


class ContactForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Contact
        fields = ['name', 'email', 'phone', 'position', 'anrede', 'is_primary']

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('is_primary') and not cleaned_data.get('anrede', '').strip():
            self.add_error('anrede', _('Pflichtfeld für Hauptansprechpersonen.'))
        return cleaned_data


class AccountTypeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AccountType
        fields = ['name']


class ActivityForm(BootstrapFormMixin, forms.ModelForm):
    MANUAL_ACTIVITY_TYPES = [('call', _('Telefonanruf')), ('email', _('E-Mail')), ('meeting', _('Termin'))]

    class Meta:
        model = Activity
        fields = ['activity_type', 'subject', 'description', 'date', 'contact']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
            'date': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        }

    def __init__(self, *args, account=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['activity_type'].choices = self.MANUAL_ACTIVITY_TYPES
        self.fields['contact'].queryset = Contact.objects.filter(
            account=account, is_archived=False
        ) if account else Contact.objects.none()


class TodoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Todo
        fields = ['title', 'description', 'due_date', 'attachment', 'assigned_to']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
            'due_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'attachment': forms.FileInput(attrs={'accept': '.pdf'}),
        }

    def __init__(self, *args, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        User = get_user_model()
        self.fields['assigned_to'].queryset = User.objects.filter(is_active=True).order_by('first_name', 'last_name', 'username')
        self.fields['assigned_to'].empty_label = _('— Nicht zugewiesen —')
        if current_user and not self.instance.pk:
            self.fields['assigned_to'].initial = current_user
