from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from accounts.models import Activity
from products.models import Product
from .forms import AssignEmailForm, UserEmailAddressForm
from .models import InboundEmail, UserEmailAddress, UserInboundAddress


@login_required
def profile_overview(request):
    inbound_address, _ = UserInboundAddress.objects.get_or_create(user=request.user)
    email_addresses = UserEmailAddress.objects.filter(user=request.user)
    form = UserEmailAddressForm()
    products = Product.objects.filter(is_archived=False)
    return render(request, 'emails/profile_overview.html', {
        'inbound_address': inbound_address,
        'email_addresses': email_addresses,
        'form': form,
        'products': products,
    })


@login_required
def set_default_product(request):
    if request.method == 'POST':
        product_id = request.POST.get('default_product')
        if product_id:
            try:
                product = Product.objects.get(pk=product_id, is_archived=False)
                request.user.default_dashboard_product = product
                request.user.save()
                messages.success(request, _(f'Standard-Produkt auf "{product.name}" gesetzt.'))
            except Product.DoesNotExist:
                messages.error(request, _('Ungültiges Produkt.'))
        else:
            request.user.default_dashboard_product = None
            request.user.save()
            messages.success(request, _('Standard-Produkt entfernt.'))
    return redirect('emails:profile_overview')


@login_required
def email_address_add(request):
    if request.method == 'POST':
        form = UserEmailAddressForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user
            try:
                obj.save()
                messages.success(request, _(f'E-Mail-Adresse "{obj.email}" hinzugefügt.'))
            except IntegrityError:
                messages.error(request, _('Diese E-Mail-Adresse ist bereits registriert.'))
    return redirect('emails:profile_overview')


@login_required
def email_address_delete(request, pk):
    if request.method == 'POST':
        obj = get_object_or_404(UserEmailAddress, pk=pk, user=request.user)
        email = obj.email
        obj.delete()
        messages.success(request, _(f'E-Mail-Adresse "{email}" entfernt.'))
    return redirect('emails:profile_overview')


@login_required
def unresolved_emails(request):
    emails = InboundEmail.objects.filter(
        user=request.user, status='unresolved',
    ).order_by('-received_at')
    email_list = [
        {'email': e, 'form': AssignEmailForm()}
        for e in emails
    ]
    return render(request, 'emails/unresolved_emails.html', {
        'email_list': email_list,
    })


@login_required
def delete_email(request, pk):
    email_obj = get_object_or_404(InboundEmail, pk=pk, user=request.user, status='unresolved')
    if request.method == 'POST':
        if request.POST.get('confirm_username') != request.user.username:
            messages.error(request, _('Benutzername stimmt nicht überein.'))
            return redirect('emails:unresolved_emails')
        subject = email_obj.subject or _('(Kein Betreff)')
        email_obj.delete()
        messages.success(request, _(f'E-Mail "{subject}" gelöscht.'))
    return redirect('emails:unresolved_emails')


@login_required
def assign_email(request, pk):
    email_obj = get_object_or_404(InboundEmail, pk=pk, user=request.user)
    if request.method == 'POST':
        form = AssignEmailForm(request.POST)
        if form.is_valid():
            account = form.cleaned_data['account']
            email_obj.account = account
            email_obj.status = 'resolved'
            email_obj.save()
            Activity.objects.create(
                account=account,
                activity_type='email',
                subject=email_obj.subject or _('(Kein Betreff)'),
                description=f'Von: {email_obj.sender_email}',
                date=email_obj.received_at,
                created_by=request.user,
                inbound_email=email_obj,
            )
            messages.success(request, _(f'E-Mail "{email_obj.subject}" dem Account "{account.name}" zugewiesen.'))
    return redirect('emails:unresolved_emails')
