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
from .models import Account, AccountType, Contact, Activity, Todo


@login_required
def account_list(request):
    show_archived = request.GET.get('archived') == '1'
    accounts = Account.objects.filter(is_archived=show_archived).select_related(
        'account_type', 'owner',
    )

    filters = {
        'q': request.GET.get('q', '').strip(),
        'account_type': request.GET.get('account_type', ''),
        'owner': request.GET.get('owner', ''),
        'product': request.GET.get('product', ''),
        'phase': request.GET.get('phase', ''),
    }
    date_fields = []  # list of {'field': ProductField, 'selected': '1'|'0'|''}

    if filters['q']:
        accounts = accounts.filter(name__icontains=filters['q'])
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
        'q': filters['q'],
        'account_type_id': filters['account_type'], 'owner_id': owner_id,
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
    account_type = request.POST.get('account_type', '')
    owner_id = request.POST.get('owner_id', '')
    product_id = request.POST.get('product_id', '')
    phase_id = request.POST.get('phase_id', '')

    if q:
        accounts = accounts.filter(name__icontains=q)
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
