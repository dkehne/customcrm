import csv

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import get_valid_filename
from django.utils.translation import gettext as _

from accounts.models import Account, Contact
from core.utils import toggle_archive, confirm_delete
from products.models import AccountProduct, Product, ProductPhase

from .forms import CampaignForm
from .models import Campaign, CampaignContact
from .utils import get_contacts_for_product


@login_required
def campaign_list(request):
    show_archived = request.GET.get('archived') == '1'
    campaigns = Campaign.objects.filter(is_archived=show_archived).annotate(
        contact_count=Count('campaign_contacts'),
    )

    products = Product.objects.filter(is_archived=False)
    phases = ProductPhase.objects.all()

    # Global CSV export
    if request.GET.get('export') == 'csv':
        product_id = request.GET.get('product', '')
        phase_id = request.GET.get('phase', '')

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="kontakte_export.csv"'
        response.charset = 'utf-8-sig'
        writer = csv.writer(response, delimiter=';')
        writer.writerow(['Account', 'Name', 'E-Mail', 'Produkt'])

        if product_id:
            try:
                filter_product = Product.objects.get(pk=int(product_id))
            except (ValueError, Product.DoesNotExist):
                filter_product = None

            if filter_product:
                matching_accounts = Account.objects.filter(
                    is_archived=False,
                    account_products__product=filter_product,
                    account_products__is_archived=False,
                ).distinct()
                if phase_id:
                    matching_accounts = matching_accounts.filter(
                        account_products__current_phase_id=phase_id,
                    ).distinct()
                for account in matching_accounts:
                    for contact in get_contacts_for_product(account, filter_product, phase_id):
                        writer.writerow([
                            account.name,
                            contact.name,
                            contact.email,
                            filter_product.name,
                        ])
        else:
            contacts = Contact.objects.filter(
                is_primary=True,
                is_archived=False,
                account__is_archived=False,
            ).select_related('account').prefetch_related(
                'primary_for_products__product',
            )
            for c in contacts:
                assigned = ', '.join(
                    ap.product.name
                    for ap in c.primary_for_products.all()
                    if not ap.is_archived
                )
                writer.writerow([
                    c.account.name,
                    c.name,
                    c.email,
                    assigned,
                ])
        return response

    return render(request, 'campaigns/campaign_list.html', {
        'campaigns': campaigns,
        'products': products,
        'phases': phases,
        'show_archived': show_archived,
    })


@login_required
def campaign_create(request):
    if request.method == 'POST':
        form = CampaignForm(request.POST)
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.created_by = request.user
            campaign.save()
            messages.success(request, _(f'Kampagne "{campaign.name}" erstellt.'))
            return redirect('campaigns:campaign_detail', pk=campaign.pk)
    else:
        form = CampaignForm()
    return render(request, 'campaigns/campaign_form.html', {
        'form': form,
        'title': 'Neue Kampagne',
    })


@login_required
def campaign_edit(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    if request.method == 'POST':
        form = CampaignForm(request.POST, instance=campaign)
        if form.is_valid():
            form.save()
            messages.success(request, _('Kampagne aktualisiert.'))
            return redirect('campaigns:campaign_detail', pk=pk)
    else:
        form = CampaignForm(instance=campaign)
    return render(request, 'campaigns/campaign_form.html', {
        'form': form,
        'title': f'Kampagne bearbeiten: {campaign.name}',
        'campaign': campaign,
    })


@login_required
def campaign_archive(request, pk):
    return toggle_archive(request, get_object_or_404(Campaign, pk=pk), 'campaigns:campaign_list')


@login_required
def campaign_delete(request, pk):
    return confirm_delete(request, get_object_or_404(Campaign, pk=pk), 'campaigns:campaign_list')


@login_required
def campaign_detail(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    campaign_contacts = campaign.campaign_contacts.all()

    # Campaign-specific CSV export
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        filename = get_valid_filename(campaign.name)[:100] + '.csv'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.charset = 'utf-8-sig'
        writer = csv.writer(response, delimiter=';')
        writer.writerow(['Account', 'Anrede', 'Name', 'E-Mail', 'Telefon'])
        for cc in campaign_contacts:
            anrede = cc.contact.anrede if cc.contact_id else cc.contact_salutation
            writer.writerow([
                cc.account_name,
                anrede,
                cc.contact_name,
                cc.contact_email,
                cc.contact_phone,
            ])
        return response

    # Allow contact removal only if campaign end date has not been reached
    can_remove_contacts = campaign.end_date >= date.today()

    return render(request, 'campaigns/campaign_detail.html', {
        'campaign': campaign,
        'campaign_contacts': campaign_contacts,
        'can_remove_contacts': can_remove_contacts,
    })


@login_required
def campaign_add_accounts(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)

    if request.method == 'POST':
        account_ids = request.POST.getlist('accounts')
        added = 0
        for account_id in account_ids:
            try:
                account = Account.objects.get(pk=account_id, is_archived=False)
            except Account.DoesNotExist:
                continue
            for contact in get_contacts_for_product(account, campaign.product):
                _, created = CampaignContact.objects.get_or_create(
                    campaign=campaign,
                    contact=contact,
                    defaults={
                        'account': account,
                        'contact_name': contact.name,
                        'contact_salutation': contact.anrede,
                        'contact_email': contact.email,
                        'contact_phone': contact.phone,
                        'account_name': account.name,
                    },
                )
                if created:
                    added += 1
        messages.success(request, _(f'{added} Kontakt(e) zur Kampagne hinzugefügt.'))
        return redirect('campaigns:campaign_detail', pk=pk)

    # GET: show account selection
    if request.user.is_superuser:
        accounts = Account.objects.filter(is_archived=False).select_related('account_type', 'owner')
    else:
        accounts = Account.objects.filter(is_archived=False, owner=request.user).select_related('account_type', 'owner')

    return render(request, 'campaigns/campaign_add_accounts.html', {
        'campaign': campaign,
        'accounts': accounts,
    })


@login_required
def campaign_remove_contact(request, pk, contact_pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    campaign_contact = get_object_or_404(CampaignContact, pk=contact_pk, campaign=campaign)

    # Only allow removal if campaign end date has not been reached
    if campaign.end_date < date.today():
        messages.error(request, _('Kontakte können nicht entfernt werden, da das Enddatum der Kampagne erreicht ist.'))
        return redirect('campaigns:campaign_detail', pk=pk)

    if request.method == 'POST':
        campaign_contact.delete()
        messages.success(request, _('Kontakt aus der Kampagne entfernt.'))
        return redirect('campaigns:campaign_detail', pk=pk)

    return redirect('campaigns:campaign_detail', pk=pk)
