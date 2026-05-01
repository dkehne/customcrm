import csv
import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import get_valid_filename

from campaigns.forms import AccountCampaignForm
from campaigns.models import Campaign, AccountCampaign, CampaignContact
from campaigns.utils import get_contacts_for_product
from contracts.forms import ContractForm, ContractDocumentForm
from contracts.models import Contract, ContractDocument
from core.models import CustomUser
from core.utils import toggle_archive, confirm_delete
from products.forms import AccountProductForm
from products.models import AccountProduct, AccountProductFieldValue, Product, ProductField, ProductPhase

from .forms import AccountForm, ContactForm, ActivityForm, TodoForm
from .models import Account, AccountType, Contact, Activity, Todo, RegionHealthUpload, RegionHealthEntry


# --- Region Health helpers ---

# Mapping: CSV prefix → Account type names (in order of priority)
_PREFIX_TO_ACCOUNT_TYPES = {
    'Bundesland': ['Bundesland'],
    'Landkreis': ['Kreis / Landkreis'],
    'Kreis': ['Kreis / Landkreis'],
    'Region': ['Region'],
    'Städteregion': ['Region'],
    'Stadt': ['Stadt (kreisfrei)', 'Stadt (kreisangehörig)'],
    'Gemeinde': ['Stadt (kreisangehörig)', 'Stadt (kreisfrei)'],
    'Samtgemeinde': ['Stadt (kreisangehörig)', 'Stadt (kreisfrei)'],
}

_KNOWN_PREFIXES = sorted(_PREFIX_TO_ACCOUNT_TYPES.keys(), key=len, reverse=True)


def _strip_prefix(region_name):
    """Return (prefix, bare_name). prefix is '' if no known prefix found."""
    for prefix in _KNOWN_PREFIXES:
        if region_name.startswith(prefix + ' '):
            return prefix, region_name[len(prefix) + 1:].strip()
    return '', region_name


def _calc_ampel(broken_links, hix_low_count, total_pages, outdated_pages):
    """Returns (score: float, color: str)."""
    def pct_score(count, total):
        if total == 0:
            return 1
        pct = count / total * 100
        if pct < 5:
            return 1
        if pct <= 10:
            return 2
        if pct <= 50:
            return 3
        if pct <= 74:
            return 4
        return 5

    def abs_score(val):
        if val < 5:
            return 1
        if val <= 10:
            return 2
        if val <= 50:
            return 3
        if val <= 74:
            return 4
        return 5

    score = (pct_score(outdated_pages, total_pages) + pct_score(hix_low_count, total_pages) + abs_score(broken_links)) / 3
    if score <= 2.0:
        color = 'green'
    elif score <= 3.5:
        color = 'yellow'
    else:
        color = 'red'
    return round(score, 4), color


def _match_account(bare_name, prefix):
    """Try to find exactly one matching Account. Returns Account or None."""
    type_names = _PREFIX_TO_ACCOUNT_TYPES.get(prefix, [])

    def _try_name(name):
        if type_names:
            qs = Account.objects.filter(name=name, account_type__name__in=type_names, is_archived=False)
            if qs.count() == 1:
                return qs.first()
        qs_any = Account.objects.filter(name=name, is_archived=False)
        if qs_any.count() == 1:
            return qs_any.first()
        return None

    # First: bare name (CSV has prefix but account name doesn't)
    result = _try_name(bare_name)
    if result:
        return result
    # Fallback: full name with prefix (accounts were renamed to include prefix)
    if prefix:
        result = _try_name(f"{prefix} {bare_name}")
        if result:
            return result
    return None


def _parse_region_health_csv(file_obj):
    """
    Parse uploaded CSV file. Returns list of dicts with parsed + computed fields.
    Each dict has: region_name, broken_links, hix_low_count, total_pages,
    missing_translation_pages, outdated_pages, mt_budget, active_languages,
    ampel_score, ampel_color, account_id (int or None), matched (bool).
    """
    content = file_obj.read()
    # Try UTF-8-sig first (Excel export), then UTF-8
    for encoding in ('utf-8-sig', 'utf-8', 'latin-1'):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    reader = csv.DictReader(io.StringIO(text))
    entries = []
    for row in reader:
        region_name = row.get('Region', '').strip()
        if not region_name:
            continue
        try:
            broken_links = int(row.get('Anzahl fehlerhafter Links', 0) or 0)
            hix_low_count = int(row.get('Anzahl Seiten mit niedrigem HIX-Wert', 0) or 0)
            total_pages = int(row.get('Anzahl an Seiten', 0) or 0)
            missing_translation_pages = int(row.get('Anzahl Seiten mit mindestens einer fehlenden oder veralteten Übersetzung', 0) or 0)
            outdated_pages = int(row.get('Anzahl veralteter Seiten', 0) or 0)
            mt_budget = int(row.get('MT Budget', 0) or 0)
            active_languages = int(row.get('Anzahl aktiver Sprachen neben der Standard-Sprache', 0) or 0)
        except (ValueError, TypeError):
            continue

        ampel_score, ampel_color = _calc_ampel(broken_links, hix_low_count, total_pages, outdated_pages)
        prefix, bare_name = _strip_prefix(region_name)
        account = _match_account(bare_name, prefix)

        entries.append({
            'region_name': region_name,
            'broken_links': broken_links,
            'hix_low_count': hix_low_count,
            'total_pages': total_pages,
            'missing_translation_pages': missing_translation_pages,
            'outdated_pages': outdated_pages,
            'mt_budget': mt_budget,
            'active_languages': active_languages,
            'ampel_score': ampel_score,
            'ampel_color': ampel_color,
            'account_id': account.pk if account else None,
            'account_name': account.name if account else None,
            'matched': account is not None,
        })
    return entries


