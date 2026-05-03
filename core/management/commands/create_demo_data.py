"""
Management command to populate the database with realistic demo data for
presentations and screenshots. Safe to run multiple times (idempotent via
get_or_create where possible). Use --reset to wipe and recreate everything.
"""
import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Account, AccountType, Activity, Contact, Todo
from campaigns.models import AccountCampaign, Campaign, CampaignContact
from contracts.models import Contract, ContractType
from core.models import CustomUser
from products.models import (
    AccountProduct, AccountProductFieldValue, Product, ProductField, ProductPhase,
)


# ---------------------------------------------------------------------------
# Demo data fixtures
# ---------------------------------------------------------------------------

ACCOUNT_TYPES = ['Eingetragener Verein', 'Stiftung', 'gGmbH', 'Genossenschaft', 'Kommunalverwaltung']

PRODUCTS = [
    {
        'name': 'Basispaket',
        'phases': [
            ('Erstkontakt', 0, False),
            ('Angebot versendet', 1, False),
            ('Verhandlung', 2, False),
            ('Aktiv', 3, True),
            ('Beendet', 4, True),
        ],
        'fields': [
            ('Vertragslaufzeit (Jahre)', 'integer'),
            ('Newsletter aktiv', 'boolean'),
            ('Vertragsbeginn', 'date'),
        ],
    },
    {
        'name': 'Premiumpaket',
        'phases': [
            ('Interessent', 0, False),
            ('Demo gehalten', 1, False),
            ('Angebot', 2, False),
            ('Aktiv', 3, True),
            ('Beendet', 4, True),
        ],
        'fields': [
            ('Supportstunden/Monat', 'integer'),
            ('Schulung absolviert', 'boolean'),
            ('Go-Live-Datum', 'date'),
        ],
    },
    {
        'name': 'Beratung',
        'phases': [
            ('Anfrage', 0, False),
            ('Konzept', 1, False),
            ('Umsetzung', 2, False),
            ('Abgeschlossen', 3, True),
        ],
        'fields': [
            ('Projektstunden gesamt', 'integer'),
            ('Abschlussbericht erstellt', 'boolean'),
        ],
    },
]

CONTRACT_TYPES = ['Jahreslizenz', 'Mehrjahreslizenz', 'Beratungsvertrag']

ACCOUNTS = [
    ('Gemeinschaft Zukunft e.V.', 'Eingetragener Verein'),
    ('Stiftung Miteinander', 'Stiftung'),
    ('Bildungswerk Aktiv gGmbH', 'gGmbH'),
    ('Nachbarschaftshilfe Sonntal e.V.', 'Eingetragener Verein'),
    ('Regionalentwicklung Nord eG', 'Genossenschaft'),
    ('Kulturzentrum Brücke e.V.', 'Eingetragener Verein'),
    ('Soziale Dienste Weststadt gGmbH', 'gGmbH'),
    ('Umweltnetz Grüntal e.V.', 'Eingetragener Verein'),
    ('Förderverein Jugend & Sport e.V.', 'Eingetragener Verein'),
    ('Bürgerstiftung Markthausen', 'Stiftung'),
    ('Integrationsnetz Vielfalt e.V.', 'Eingetragener Verein'),
    ('Gemeinnützige Wohnbau eG', 'Genossenschaft'),
    ('Wohlfahrtsverband Mittelstadt gGmbH', 'gGmbH'),
    ('Naturschutzverein Flusstal e.V.', 'Eingetragener Verein'),
    ('Hospizverein Trost & Würde e.V.', 'Eingetragener Verein'),
    ('Klimaschutz Initiative Havenstadt e.V.', 'Eingetragener Verein'),
    ('Stadtwerke Kooperation', 'Kommunalverwaltung'),
    ('Jugendhilfe Osten e.V.', 'Eingetragener Verein'),
    ('Sozialgenossenschaft Füreinander eG', 'Genossenschaft'),
    ('Digitales Ehrenamt e.V.', 'Eingetragener Verein'),
]

