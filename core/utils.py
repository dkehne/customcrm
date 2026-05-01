from django import forms
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse


def _resolve_redirect(redirect_url):
    """Resolve redirect_url which can be a string or tuple (url_name, kwargs)."""
    if isinstance(redirect_url, tuple):
        return reverse(redirect_url[0], kwargs=redirect_url[1])
    return redirect_url


def toggle_archive(request, obj, redirect_url, name_attr='name'):
    """Toggle is_archived on an object and redirect with success message."""
    obj.is_archived = not obj.is_archived
    obj.save()
    if name_attr:
        name = getattr(obj, name_attr, str(obj))
        action = 'archiviert' if obj.is_archived else 'wiederhergestellt'
        messages.success(request, f'"{name}" {action}.')
    else:
        action = 'archiviert' if obj.is_archived else 'wiederhergestellt'
        messages.success(request, f'{action.capitalize()}.')
    return redirect(_resolve_redirect(redirect_url))


def confirm_delete(request, obj, redirect_url, name_attr='name'):
    """
    Delete an object after confirmation. Returns redirect response or None if checks fail.
    Object must be archived before deletion. User must confirm with their username.
    """
    resolved_url = _resolve_redirect(redirect_url)
    name = getattr(obj, name_attr, str(obj)) if name_attr else None

    if request.method != 'POST' or not getattr(obj, 'is_archived', True):
        messages.error(request, 'Löschen nicht erlaubt.')
        return redirect(resolved_url)

    if request.POST.get('confirm_username') != request.user.username:
        messages.error(request, 'Benutzername stimmt nicht überein.')
        return redirect(resolved_url)

    obj.delete()
    if name:
        messages.success(request, f'"{name}" endgültig gelöscht.')
    else:
        messages.success(request, 'Endgültig gelöscht.')
    return redirect(resolved_url)


class BootstrapFormMixin:
    """Mixin that auto-applies Bootstrap CSS classes to form widgets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            css_class = self._get_bootstrap_class(widget)
            if css_class:
                existing = widget.attrs.get('class', '')
                if css_class not in existing:
                    widget.attrs['class'] = f'{existing} {css_class}'.strip()

    def _get_bootstrap_class(self, widget):
        if isinstance(widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
            return 'form-check-input'
        if isinstance(widget, (forms.Select, forms.SelectMultiple)):
            return 'form-select'
        if isinstance(widget, (forms.FileInput, forms.ClearableFileInput)):
            return 'form-control'
        if isinstance(widget, (forms.TextInput, forms.Textarea, forms.EmailInput,
                               forms.NumberInput, forms.DateInput, forms.PasswordInput)):
            return 'form-control'
        return None