@login_required
def account_list(request):
    show_archived = request.GET.get('archived') == '1'
    accounts = Account.objects.filter(is_archived=show_archived).select_related(
        'account_type', 'owner',
    )

    filters = {
        'q': request.GET.get('q', '').strip(),
        'bundesland': request.GET.get('bundesland', ''),
        'account_type': request.GET.get('account_type', ''),
        'owner': request.GET.get('owner', ''),
        'product': request.GET.get('product', ''),
        'phase': request.GET.get('phase', ''),
    }
    date_fields = []  # list of {'field': ProductField, 'selected': '1'|'0'|''}

    if filters['q']:
        accounts = accounts.filter(name__icontains=filters['q'])
    if filters['bundesland']:
        accounts = accounts.filter(bundesland=filters['bundesland'])
    if filters['account_type']:
        accounts = accounts.filter(account_type_id=filters['account_type'])

    # Default to own accounts for non-superusers
    owner_id = filters['owner']
    if 'owner' not in request.GET and not request.user.is_superuser:
        owner_id = str(request.user.pk)

    if owner_id:
        accounts = accounts.filter(owner__isnull=True) if owner_id == 'none' else accounts.filter(owner_id=owner_id)

    # Product and phase filtering (combined to hit the same JOIN)
    products_all = Product.objects.filter(is_archived=False)
    selected_product = None
    phases = []
    bool_fields = []  # list of {'field': ProductField, 'selected': '1'|'0'|''}
    if filters['product']:
        try:
            selected_product = products_all.get(pk=int(filters['product']))
            phases = list(selected_product.phases.all())
            ap_filter = {'account_products__product': selected_product, 'account_products__is_archived': False}
            if filters['phase']:
                ap_filter['account_products__current_phase_id'] = filters['phase']
            accounts = accounts.filter(**ap_filter).distinct()

            # Boolean product field filters
            raw_bool_fields = list(selected_product.fields.filter(
                field_type=ProductField.FieldType.BOOLEAN, is_archived=False
            ).order_by('name'))
            for field in raw_bool_fields:
                val = request.GET.get(f'bf_{field.pk}', '')
                bool_fields.append({'field': field, 'selected': val})
                if val in ('1', '0'):
                    target_bool = val == '1'
                    matching_account_ids = AccountProductFieldValue.objects.filter(
                        field=field,
                        value_bool=target_bool,
                        account_product__product=selected_product,
                        account_product__is_archived=False,
                    ).values_list('account_product__account_id', flat=True)
                    accounts = accounts.filter(pk__in=matching_account_ids)

            # Date product field filters (Ja = date set, Nein = date not set)
            raw_date_fields = list(selected_product.fields.filter(
                field_type=ProductField.FieldType.DATE, is_archived=False
            ).order_by('name'))
            for field in raw_date_fields:
                val = request.GET.get(f'df_{field.pk}', '')
                date_fields.append({'field': field, 'selected': val})
                if val in ('1', '0'):
                    accounts_with_date = AccountProductFieldValue.objects.filter(
                        field=field,
                        value_date__isnull=False,
                        account_product__product=selected_product,
                        account_product__is_archived=False,
                    ).values_list('account_product__account_id', flat=True)
                    if val == '1':
                        accounts = accounts.filter(pk__in=accounts_with_date)
                    else:
                        accounts = accounts.exclude(pk__in=accounts_with_date)
        except (ValueError, Product.DoesNotExist):
            filters['product'] = ''
            filters['phase'] = ''

    return render(request, 'accounts/account_list.html', {
        'accounts': accounts, 'show_archived': show_archived,
        'q': filters['q'], 'bundesland': filters['bundesland'],
        'account_type_id': filters['account_type'], 'owner_id': owner_id,
        'bundesland_choices': Account.BUNDESLAND_CHOICES,
        'account_types': AccountType.objects.filter(is_archived=False),
        'users': CustomUser.objects.filter(is_active=True).order_by('username'),
        'products': products_all,
        'product_id': filters['product'],
        'phases': phases,
        'phase_id': filters['phase'],
        'bool_fields': bool_fields,
        'date_fields': date_fields,
        'campaigns': Campaign.objects.filter(is_archived=False, end_date__gte=timezone.now().date()).order_by('-start_date'),
    })



