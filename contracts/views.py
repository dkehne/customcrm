from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Contract


@login_required
def contract_list(request):
    show_archived = request.GET.get('archived') == '1'
    contracts = Contract.objects.filter(is_archived=show_archived).select_related(
        'account', 'account__account_type', 'account_product__product', 'contract_type',
    )

    q = request.GET.get('q', '').strip()
    if q:
        contracts = contracts.filter(account__name__icontains=q)

    contract_type_id = request.GET.get('contract_type', '')
    if contract_type_id:
        contracts = contracts.filter(contract_type_id=contract_type_id)

    from .models import ContractType
    return render(request, 'contracts/contract_list.html', {
        'contracts': contracts,
        'show_archived': show_archived,
        'q': q,
        'contract_type_id': contract_type_id,
        'contract_types': ContractType.objects.filter(is_archived=False, is_active=True),
    })
