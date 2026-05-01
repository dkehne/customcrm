from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Account, Activity, Contact
from contracts.models import Contract
from products.models import AccountProduct, AccountProductFieldValue


class Command(BaseCommand):
    help = 'Dupliziert einen Account (Stammdaten, Kontakte, Produkte, Verträge, Aktivitäten) – ohne Todos, Umfragen und Vertragsdokumente.'

    def add_arguments(self, parser):
        parser.add_argument('account_id', type=int, help='PK des zu duplizierenden Accounts')

    def handle(self, *args, **options):
        pk = options['account_id']

        try:
            source = Account.objects.get(pk=pk)
        except Account.DoesNotExist:
            raise CommandError(f'Account mit ID {pk} nicht gefunden.')

        self.stdout.write(f'Dupliziere Account „{source.name}" (ID {source.pk}) …')

        with transaction.atomic():
            # 1. Account
            new_account = Account.objects.create(
                name=f'{source.name} (Kopie)',
                account_type=source.account_type,
                bundesland=source.bundesland,
                owner=source.owner,
                notes=source.notes,
                is_archived=source.is_archived,
            )
            self.stdout.write(f'  ✓ Account erstellt (ID {new_account.pk})')

            # 2. Kontakte – altes PK → neues Contact-Objekt
            contact_map = {}
            contacts = list(source.contacts.all())
            for c in contacts:
                new_c = Contact.objects.create(
                    account=new_account,
                    name=c.name,
                    email=c.email,
                    phone=c.phone,
                    gender=c.gender,
                    position=c.position,
                    is_primary=c.is_primary,
                    is_archived=c.is_archived,
                )
                contact_map[c.pk] = new_c
            self.stdout.write(f'  ✓ {len(contacts)} Kontakte erstellt')

            # 3. Account-Produkte – erst ohne lead_account_product und primary_contacts
            ap_map = {}
            account_products = list(source.account_products.all())
            for ap in account_products:
                new_ap = AccountProduct.objects.create(
                    account=new_account,
                    product=ap.product,
                    current_phase=ap.current_phase,
                    responsible=ap.responsible,
                    lead_account_product=None,  # wird nach Erstellung gesetzt
                    is_archived=ap.is_archived,
                )
                ap_map[ap.pk] = new_ap

                # Feldwerte
                for fv in ap.field_values.all():
                    AccountProductFieldValue.objects.create(
                        account_product=new_ap,
                        field=fv.field,
                        value_text=fv.value_text,
                        value_int=fv.value_int,
                        value_bool=fv.value_bool,
                        value_date=fv.value_date,
                    )

                # Hauptansprechpersonen (M2M) – nur wenn Kontakt im gleichen Account
                for pc in ap.primary_contacts.all():
                    if pc.pk in contact_map:
                        new_ap.primary_contacts.add(contact_map[pc.pk])
            self.stdout.write(f'  ✓ {len(account_products)} Produkte erstellt')

            # lead_account_product nachträglich setzen (nur interne Verweise)
            for ap in account_products:
                if ap.lead_account_product_id and ap.lead_account_product_id in ap_map:
                    ap_map[ap.pk].lead_account_product = ap_map[ap.lead_account_product_id]
                    ap_map[ap.pk].save(update_fields=['lead_account_product'])

            # 4. Verträge – ohne Dokumente (Dateien müssen manuell übertragen werden)
            contracts = list(source.contracts.all())
            for c in contracts:
                new_ap_ref = None
                if c.account_product_id and c.account_product_id in ap_map:
                    new_ap_ref = ap_map[c.account_product_id]
                Contract.objects.create(
                    account=new_account,
                    account_product=new_ap_ref,
                    gross_annual_price=c.gross_annual_price,
                    contract_type=c.contract_type,
                    start_date=c.start_date,
                    duration_months=c.duration_months,
                    is_self_cancelling=c.is_self_cancelling,
                    renewal_interval_months=c.renewal_interval_months,
                    notice_period_months=c.notice_period_months,
                    is_archived=c.is_archived,
                )
            self.stdout.write(f'  ✓ {len(contracts)} Verträge erstellt (ohne Dokumente)')

            # 5. Aktivitäten – Kontakt-Verknüpfung auf neuen Kontakt remappen
            activities = list(source.activities.all())
            for a in activities:
                new_contact = contact_map.get(a.contact_id)
                Activity.objects.create(
                    account=new_account,
                    activity_type=a.activity_type,
                    subject=a.subject,
                    description=a.description,
                    date=a.date,
                    contact=new_contact,
                    created_by=a.created_by,
                )
            self.stdout.write(f'  ✓ {len(activities)} Aktivitäten erstellt')

        self.stdout.write(self.style.SUCCESS(
            f'\nFertig. Neuer Account: „{new_account.name}" (ID {new_account.pk})'
        ))
        if contracts:
            self.stdout.write(self.style.WARNING(
                '  Hinweis: Vertragsdokumente (PDFs) wurden nicht kopiert – bitte manuell nachpflegen.'
            ))