@login_required
def accounts_to_campaign(request):
    if request.method != 'POST':
        return redirect('accounts:account_list')

    campaign_id = request.POST.get('campaign_id', '').strip()
    if not campaign_id:
        messages.error(request, 'Bitte eine Kampagne auswählen.')
        return redirect('accounts:account_list')

    campaign = get_object_or_404(Campaign, pk=campaign_id, is_archived=False)

    accounts = Account.objects.filter(is_archived=False).prefetch_related('contacts')

    if not request.user.is_superuser:
        accounts = accounts.filter(owner=request.user)

    q = request.POST.get('q', '').strip()
    bundesland = request.POST.get('bundesland', '')
    account_type = request.POST.get('account_type', '')
    owner_id = request.POST.get('owner_id', '')
    product_id = request.POST.get('product_id', '')
    phase_id = request.POST.get('phase_id', '')

    if q:
        accounts = accounts.filter(name__icontains=q)
    if bundesland:
        accounts = accounts.filter(bundesland=bundesland)
    if account_type:
        accounts = accounts.filter(account_type_id=account_type)
    if owner_id == 'none':
        accounts = accounts.filter(owner__isnull=True)
    elif owner_id:
        accounts = accounts.filter(owner_id=owner_id)
    if product_id:
        try:
            product_pk = int(product_id)
            ap_filter = {'account_products__product_id': product_pk, 'account_products__is_archived': False}
            if phase_id:
                ap_filter['account_products__current_phase_id'] = phase_id
            accounts = accounts.filter(**ap_filter).distinct()

            # Boolean product field filters (mirrors account_list logic)
            bool_fields_qs = ProductField.objects.filter(
                product_id=product_pk, field_type=ProductField.FieldType.BOOLEAN, is_archived=False
            )
            for field in bool_fields_qs:
                val = request.POST.get(f'bf_{field.pk}', '')
                if val in ('1', '0'):
                    target_bool = val == '1'
                    matching_account_ids = AccountProductFieldValue.objects.filter(
                        field=field,
                        value_bool=target_bool,
                        account_product__product_id=product_pk,
                        account_product__is_archived=False,
                    ).values_list('account_product__account_id', flat=True)
                    accounts = accounts.filter(pk__in=matching_account_ids)
        except ValueError:
            pass

    added = 0
    for account in accounts:
        for contact in get_contacts_for_product(account, campaign.product):
            _, created = CampaignContact.objects.get_or_create(
                campaign=campaign,
                contact=contact,
                defaults={
                    'account': account,
                    'contact_name': contact.name,
                    'contact_salutation': contact.anrede,
                    'contact_email': contact.email or '',
                    'contact_phone': contact.phone or '',
                    'account_name': account.name,
                    'bundesland': account.bundesland or '',
                },
            )
            if created:
                added += 1

    messages.success(request, f'{added} Kontakt(e) zur Kampagne „{campaign.name}" hinzugefügt.')
    return redirect('campaigns:campaign_detail', pk=campaign.pk)


@login_required
def account_create(request):
    if request.method == 'POST':
        form = AccountForm(request.POST)
        if form.is_valid():
            account = form.save()
            messages.success(request, f'Account "{account.name}" erstellt.')
            return redirect('accounts:account_detail', pk=account.pk)
    else:
        form = AccountForm()
    return render(request, 'accounts/account_form.html', {'form': form, 'title': 'Neuer Account'})


@login_required
def account_edit(request, pk):
    account = get_object_or_404(Account, pk=pk)
    if request.method == 'POST':
        form = AccountForm(request.POST, instance=account)
        if form.is_valid():
            form.save()
            messages.success(request, 'Account aktualisiert.')
            return redirect('accounts:account_detail', pk=pk)
    else:
        form = AccountForm(instance=account)
    return render(request, 'accounts/account_form.html', {
        'form': form, 'title': f'Account bearbeiten: {account.name}', 'account': account,
    })