CONTACTS = [
    ('Maria Schreiber', 'Geschäftsführung', 'Sehr geehrte Frau Schreiber'),
    ('Thomas Kranz', 'Vorstandsvorsitzender', 'Sehr geehrter Herr Kranz'),
    ('Sabine Hoffmann', 'Projektleitung', 'Sehr geehrte Frau Hoffmann'),
    ('Markus Weiler', 'Geschäftsführer', 'Sehr geehrter Herr Weiler'),
    ('Claudia Bauer', 'Koordinatorin', 'Sehr geehrte Frau Bauer'),
    ('Stefan Neumann', 'Vorstand', 'Sehr geehrter Herr Neumann'),
    ('Anke Zimmermann', 'Leiterin Öffentlichkeitsarbeit', 'Sehr geehrte Frau Zimmermann'),
    ('Ralf Fischer', 'Projektmanager', 'Sehr geehrter Herr Fischer'),
    ('Julia Hartmann', 'Teamleitung', 'Sehr geehrte Frau Hartmann'),
    ('Andreas Koch', 'Verwaltungsleiter', 'Sehr geehrter Herr Koch'),
]

ACTIVITY_SUBJECTS = [
    ('call', 'Erstgespräch geführt'),
    ('call', 'Nachfrage zu Angebot'),
    ('email', 'Angebot versendet'),
    ('email', 'Unterlagen nachgefordert'),
    ('meeting', 'Demo-Termin durchgeführt'),
    ('meeting', 'Vertragsverhandlung'),
    ('call', 'Quartals-Check-in'),
    ('email', 'Verlängerungsangebot versendet'),
    ('meeting', 'Jahresgespräch'),
    ('call', 'Supportanfrage besprochen'),
    ('email', 'Schulungsunterlagen verschickt'),
    ('meeting', 'Onboarding-Termin'),
]

TODO_TITLES = [
    'Angebot nachfassen',
    'Vertrag zur Unterschrift vorbereiten',
    'Schulungstermin koordinieren',
    'Rechnung prüfen',
    'Abschlussbericht anfordern',
    'Kontaktdaten aktualisieren',
    'Verlängerungsgespräch einplanen',
    'Referenzbericht anfragen',
]

CAMPAIGN_NAMES = [
    ('Jahreskonferenz 2026', date(2026, 9, 15), date(2026, 9, 15)),
    ('Newsletter Q2 2026', date(2026, 4, 1), date(2026, 6, 30)),
    ('Onboarding-Webinar Mai', date(2026, 5, 20), date(2026, 5, 20)),
]


