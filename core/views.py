from datetime import date, timedelta
from django.conf import settings
from django.http import FileResponse, Http404, HttpRequest
import os

from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from collections import defaultdict

from django.db.models import Avg, Count, Min, Q, OuterRef, Subquery, Sum
from django.http import HttpRequest
from django.shortcuts import render, redirect

from accounts.models import Account, Activity, RegionHealthEntry, RegionHealthUpload, SurveySnapshot, Todo
from contracts.models import Contract
from products.models import AccountProduct, AccountProductFieldValue, Product, ProductField


def login_view(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    oidc_enabled = getattr(django_settings, 'OIDC_ENABLED', False)
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect(request.GET.get('next', 'core:dashboard'))
        return render(request, 'core/login.html', {
            'form': {'errors': True},
            'oidc_enabled': oidc_enabled,
        })
    return render(request, 'core/login.html', {'oidc_enabled': oidc_enabled})


def logout_view(request):
    logout(request)
    return redirect('core:login')


@login_required
def dashboard(request):
    user = request.user
    if user.is_superuser:
        today = date.today()
        current_year = today.year
        contracts_by_type = (
            Contract.objects.filter(is_archived=False)
            .values('contract_type__name')
            .annotate(
                count=Count('id'),
                new_this_year=Count('id', filter=Q(start_date__year=current_year)),
            )
            .order_by('-count')
        )
        products_by_phase = (
            AccountProduct.objects.filter(is_archived=False)
            .values('product__name', 'current_phase__name')
            .annotate(count=Count('id'))
            .order_by('product__name', 'current_phase__name')
        )
        pipeline_per_user = (
            AccountProduct.objects.filter(
                is_archived=False,
                account__is_archived=False,
                current_phase__is_final_phase=False,
                account__owner__isnull=False,
            )
            .values('account__owner__id', 'account__owner__username', 'account__owner__first_name', 'account__owner__last_name')
            .annotate(count=Count('account__auto_id', distinct=True))
            .order_by('-count')
        )
        pipeline_by_owner = {row['account__owner__id']: row['count'] for row in pipeline_per_user}
        total_accounts = Account.objects.filter(is_archived=False).count()
        total_contracts = Contract.objects.filter(is_archived=False).count()

        # Widget: Malte Größenverteilung (Aktiv)
        malte_groesse_raw = (
            AccountProductFieldValue.objects
            .filter(
                field__name__iexact='Größe',
                field__product__name__iexact='Malte',
                account_product__is_archived=False,
                account_product__account__is_archived=False,
                account_product__current_phase__name='Aktiv',
            )
            .values('value_int')
            .annotate(count=Count('id'))
            .order_by('value_int')
        )
        malte_groesse = {row['value_int']: row['count'] for row in malte_groesse_raw}

        # Widget: Auslaufende Verträge (fixed end date, within 90 days)
        in_90_days = today + timedelta(days=90)
        expiring_contracts_raw = (
            Contract.objects
            .filter(is_archived=False, is_self_cancelling=True, start_date__lte=in_90_days)
            .select_related('account', 'account__owner', 'contract_type')
        )
        expiring_contracts = []
        for c in expiring_contracts_raw:
            end = c.initial_end_date()
            if today <= end <= in_90_days:
                expiring_contracts.append({'contract': c, 'end_date': end, 'days_until': (end - today).days})
        expiring_contracts.sort(key=lambda x: x['end_date'])

        # Widget: Inaktive Partner (active contract, last activity > 90 days ago or never)
        cutoff = today - timedelta(days=90)
        last_activity_sub = Activity.objects.filter(
            account=OuterRef('pk'),
        ).order_by('-date').values('date')[:1]
        inactive_accounts = (
            Account.objects
            .filter(is_archived=False, contracts__is_archived=False)
            .distinct()
            .annotate(last_activity_date=Subquery(last_activity_sub))
            .filter(Q(last_activity_date__lt=cutoff) | Q(last_activity_date__isnull=True))
            .select_related('owner')
            .order_by('last_activity_date')
        )

        return render(request, 'core/dashboard_superuser.html', {
            'contracts_by_type': contracts_by_type,
            'products_by_phase': products_by_phase,
            'total_accounts': total_accounts,
            'total_contracts': total_contracts,
            'current_year': current_year,
            'today': today,
            'pipeline_per_user': pipeline_per_user,
            'expiring_contracts': expiring_contracts,
            'inactive_accounts': inactive_accounts,
            'malte_groesse': malte_groesse,
        })
    else:
        return render(request, 'core/dashboard_verwalter.html',
                      _my_accounts_context(request.user, request))


def _my_accounts_context(user, request):
    """Build the context for the 'Meine Kunden' view (used by Verwalter dashboard and superuser page)."""
    products = Product.objects.filter(is_archived=False)
    selected_product_id = request.GET.get('product', '')
    selected_product = None
    fields = []
    rows = []

    if selected_product_id:
        try:
            selected_product = products.get(pk=int(selected_product_id))
        except (ValueError, Product.DoesNotExist):
            pass

    if not selected_product:
        if user.default_dashboard_product and not user.default_dashboard_product.is_archived:
            selected_product = user.default_dashboard_product
        else:
            selected_product = products.first()

    if selected_product:
        fields = list(
            selected_product.fields.filter(is_archived=False, show_on_dashboard=True).order_by('name')
        )
        active_products_count = AccountProduct.objects.filter(
            account=OuterRef('account'),
            is_archived=False,
        ).values('account').annotate(cnt=Count('id')).values('cnt')

        last_activity_subquery = Activity.objects.filter(
            account=OuterRef('account'),
        ).order_by('-date').values('date')[:1]

        partner_count_subquery = AccountProduct.objects.filter(
            lead_account_product=OuterRef('pk'),
            is_archived=False,
        ).values('lead_account_product').annotate(cnt=Count('id')).values('cnt')

        account_products = (
            AccountProduct.objects
            .annotate(
                active_product_count=Subquery(active_products_count),
                last_activity_date=Subquery(last_activity_subquery),
                partner_count=Subquery(partner_count_subquery),
            )
            .filter(
                account__is_archived=False,
                product=selected_product,
                is_archived=False,
                current_phase__name__iexact='Aktiv',
                lead_account_product__isnull=True,
            )
            .filter(
                Q(responsible=user) |
                Q(responsible__isnull=True, account__owner=user, active_product_count=1)
            )
            .select_related('account', 'account__account_type', 'current_phase', 'responsible')
            .prefetch_related('field_values', 'field_values__field')
            .order_by('account__name')
        )

        is_integreat = selected_product.name.lower() == 'integreat'
        ampel_by_account = {}
        if is_integreat:
            latest_upload = RegionHealthUpload.objects.first()
            if latest_upload:
                account_ids = [ap.account_id for ap in account_products]
                ampel_entries = RegionHealthEntry.objects.filter(
                    upload=latest_upload,
                    account_id__in=account_ids,
                ).values('account_id', 'ampel_color')
                ampel_by_account = {e['account_id']: e['ampel_color'] for e in ampel_entries}

        for ap in account_products:
            value_map = {fv.field_id: fv for fv in ap.field_values.all()}
            field_cells = []
            for f in fields:
                fv = value_map.get(f.pk)
                if fv is None:
                    field_cells.append({'type': 'empty'})
                elif f.field_type == ProductField.FieldType.BOOLEAN:
                    field_cells.append({'type': 'bool', 'value': fv.value_bool})
                elif f.field_type == ProductField.FieldType.INTEGER:
                    field_cells.append({'type': 'int', 'value': fv.value_int})
                elif f.field_type == ProductField.FieldType.DATE:
                    field_cells.append({'type': 'date', 'value': fv.value_date})
                else:
                    field_cells.append({'type': 'empty'})
            lad = ap.last_activity_date
            if lad:
                days = (date.today() - lad.date()).days
                last_activity = '<60 Tage' if days < 60 else f'{days} Tage'
            else:
                last_activity = '–'
            rows.append({
                'account_product': ap,
                'field_cells': field_cells,
                'last_activity': last_activity,
                'ampel': ampel_by_account.get(ap.account_id),
                'partner_count': ap.partner_count or 0,
            })

    return {
        'products': products,
        'selected_product': selected_product,
        'fields': fields,
        'rows': rows,
        'show_ampel': selected_product is not None and selected_product.name.lower() == 'integreat',
    }


@login_required
def my_accounts(request):
    return render(request, 'core/dashboard_verwalter.html', _my_accounts_context(request.user, request))


@login_required
def password_change(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Passwort erfolgreich geändert.')
            return redirect('emails:profile_overview')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'core/password_change.html', {
        'form': form,
    })


@login_required
def protected_media(request: HttpRequest, path: str) -> FileResponse:
    """
    Serve media files only to authenticated users.
    """
    media_root = django_settings.MEDIA_ROOT
    normalized_path = os.path.normpath(path).lstrip(os.sep)
    full_path = os.path.abspath(os.path.join(media_root, normalized_path))
    if not full_path.startswith(os.path.abspath(media_root)):
        raise Http404("File not found")
    if not os.path.exists(full_path):
        raise Http404("File not found")
    return FileResponse(open(full_path, 'rb'), as_attachment=False)


@login_required
def pipeline(request):
    user = request.user
    today = date.today()

    last_activity_subquery = Activity.objects.filter(
        account=OuterRef('account'),
    ).order_by('-date').values('date')[:1]

    active_products_count = AccountProduct.objects.filter(
        account=OuterRef('account'),
        is_archived=False,
    ).values('account').annotate(cnt=Count('id')).values('cnt')

    account_products = (
        AccountProduct.objects
        .annotate(
            last_activity_date=Subquery(last_activity_subquery),
            active_product_count=Subquery(active_products_count),
        )
        .filter(
            account__is_archived=False,
            is_archived=False,
        )
        .exclude(current_phase__is_final_phase=True)
        .filter(
            Q(responsible=user) |
            Q(responsible__isnull=True, account__owner=user, active_product_count=1)
        )
        .select_related('account', 'account__account_type', 'current_phase', 'product')
        .order_by('last_activity_date')
    )

    rows = []
    for ap in account_products:
        lad = ap.last_activity_date
        if lad:
            days = (today - lad.date()).days
        else:
            days = None
        rows.append({'account_product': ap, 'days': days})

    return render(request, 'core/pipeline.html', {
        'rows': rows,
        'today': today,
    })


@login_required
def todo_list(request):
    user = request.user
    today = date.today()
    two_weeks_from_now = today + timedelta(days=14)

    todos = Todo.objects.filter(
        assigned_to=user,
        account__is_archived=False,
        is_completed=False,
    ).select_related('account', 'created_by').order_by('due_date', 'created_at')

    # Split into upcoming (next 2 weeks) and other
    upcoming_todos = [t for t in todos if t.due_date and t.due_date <= two_weeks_from_now]
    other_todos = [t for t in todos if not t.due_date or t.due_date > two_weeks_from_now]

    return render(request, 'core/todo_list.html', {
        'upcoming_todos': upcoming_todos,
        'other_todos': other_todos,
        'today': today,
    })


def _compute_ampel_per_manager():
    """Compute Integreat Ampelbewertung table data grouped by account manager."""
    today = date.today()
    latest_upload = RegionHealthUpload.objects.first()
    if not latest_upload:
        return [], None, None

    entries = (
        RegionHealthEntry.objects
        .filter(upload=latest_upload, account__isnull=False, account__owner__isnull=False)
        .select_related('account__owner')
    )

    oldest_contracts = (
        Contract.objects
        .filter(is_archived=False, is_self_cancelling=False, account__owner__isnull=False)
        .values('account_id', 'account__owner_id')
        .annotate(oldest_start=Min('start_date'))
    )
    owner_contract_starts = defaultdict(list)
    for row in oldest_contracts:
        owner_contract_starts[row['account__owner_id']].append(row['oldest_start'])
    avg_age_by_owner = {
        owner_id: sum((today - s).days for s in starts) / len(starts) / 365.25
        for owner_id, starts in owner_contract_starts.items()
    }

    support_rows = (
        AccountProductFieldValue.objects
        .filter(
            field__name__icontains='Supportstunden',
            field__field_type='integer',
            account_product__is_archived=False,
            account_product__account__is_archived=False,
            account_product__account__owner__isnull=False,
            value_int__isnull=False,
        )
        .values('account_product__account__owner_id')
        .annotate(total=Sum('value_int'))
    )
    supportstunden_per_owner = {
        row['account_product__account__owner_id']: row['total']
        for row in support_rows
    }

    pipeline_per_user = (
        AccountProduct.objects.filter(
            is_archived=False,
            account__is_archived=False,
            current_phase__is_final_phase=False,
            account__owner__isnull=False,
        )
        .values('account__owner__id')
        .annotate(count=Count('account__auto_id', distinct=True))
    )
    pipeline_by_owner = {row['account__owner__id']: row['count'] for row in pipeline_per_user}

    manager_data = {}
    for entry in entries:
        owner = entry.account.owner
        key = owner.pk
        if key not in manager_data:
            name = owner.get_full_name() or owner.username
            manager_data[key] = {'manager': name, 'green': 0, 'yellow': 0, 'red': 0}
        manager_data[key][entry.ampel_color] += 1
    for owner_pk, data in manager_data.items():
        data['total'] = data['green'] + data['yellow'] + data['red']
        avg_years = avg_age_by_owner.get(owner_pk)
        data['avg_contract_age'] = round(avg_years, 1) if avg_years is not None else None
        data['supportstunden'] = supportstunden_per_owner.get(owner_pk)
        data['pipeline'] = pipeline_by_owner.get(owner_pk, 0)
    ampel_per_manager = sorted(manager_data.values(), key=lambda x: (-x['green'], x['manager']))

    if not ampel_per_manager:
        return [], None, None

    n = len(ampel_per_manager)
    age_values = [r['avg_contract_age'] for r in ampel_per_manager if r['avg_contract_age'] is not None]
    support_values = [r['supportstunden'] for r in ampel_per_manager if r['supportstunden'] is not None]
    ampel_sum_row = {
        'green': sum(r['green'] for r in ampel_per_manager),
        'yellow': sum(r['yellow'] for r in ampel_per_manager),
        'red': sum(r['red'] for r in ampel_per_manager),
        'total': sum(r['total'] for r in ampel_per_manager),
        'avg_contract_age': round(sum(age_values) / len(age_values), 1) if age_values else None,
        'supportstunden': sum(support_values) if support_values else None,
        'pipeline': sum(r['pipeline'] for r in ampel_per_manager),
    }
    ampel_avg_row = {
        'green': round(ampel_sum_row['green'] / n, 1),
        'yellow': round(ampel_sum_row['yellow'] / n, 1),
        'red': round(ampel_sum_row['red'] / n, 1),
        'total': round(ampel_sum_row['total'] / n, 1),
        'avg_contract_age': round(sum(age_values) / len(age_values), 1) if age_values else None,
        'supportstunden': round(sum(support_values) / len(support_values), 1) if support_values else None,
        'pipeline': round(ampel_sum_row['pipeline'] / n, 1),
    }
    return ampel_per_manager, ampel_sum_row, ampel_avg_row


@login_required
def analyse(request):
    ampel_per_manager, ampel_sum_row, ampel_avg_row = _compute_ampel_per_manager()

    satisfaction_trend = (
        SurveySnapshot.objects
        .values('year')
        .annotate(
            avg_overall=Avg('satisfaction_overall'),
            avg_app=Avg('satisfaction_app'),
            avg_cms=Avg('satisfaction_cms'),
            avg_support=Avg('satisfaction_support'),
            count=Count('id'),
        )
        .order_by('year')
    )

    bundesland_map = dict(Account.BUNDESLAND_CHOICES)
    satisfaction_by_bundesland_qs = (
        SurveySnapshot.objects
        .filter(account__bundesland__gt='', satisfaction_overall__isnull=False)
        .values('account__bundesland')
        .annotate(
            avg_overall=Avg('satisfaction_overall'),
            count=Count('id'),
        )
        .order_by('-avg_overall')
    )
    satisfaction_by_bundesland = [
        {**row, 'bundesland_display': bundesland_map.get(row['account__bundesland'], row['account__bundesland'])}
        for row in satisfaction_by_bundesland_qs
    ]

    # Integreat boolean field stats (active/final phase accounts)
    integreat_field_stats = []
    integreat_active_total = 0
    integreat = Product.objects.filter(name__iexact='integreat', is_archived=False).first()
    if integreat:
        final_phases = integreat.phases.filter(is_final_phase=True)
        active_aps = AccountProduct.objects.filter(
            product=integreat,
            is_archived=False,
            current_phase__in=final_phases,
            lead_account_product__isnull=True,
        )
        integreat_active_total = active_aps.count()
        bool_fields = integreat.fields.filter(field_type=ProductField.FieldType.BOOLEAN, is_archived=False).order_by('name')
        for field in bool_fields:
            count_yes = AccountProductFieldValue.objects.filter(
                field=field,
                value_bool=True,
                account_product__product=integreat,
                account_product__is_archived=False,
                account_product__current_phase__in=final_phases,
                account_product__lead_account_product__isnull=True,
            ).count()
            integreat_field_stats.append({'name': field.name, 'count': count_yes, 'total': integreat_active_total})

    return render(request, 'core/analyse.html', {
        'ampel_per_manager': ampel_per_manager,
        'ampel_sum_row': ampel_sum_row,
        'ampel_avg_row': ampel_avg_row,
        'satisfaction_trend': satisfaction_trend,
        'satisfaction_by_bundesland': satisfaction_by_bundesland,
        'integreat_field_stats': integreat_field_stats,
        'integreat_active_total': integreat_active_total,
    })