@login_required
def account_detail(request, pk):
    account = get_object_or_404(
        Account.objects.select_related('account_type', 'owner'), pk=pk,
    )
    # Auto-create AccountCampaign records for system campaigns linked to this account
    system_campaigns = Campaign.objects.filter(
        campaign_contacts__account=account, is_archived=False,
    ).distinct()
    for campaign in system_campaigns:
        AccountCampaign.objects.get_or_create(account=account, campaign=campaign)

    back_url = request.GET.get('back', '') or request.POST.get('back', '')
    if not url_has_allowed_host_and_scheme(back_url, allowed_hosts={request.get_host()}):
        back_url = ''

    if request.method == 'POST' and request.POST.get('action') == 'edit_account':
        account_form = AccountForm(request.POST, instance=account)
        if account_form.is_valid():
            account_form.save()
            messages.success(request, 'Stammdaten aktualisiert.')
            redirect_url = f"{reverse('accounts:account_detail', args=[pk])}"
            if back_url:
                redirect_url += f'?back={back_url}'
            return redirect(redirect_url)
    else:
        account_form = AccountForm(instance=account)

    survey_snapshots = account.survey_snapshots.prefetch_related('features').order_by('year')
    latest_snapshot = survey_snapshots.last()

    latest_region_health = (
        account.region_health_entries.select_related('upload').order_by('-upload__id').first()
    )

    integreat_ap = account.account_products.filter(
        is_archived=False,
        product__name__icontains='integreat',
        current_phase__name__iexact='aktiv',
    ).first()

    return render(request, 'accounts/account_detail.html', {
        'account': account,
        'account_form': account_form,
        'back_url': back_url,
        'contacts': account.contacts.filter(is_archived=False).prefetch_related(
            Prefetch('primary_for_products', queryset=AccountProduct.objects.filter(is_archived=False).select_related('product'))
        ),
        'archived_contacts': account.contacts.filter(is_archived=True),
        'archived_account_products': account.account_products.filter(is_archived=True).select_related('product', 'current_phase'),
        'account_products': account.account_products.filter(is_archived=False).select_related('product', 'current_phase', 'responsible', 'lead_account_product__account').prefetch_related(
            Prefetch('partner_products', queryset=AccountProduct.objects.filter(is_archived=False).select_related('account')),
            'primary_contacts',
        ),
        'contracts': account.contracts.filter(is_archived=False).select_related('contract_type', 'account_product__product'),
        'todos': account.todos.filter(is_completed=False),
        'completed_todos': account.todos.filter(is_completed=True).order_by('-completed_at')[:10],
        'activities': account.activities.exclude(activity_type='task').select_related('inbound_email').prefetch_related('inbound_email__attachments'),
        'account_campaigns': account.account_campaigns.select_related('campaign').order_by('-campaign__start_date'),
        'account_campaign_form': AccountCampaignForm(),
        'contact_form': ContactForm(),
        'account_product_form': AccountProductForm(),
        'contract_form': ContractForm(account=account),
        'document_form': ContractDocumentForm(),
        'activity_form': ActivityForm(account=account),
        'todo_form': TodoForm(current_user=request.user),
        'survey_snapshots': survey_snapshots,
        'latest_snapshot': latest_snapshot,
        'latest_region_health': latest_region_health,
        'integreat_ap': integreat_ap,
    })


@login_required
def account_archive(request, pk):
    return toggle_archive(request, get_object_or_404(Account, pk=pk), 'accounts:account_list')


@login_required
def account_delete(request, pk):
    return confirm_delete(request, get_object_or_404(Account, pk=pk), 'accounts:account_list')


@login_required
def account_assign_owner(request, pk):
    account = get_object_or_404(Account, pk=pk)
    account.owner = request.user
    account.save()
    messages.success(request, f'Account "{account.name}" Ihnen zugewiesen.')
    return redirect('accounts:account_detail', pk=pk)


# Contact views
@login_required
def contact_list(request):
    q = request.GET.get('q', '').strip()
    contacts = Contact.objects.filter(is_archived=False, account__is_archived=False).select_related('account', 'account__account_type')
    if not request.user.is_superuser:
        contacts = contacts.filter(account__owner=request.user)
    if q:
        contacts = contacts.filter(Q(name__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q))
    contacts = contacts.order_by('account__name', '-is_primary', 'name')
    return render(request, 'accounts/contact_list.html', {'contacts': contacts, 'q': q})


@login_required
def contact_add(request, account_pk):
    account = get_object_or_404(Account, pk=account_pk)
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            contact = form.save(commit=False)
            contact.account = account
            contact.save()
            if contact.is_primary:
                ap_ids = request.POST.getlist('primary_products')
                if ap_ids:
                    valid_aps = AccountProduct.objects.filter(
                        pk__in=ap_ids, account=account, is_archived=False,
                    )
                    contact.primary_for_products.set(valid_aps)
            messages.success(request, f'Kontakt "{contact.name}" hinzugefügt.')
    return redirect('accounts:account_detail', pk=account_pk)


