from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from accounts.forms import AccountTypeForm
from accounts.models import AccountType
from contracts.forms import ContractTypeForm
from contracts.models import ContractType
from products.forms import ProductForm, ProductPhaseForm, ProductFieldForm
from products.models import Product, ProductPhase, ProductField

from .forms import UserCreateForm, UserEditForm, SiteSettingsForm
from .models import CustomUser, SiteSettings
from .utils import toggle_archive, confirm_delete


def superuser_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, _('Zugriff verweigert.'))
            return redirect('core:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def _handle_form(request, form_class, redirect_url, title, instance=None, parent_field=None, parent_obj=None):
    """Generic form handler for create/edit views."""
    if request.method == 'POST':
        form = form_class(request.POST, instance=instance)
        if form.is_valid():
            obj = form.save(commit=parent_field is None)
            if parent_field:
                setattr(obj, parent_field, parent_obj)
                obj.save()
            action = _('aktualisiert') if instance else _('erstellt')
            messages.success(request, _('{name} {action}.').format(name=title.split()[0], action=action))
            return redirect(redirect_url)
    else:
        form = form_class(instance=instance)
    return render(request, 'settings/generic_form.html', {
        'form': form, 'title': title, 'back_url': redirect_url,
    })


# AccountType CRUD
@superuser_required
def account_type_list(request):
    return render(request, 'settings/account_type_list.html', {'types': AccountType.objects.all()})


@superuser_required
def account_type_create(request):
    return _handle_form(request, AccountTypeForm, 'settings:account_type_list', 'Neuer Account-Typ')


@superuser_required
def account_type_edit(request, pk):
    obj = get_object_or_404(AccountType, pk=pk)
    return _handle_form(request, AccountTypeForm, 'settings:account_type_list',
                        f'Account-Typ bearbeiten: {obj.name}', instance=obj)


@superuser_required
def account_type_archive(request, pk):
    return toggle_archive(request, get_object_or_404(AccountType, pk=pk), 'settings:account_type_list')


@superuser_required
def account_type_delete(request, pk):
    return confirm_delete(request, get_object_or_404(AccountType, pk=pk), 'settings:account_type_list')


# Product CRUD
@superuser_required
def product_list(request):
    return render(request, 'settings/product_list.html', {
        'products': Product.objects.prefetch_related('phases', 'fields').all()
    })


@superuser_required
def product_create(request):
    return _handle_form(request, ProductForm, 'settings:product_list', 'Neues Produkt')


@superuser_required
def product_edit(request, pk):
    obj = get_object_or_404(Product, pk=pk)
    return _handle_form(request, ProductForm, 'settings:product_list',
                        f'Produkt bearbeiten: {obj.name}', instance=obj)


@superuser_required
def product_archive(request, pk):
    return toggle_archive(request, get_object_or_404(Product, pk=pk), 'settings:product_list')


@superuser_required
def product_delete(request, pk):
    return confirm_delete(request, get_object_or_404(Product, pk=pk), 'settings:product_list')


# ProductPhase CRUD
@superuser_required
def product_phase_create(request, product_pk):
    product = get_object_or_404(Product, pk=product_pk)
    return _handle_form(request, ProductPhaseForm, 'settings:product_list',
                        f'Neue Phase für {product.name}', parent_field='product', parent_obj=product)


@superuser_required
def product_phase_edit(request, pk):
    obj = get_object_or_404(ProductPhase, pk=pk)
    return _handle_form(request, ProductPhaseForm, 'settings:product_list',
                        f'Phase bearbeiten: {obj.name}', instance=obj)


@superuser_required
def product_phase_delete(request, pk):
    get_object_or_404(ProductPhase, pk=pk).delete()
    messages.success(request, _('Phase gelöscht.'))
    return redirect('settings:product_list')


# ProductField CRUD
@superuser_required
def product_field_create(request, product_pk):
    product = get_object_or_404(Product, pk=product_pk)
    return _handle_form(request, ProductFieldForm, 'settings:product_list',
                        f'Neues Feld für {product.name}', parent_field='product', parent_obj=product)


@superuser_required
def product_field_edit(request, pk):
    obj = get_object_or_404(ProductField, pk=pk)
    return _handle_form(request, ProductFieldForm, 'settings:product_list',
                        f'Feld bearbeiten: {obj.name}', instance=obj)


@superuser_required
def product_field_archive(request, pk):
    return toggle_archive(request, get_object_or_404(ProductField, pk=pk), 'settings:product_list')


@superuser_required
def product_field_delete(request, pk):
    return confirm_delete(request, get_object_or_404(ProductField, pk=pk), 'settings:product_list')


# ContractType CRUD
@superuser_required
def contract_type_list(request):
    return render(request, 'settings/contract_type_list.html', {'types': ContractType.objects.all()})


@superuser_required
def contract_type_create(request):
    return _handle_form(request, ContractTypeForm, 'settings:contract_type_list', 'Neuer Vertragstyp')


@superuser_required
def contract_type_edit(request, pk):
    obj = get_object_or_404(ContractType, pk=pk)
    return _handle_form(request, ContractTypeForm, 'settings:contract_type_list',
                        f'Vertragstyp bearbeiten: {obj.name}', instance=obj)


@superuser_required
def contract_type_archive(request, pk):
    return toggle_archive(request, get_object_or_404(ContractType, pk=pk), 'settings:contract_type_list')


@superuser_required
def contract_type_toggle_active(request, pk):
    if request.method != 'POST':
        return redirect('settings:contract_type_list')
    obj = get_object_or_404(ContractType, pk=pk)
    obj.is_active = not obj.is_active
    obj.save()
    return redirect('settings:contract_type_list')


@superuser_required
def contract_type_delete(request, pk):
    return confirm_delete(request, get_object_or_404(ContractType, pk=pk), 'settings:contract_type_list')


# User Management
@superuser_required
def user_list(request):
    return render(request, 'settings/user_list.html', {'users': CustomUser.objects.order_by('username')})


@superuser_required
def user_create(request):
    return _handle_form(request, UserCreateForm, 'settings:user_list', 'Neuer Benutzer')


@superuser_required
def user_edit(request, pk):
    obj = get_object_or_404(CustomUser, pk=pk)
    return _handle_form(request, UserEditForm, 'settings:user_list',
                        f'Benutzer bearbeiten: {obj.username}', instance=obj)


# Site Settings (Branding)
@superuser_required
def site_settings(request):
    settings = SiteSettings.get_settings()
    if request.method == 'POST':
        form = SiteSettingsForm(request.POST, request.FILES, instance=settings)
        if form.is_valid():
            form.save()
            messages.success(request, _('Systemeinstellungen gespeichert.'))
            return redirect('settings:site_settings')
    else:
        form = SiteSettingsForm(instance=settings)
    return render(request, 'settings/site_settings.html', {'form': form})