class Command(BaseCommand):
    help = 'Create demo data for presentations and screenshots'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete all existing demo data before creating new',
        )

    def handle(self, *args, **options):
        if options['reset']:
            self._reset()

        self.stdout.write('Creating demo data...')
        today = date.today()

        # Users
        admin = self._get_or_create_superuser()
        verwalter1 = self._get_or_create_verwalter('lisa.meier', 'Lisa', 'Meier')
        verwalter2 = self._get_or_create_verwalter('jonas.wolf', 'Jonas', 'Wolf')
        users = [verwalter1, verwalter2]

        # Account types
        types_map = {}
        for name in ACCOUNT_TYPES:
            at, _ = AccountType.objects.get_or_create(name=name)
            types_map[name] = at
        self.stdout.write(f'  {len(ACCOUNT_TYPES)} account types')

        # Products
        products_map = {}
        for pdata in PRODUCTS:
            product, _ = Product.objects.get_or_create(name=pdata['name'])
            products_map[pdata['name']] = product
            for phase_name, order, is_final in pdata['phases']:
                ProductPhase.objects.get_or_create(
                    product=product, name=phase_name,
                    defaults={'order': order, 'is_final_phase': is_final},
                )
            for field_name, field_type in pdata['fields']:
                ProductField.objects.get_or_create(
                    product=product, name=field_name,
                    defaults={'field_type': field_type, 'show_on_dashboard': True},
                )
        self.stdout.write(f'  {len(PRODUCTS)} products with phases and fields')

        # Contract types
        for ct_name in CONTRACT_TYPES:
            ContractType.objects.get_or_create(name=ct_name)

        # Accounts + contacts + activities + todos + products + contracts
        accounts = []
        for i, (acc_name, acc_type_name) in enumerate(ACCOUNTS):
            owner = users[i % len(users)]
            account, _ = Account.objects.get_or_create(
                name=acc_name,
                defaults={
                    'account_type': types_map[acc_type_name],
                    'owner': owner,
                    'notes': f'Demo-Datensatz für {acc_name}.',
                },
            )
            accounts.append(account)

            # 1–2 contacts per account
            contact_data = CONTACTS[i % len(CONTACTS)]
            contact, _ = Contact.objects.get_or_create(
                account=account,
                name=contact_data[0],
                defaults={
                    'position': contact_data[1],
                    'anrede': contact_data[2],
                    'email': f'{contact_data[0].lower().replace(" ", ".")}'
                             f'@{acc_name[:8].lower().replace(" ", "")}.de',
                    'phone': f'+49 {random.randint(100,999)} {random.randint(1000000,9999999)}',
                    'is_primary': True,
                },
            )
            if i % 3 == 0:
                second = CONTACTS[(i + 5) % len(CONTACTS)]
                Contact.objects.get_or_create(
                    account=account,
                    name=second[0] + ' (2)',
                    defaults={
                        'position': 'Stellvertretung',
                        'email': f'{second[0].lower().replace(" ", ".")}.2'
                                 f'@{acc_name[:8].lower().replace(" ", "")}.de',
                        'is_primary': False,
                    },
                )

            # Assign a product in a meaningful phase
            product = list(products_map.values())[i % len(products_map)]
            phases = list(product.phases.order_by('order'))
            if i < 4:
                phase = next((p for p in phases if p.is_final_phase and 'Aktiv' in p.name), phases[-2])
            elif i < 8:
                phase = phases[1]  # early funnel
            elif i < 14:
                phase = next((p for p in phases if p.is_final_phase and 'Aktiv' in p.name), phases[-2])
            else:
                phase = phases[2] if len(phases) > 2 else phases[1]

            ap, created = AccountProduct.objects.get_or_create(
                account=account, product=product,
                defaults={'current_phase': phase, 'responsible': owner},
            )
            if created:
                # Set some field values
                for field in product.fields.filter(is_archived=False):
                    if field.field_type == 'integer':
                        AccountProductFieldValue.objects.get_or_create(
                            account_product=ap, field=field,
                            defaults={'value_int': random.choice([12, 24, 36, 48])},
                        )
                    elif field.field_type == 'boolean':
                        AccountProductFieldValue.objects.get_or_create(
                            account_product=ap, field=field,
                            defaults={'value_bool': random.choice([True, True, False])},
                        )
                    elif field.field_type == 'date':
                        AccountProductFieldValue.objects.get_or_create(
                            account_product=ap, field=field,
                            defaults={'value_date': today - timedelta(days=random.randint(30, 500))},
                        )

            # Contract for active accounts
            if phase.is_final_phase and 'Aktiv' in phase.name:
                ct = ContractType.objects.filter(is_archived=False).order_by('?').first()
                if ct:
                    start = today - timedelta(days=random.randint(60, 700))
                    Contract.objects.get_or_create(
                        account=account,
                        account_product=ap,
                        contract_type=ct,
                        defaults={
                            'gross_annual_price': random.choice([1200, 2400, 3600, 4800, 6000]),
                            'start_date': start,
                            'duration_months': 12,
                            'renewal_interval_months': 12,
                            'notice_period_months': 3,
                            'is_self_cancelling': False,
                        },
                    )

            # Activities (2–4 per account)
            for j in range(random.randint(2, 4)):
                act_type, act_subject = ACTIVITY_SUBJECTS[(i + j) % len(ACTIVITY_SUBJECTS)]
                days_ago = random.randint(1, 180)
                Activity.objects.get_or_create(
                    account=account,
                    subject=act_subject,
                    date=timezone.now() - timedelta(days=days_ago),
                    defaults={
                        'activity_type': act_type,
                        'contact': contact,
                        'created_by': owner,
                        'description': f'Notiz zum Gespräch vom {(today - timedelta(days=days_ago)).strftime("%d.%m.%Y")}.',
                    },
                )

            # Todo for some accounts
            if i % 4 == 0:
                Todo.objects.get_or_create(
                    account=account,
                    title=TODO_TITLES[i % len(TODO_TITLES)],
                    defaults={
                        'due_date': today + timedelta(days=random.randint(3, 30)),
                        'created_by': owner,
                        'assigned_to': owner,
                        'description': 'Automatisch erzeugter Demo-Datensatz.',
                    },
                )

        self.stdout.write(f'  {len(ACCOUNTS)} accounts with contacts, products, activities')

        # Campaigns
        for camp_name, start, end in CAMPAIGN_NAMES:
            campaign, created = Campaign.objects.get_or_create(
                name=camp_name,
                defaults={
                    'start_date': start,
                    'end_date': end,
                    'created_by': admin,
                },
            )
            if created:
                for account in accounts[:8]:
                    primary = account.contacts.filter(is_primary=True).first()
                    if primary:
                        cc, _ = CampaignContact.objects.get_or_create(
                            campaign=campaign,
                            contact=primary,
                            defaults={
                                'account': account,
                                'contact_name': primary.name,
                                'contact_email': primary.email,
                                'contact_phone': primary.phone,
                                'contact_salutation': primary.anrede,
                                'account_name': account.name,
                            },
                        )
                        AccountCampaign.objects.get_or_create(
                            account=account, campaign=campaign,
                        )
        self.stdout.write(f'  {len(CAMPAIGN_NAMES)} campaigns')

        self.stdout.write(self.style.SUCCESS('Demo data created successfully.'))
        self.stdout.write('  Login:  admin / admin  (Superuser)')
        self.stdout.write('  Login:  lisa.meier / demo  (Verwalter)')
        self.stdout.write('  Login:  jonas.wolf / demo  (Verwalter)')

    def _get_or_create_superuser(self):
        user, created = CustomUser.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@example.com',
                'first_name': 'Admin',
                'last_name': 'Demo',
                'role': CustomUser.Role.SUPERUSER,
                'is_superuser': True,
                'is_staff': True,
            },
        )
        if created:
            user.set_password('admin')
            user.save()
        return user

    def _get_or_create_verwalter(self, username, first, last):
        user, created = CustomUser.objects.get_or_create(
            username=username,
            defaults={
                'email': f'{username}@example.com',
                'first_name': first,
                'last_name': last,
                'role': CustomUser.Role.VERWALTER,
            },
        )
        if created:
            user.set_password('demo')
            user.save()
        return user

    def _reset(self):
        self.stdout.write(self.style.WARNING('Resetting demo data...'))
        CampaignContact.objects.all().delete()
        AccountCampaign.objects.all().delete()
        Campaign.objects.all().delete()
        Contract.objects.all().delete()
        AccountProductFieldValue.objects.all().delete()
        AccountProduct.objects.all().delete()
        Activity.objects.all().delete()
        Todo.objects.all().delete()
        Contact.objects.all().delete()
        Account.objects.all().delete()
        ProductField.objects.all().delete()
        ProductPhase.objects.all().delete()
        Product.objects.all().delete()
        ContractType.objects.all().delete()
        AccountType.objects.all().delete()
        CustomUser.objects.exclude(username='admin').delete()
        self.stdout.write('  Reset complete.')