@login_required
def contact_edit(request, pk):
    contact = get_object_or_404(Contact, pk=pk)
    account_products = AccountProduct.objects.filter(
        account=contact.account, is_archived=False,
    ).select_related('product')
    if request.method == 'POST':
        form = ContactForm(request.POST, instance=contact)
        if form.is_valid():
            contact = form.save()
            if contact.is_primary:
                ap_ids = request.POST.getlist('primary_products')
                valid_aps = AccountProduct.objects.filter(
                    pk__in=ap_ids, account=contact.account, is_archived=False,
                )
                contact.primary_for_products.set(valid_aps)
            else:
                contact.primary_for_products.clear()
            messages.success(request, 'Kontakt aktualisiert.')
            return redirect('accounts:account_detail', pk=contact.account_id)
    else:
        form = ContactForm(instance=contact)
    assigned_ids = list(contact.primary_for_products.values_list('pk', flat=True))
    return render(request, 'accounts/contact_edit.html', {
        'form': form,
        'contact': contact,
        'account_products': account_products,
        'assigned_product_ids': assigned_ids,
    })


@login_required
def contact_archive(request, pk):
    contact = get_object_or_404(Contact, pk=pk)
    return toggle_archive(request, contact, ('accounts:account_detail', {'pk': contact.account_id}))


@login_required
def contact_delete(request, pk):
    contact = get_object_or_404(Contact, pk=pk)
    return confirm_delete(request, contact, ('accounts:account_detail', {'pk': contact.account_id}))


# Account Product views
@login_required
def account_product_add(request, account_pk):
    account = get_object_or_404(Account, pk=account_pk)
    if request.method == 'POST':
        form = AccountProductForm(request.POST)
        if form.is_valid():
            ap = form.save(commit=False)
            ap.account = account
            existing = AccountProduct.objects.filter(account=account, product=ap.product).first()
            if existing and existing.is_archived:
                reactivate_url = reverse('accounts:account_product_archive', args=[existing.pk])
                messages.error(
                    request,
                    format_html(
                        'Produkt "{}" existiert bereits als archivierter Eintrag. '
                        '<a href="{}">Jetzt reaktivieren</a>.',
                        ap.product.name,
                        reactivate_url,
                    ),
                )
            elif existing:
                messages.error(request, f'Produkt "{ap.product.name}" ist bereits diesem Account zugeordnet.')
            else:
                try:
                    with transaction.atomic():
                        if not ap.current_phase_id:
                            first_phase = ap.product.phases.first()
                            if first_phase:
                                ap.current_phase = first_phase
                        ap.save()
                        for field in ap.product.fields.filter(is_archived=False):
                            AccountProductFieldValue.objects.get_or_create(account_product=ap, field=field)
                    messages.success(request, f'Produkt "{ap.product.name}" zugeordnet.')
                except IntegrityError:
                    messages.error(request, f'Produkt "{ap.product.name}" ist bereits diesem Account zugeordnet.')
    return redirect('accounts:account_detail', pk=account_pk)


@login_required
def account_product_edit(request, pk):
    ap = get_object_or_404(AccountProduct.objects.select_related('product', 'account', 'lead_account_product__account'), pk=pk)
    fields = ap.product.fields.filter(is_archived=False)
    field_values = {fv.field_id: fv for fv in ap.field_values.select_related('field')}
    # Check if account has more than one active product
    active_products_count = ap.account.account_products.filter(is_archived=False).count()
    show_responsible = active_products_count > 1
    # Other AccountProducts for the same product (for Produktverbund selection)
    lead_options = AccountProduct.objects.filter(
        product=ap.product, is_archived=False,
    ).exclude(pk=ap.pk).select_related('account').order_by('account__name')

    if request.method == 'POST':
        # Handle Produktverbund (lead) selection
        lead_id = request.POST.get('lead_account_product') or None
        if lead_id:
            try:
                lead = lead_options.get(pk=int(lead_id))
                ap.lead_account_product = lead
                # Sync phase from lead
                if lead.current_phase_id:
                    ap.current_phase_id = lead.current_phase_id
            except (ValueError, AccountProduct.DoesNotExist):
                pass
        else:
            ap.lead_account_product = None
            phase_id = request.POST.get('current_phase')
            if phase_id:
                try:
                    new_phase = ap.product.phases.get(pk=int(phase_id))
                except (ValueError, ap.product.phases.model.DoesNotExist):
                    new_phase = None
                if new_phase is None:
                    pass  # invalid or foreign phase_id – ignore
                elif new_phase.name == 'Beendet':
                    # Only allow switching to "Beendet" from "Aktiv"
                    if ap.current_phase and ap.current_phase.name == 'Aktiv':
                        ap.current_phase = new_phase
                        ended_at = request.POST.get('ended_at') or None
                        ap.ended_at = ended_at
                        ap.ended_reason = request.POST.get('ended_reason') or None
                    else:
                        messages.error(
                            request,
                            'Phase „Beendet" ist nur aus der Phase „Aktiv" heraus wählbar.',
                        )
                        return redirect('accounts:account_detail', pk=ap.account_id)
                else:
                    ap.current_phase_id = phase_id
                    # Clear ended fields if moving away from "Beendet"
                    if ap.ended_at or ap.ended_reason:
                        ap.ended_at = None
                        ap.ended_reason = None

        # Handle responsible field
        if show_responsible:
            responsible_id = request.POST.get('responsible')
            ap.responsible_id = responsible_id if responsible_id else None

        try:
            ap.full_clean()
        except ValidationError as e:
            for field, errors in e.message_dict.items():
                for error in errors:
                    messages.error(request, error)
            return redirect('accounts:account_product_edit', pk=ap.pk)

        ap.save()

        if not ap.lead_account_product_id:
            for field in fields:
                fv, _ = AccountProductFieldValue.objects.get_or_create(account_product=ap, field=field)
                post_key = f'field_{field.pk}'
                val = request.POST.get(post_key)
                if field.field_type == ProductField.FieldType.DATE:
                    fv.value_date = val or None
                elif field.field_type == ProductField.FieldType.INTEGER:
                    fv.value_int = int(val) if val else None
                elif field.field_type == ProductField.FieldType.BOOLEAN:
                    fv.value_bool = post_key in request.POST
                fv.save()

        messages.success(request, 'Produkt-Zuordnung aktualisiert.')
        return redirect('accounts:account_detail', pk=ap.account_id)

    return render(request, 'accounts/account_product_edit.html', {
        'account_product': ap,
        'phases': ap.product.phases.all(),
        'field_data': [{'field': f, 'value': field_values.get(f.pk)} for f in fields],
        'show_responsible': show_responsible,
        'users': CustomUser.objects.filter(is_active=True).order_by('username') if show_responsible else [],
        'contacts': ap.account.contacts.filter(is_archived=False).order_by('-is_primary', 'name') if show_responsible else [],
        'lead_options': lead_options,
        'partner_products': ap.partner_products.filter(is_archived=False).select_related('account'),
    })


@login_required
def account_product_archive(request, pk):
    ap = get_object_or_404(AccountProduct, pk=pk)
    return toggle_archive(request, ap, ('accounts:account_detail', {'pk': ap.account_id}), name_attr=None)


@login_required
def account_product_delete(request, pk):
    ap = get_object_or_404(AccountProduct, pk=pk)
    return confirm_delete(request, ap, ('accounts:account_detail', {'pk': ap.account_id}), name_attr=None)


# Contract views
@login_required
def contract_add(request, account_pk):
    account = get_object_or_404(Account, pk=account_pk)
    if request.method == 'POST':
        form = ContractForm(request.POST, account=account)
        if form.is_valid():
            contract = form.save(commit=False)
            contract.account = account
            contract.save()
            for f in request.FILES.getlist('documents'):
                if f.name.lower().endswith('.pdf'):
                    f.name = get_valid_filename(f.name)[:100]
                    ContractDocument.objects.create(contract=contract, file=f)
            messages.success(request, 'Vertrag erstellt.')
    return redirect('accounts:account_detail', pk=account_pk)


@login_required
def contract_edit(request, pk):
    contract = get_object_or_404(
        Contract.objects.select_related('account', 'account_product', 'contract_type'), pk=pk,
    )
    if request.method == 'POST':
        form = ContractForm(request.POST, instance=contract, account=contract.account)
        if form.is_valid():
            form.save()
            for f in request.FILES.getlist('documents'):
                if f.name.lower().endswith('.pdf'):
                    f.name = get_valid_filename(f.name)[:100]
                    ContractDocument.objects.create(contract=contract, file=f)
            messages.success(request, 'Vertrag aktualisiert.')
            return redirect('accounts:account_detail', pk=contract.account_id)
    else:
        form = ContractForm(instance=contract, account=contract.account)
    return render(request, 'accounts/contract_edit.html', {
        'form': form, 'contract': contract, 'documents': contract.documents.all(),
    })


@login_required
def contract_archive(request, pk):
    contract = get_object_or_404(Contract, pk=pk)
    return toggle_archive(request, contract, ('accounts:account_detail', {'pk': contract.account_id}), name_attr=None)


@login_required
def contract_delete(request, pk):
    contract = get_object_or_404(Contract, pk=pk)
    return confirm_delete(request, contract, ('accounts:account_detail', {'pk': contract.account_id}), name_attr=None)


@login_required
def contract_document_delete(request, pk):
    doc = get_object_or_404(ContractDocument.objects.select_related('contract'), pk=pk)
    contract = doc.contract
    doc.file.delete()
    doc.delete()
    messages.success(request, 'Dokument gelöscht.')
    return redirect('accounts:contract_edit', pk=contract.pk)


# Activity views
@login_required
def activity_add(request, account_pk):
    account = get_object_or_404(Account, pk=account_pk)
    if request.method == 'POST':
        form = ActivityForm(request.POST, account=account)
        if form.is_valid():
            activity = form.save(commit=False)
            activity.account = account
            activity.created_by = request.user
            activity.save()
            messages.success(request, 'Aktivität hinzugefügt.')
    return redirect('accounts:account_detail', pk=account_pk)


@login_required
def activity_delete(request, pk):
    activity = get_object_or_404(Activity, pk=pk)
    return confirm_delete(request, activity, ('accounts:account_detail', {'pk': activity.account_id}), name_attr='subject')


# Todo views
@login_required
def todo_add(request, account_pk):
    account = get_object_or_404(Account, pk=account_pk)
    if request.method == 'POST':
        form = TodoForm(request.POST, request.FILES, current_user=request.user)
        if form.is_valid():
            todo = form.save(commit=False)
            todo.account = account
            todo.created_by = request.user
            if not todo.assigned_to_id:
                todo.assigned_to = request.user
            todo.save()
            messages.success(request, 'Aufgabe hinzugefügt.')
    return redirect('accounts:account_detail', pk=account_pk)


@login_required
def todo_edit(request, pk):
    todo = get_object_or_404(Todo.objects.select_related('account'), pk=pk)
    if request.method == 'POST':
        form = TodoForm(request.POST, request.FILES, instance=todo)
        if form.is_valid():
            form.save()
            messages.success(request, 'Aufgabe aktualisiert.')
            return redirect('accounts:account_detail', pk=todo.account_id)
    else:
        form = TodoForm(instance=todo)
    return render(request, 'accounts/todo_edit.html', {'form': form, 'todo': todo})



@login_required
def todo_complete(request, pk):
    todo = get_object_or_404(Todo, pk=pk)
    if request.method == 'POST' and not todo.is_completed:
        todo.is_completed = True
        todo.completed_at = timezone.now()
        todo.save()
        messages.success(request, f'Aufgabe "{todo.title}" als erledigt markiert.')
    return redirect('accounts:account_detail', pk=todo.account_id)


@login_required
def todo_delete(request, pk):
    todo = get_object_or_404(Todo, pk=pk)
    return confirm_delete(request, todo, ('accounts:account_detail', {'pk': todo.account_id}))


# Account Campaign views
@login_required
def account_campaign_add(request, account_pk):
    account = get_object_or_404(Account, pk=account_pk)
    if request.method == 'POST':
        form = AccountCampaignForm(request.POST, request.FILES)
        if form.is_valid():
            ac = form.save(commit=False)
            ac.account = account
            ac.save()
            messages.success(request, f'Kampagne "{ac.name}" hinzugefügt.')
    return redirect('accounts:account_detail', pk=account_pk)


@login_required
def account_campaign_edit(request, pk):
    ac = get_object_or_404(AccountCampaign, pk=pk)
    if not ac.is_external:
        messages.error(request, 'Nur externe Kampagnen können bearbeitet werden.')
        return redirect('accounts:account_detail', pk=ac.account_id)
    if request.method == 'POST':
        form = AccountCampaignForm(request.POST, request.FILES, instance=ac)
        if form.is_valid():
            form.save()
            messages.success(request, f'Kampagne "{ac.name}" aktualisiert.')
    return redirect('accounts:account_detail', pk=ac.account_id)


@login_required
def account_campaign_toggle_success(request, pk):
    ac = get_object_or_404(AccountCampaign, pk=pk)
    if request.method == 'POST':
        ac.is_successful = not ac.is_successful
        ac.save()
    return redirect('accounts:account_detail', pk=ac.account_id)


@login_required
def account_campaign_delete(request, pk):
    ac = get_object_or_404(AccountCampaign, pk=pk)
    account_pk = ac.account_id
    if request.method == 'POST' and ac.is_external:
        ac.delete()
        messages.success(request, 'Kampagne gelöscht.')
    return redirect('accounts:account_detail', pk=account_pk)


@login_required
def region_health_upload(request):
    if not request.user.is_superuser:
        messages.error(request, 'Keine Berechtigung.')
        return redirect('core:dashboard')

    if request.method == 'POST':
        uploaded_file = request.FILES.get('csv_file')
        if not uploaded_file:
            messages.error(request, 'Bitte eine CSV-Datei auswählen.')
            return render(request, 'accounts/region_health_upload.html', {})

        entries = _parse_region_health_csv(uploaded_file)
        if not entries:
            messages.error(request, 'Die CSV-Datei enthält keine verwertbaren Zeilen.')
            return render(request, 'accounts/region_health_upload.html', {})

        request.session['region_health_entries'] = entries
        request.session['region_health_filename'] = uploaded_file.name
        return redirect('accounts:region_health_preview')

    return render(request, 'accounts/region_health_upload.html', {})


@login_required
def region_health_preview(request):
    if not request.user.is_superuser:
        messages.error(request, 'Keine Berechtigung.')
        return redirect('core:dashboard')

    entries = request.session.get('region_health_entries')
    if not entries:
        messages.error(request, 'Keine Daten zum Bestätigen. Bitte zuerst eine CSV hochladen.')
        return redirect('accounts:region_health_upload')

    filename = request.session.get('region_health_filename', 'upload.csv')

    if request.method == 'POST':
        matched = [e for e in entries if e['matched']]
        upload = RegionHealthUpload.objects.create(
            uploaded_by=request.user,
            filename=filename,
            rows_total=len(entries),
            rows_matched=len(matched),
        )
        for e in entries:
            RegionHealthEntry.objects.create(
                upload=upload,
                account_id=e['account_id'],
                region_name=e['region_name'],
                broken_links=e['broken_links'],
                hix_low_count=e['hix_low_count'],
                total_pages=e['total_pages'],
                missing_translation_pages=e['missing_translation_pages'],
                outdated_pages=e['outdated_pages'],
                mt_budget=e['mt_budget'],
                active_languages=e['active_languages'],
                ampel_score=e['ampel_score'],
                ampel_color=e['ampel_color'],
            )
        del request.session['region_health_entries']
        request.session.pop('region_health_filename', None)
        unmatched_count = len(entries) - len(matched)
        if unmatched_count:
            messages.success(
                request,
                f'Upload gespeichert: {len(matched)} von {len(entries)} Einträgen gematchet. '
                f'{unmatched_count} ungematcht – bitte manuell zuordnen.',
            )
            return redirect('accounts:region_health_unmatched', upload_pk=upload.pk)
        messages.success(request, f'Upload gespeichert: alle {len(entries)} Einträge gematchet.')
        return redirect('core:dashboard')

    matched_count = sum(1 for e in entries if e['matched'])
    unmatched_entries = [e for e in entries if not e['matched']]
    return render(request, 'accounts/region_health_upload_preview.html', {
        'entries': entries,
        'filename': filename,
        'total': len(entries),
        'matched_count': matched_count,
        'unmatched_count': len(unmatched_entries),
        'unmatched_entries': unmatched_entries,
    })


@login_required
def region_health_unmatched(request, upload_pk):
    if not request.user.is_superuser:
        messages.error(request, 'Keine Berechtigung.')
        return redirect('core:dashboard')

    upload = get_object_or_404(RegionHealthUpload, pk=upload_pk)
    unmatched = upload.entries.filter(account__isnull=True).order_by('region_name')

    if request.method == 'POST':
        assigned = 0
        for key, account_id in request.POST.items():
            if not key.startswith('account_id_') or not account_id:
                continue
            entry_id = key[len('account_id_'):]
            try:
                entry = RegionHealthEntry.objects.get(pk=entry_id, upload=upload, account__isnull=True)
                account = Account.objects.get(pk=account_id, is_archived=False)
                entry.account = account
                entry.save()
                assigned += 1
            except (RegionHealthEntry.DoesNotExist, Account.DoesNotExist):
                pass
        if assigned:
            messages.success(request, f'{assigned} Einträge zugeordnet.')
        return redirect('accounts:region_health_unmatched', upload_pk=upload_pk)

    return render(request, 'accounts/region_health_unmatched.html', {
        'upload': upload,
        'unmatched': unmatched,
        'all_accounts': Account.objects.filter(
            is_archived=False,
            account_products__is_archived=False,
            account_products__product__name__iexact='integreat',
            account_products__current_phase__name='Aktiv',
        ).distinct().order_by('name'),
    })


@login_required
def account_search(request):
    q = request.GET.get('q', '').strip()
    accounts = Account.objects.filter(is_archived=False).select_related('account_type')
    if q:
        accounts = accounts.filter(name__icontains=q)
    accounts = accounts.order_by('name')[:10]
    return JsonResponse(
        [{'id': a.pk, 'name': a.name, 'type': a.account_type.name if a.account_type else ''} for a in accounts],
        safe=False,
    )
