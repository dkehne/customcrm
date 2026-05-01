"""
Einmaliger Import-Command: Salesforce-Exportdaten ins Custom CRM.

Verwendung:
    python manage.py import_salesforce --owner <username> [--sf-dir <pfad>] [--dry-run]

Was der Command tut:
  1. Erstellt neue Accounts für „Landkreis Kassel" und „Stadt Kassel"
     (mit Kontakten, E-Mail-Aktivitäten und Notizen), jeweils getrennt.
  2. Importiert Kontakte neu für „Stadt Koblenz", „Freinet-Online",
     „Bayerischer Landes-Sportverband (BLSV)" (bestehende Kontakte bleiben,
     neue werden ergänzt – Duplikate per E-Mail übersprungen).
  3. Importiert E-Mail-Aktivitäten für „Stadt Friedrichshafen", „Stadt Koblenz",
     „Stadt Dortmund", „Freinet-Online", BLSV und „Stadt Nürnberg".
  4. Aggregiert Notizen (Note.csv + Task-Beschreibungen ohne E-Mail/Anruf-Typ)
     für alle CRM-Accounts, die per Name einem Salesforce-Account zugeordnet
     werden können, und hängt sie an das Notizen-Feld des Accounts.
  5. Nicht aufgelöste E-Mails von info@integreat-app.de werden dem User
     fritjof.knier zugeordnet.

Salesforce-Account-IDs:
  Stadt Koblenz          0011t00000g9wiLAAQ
  Stadt Nürnberg         00158000004EtMnAAK
  Stadt Dortmund         0015800000MNQufAAH
  Stadt Kassel           0015800001cktzvAAA
  Landkreis Kassel       0019Y000004mBxkQAE
  Freinet-Online         0016N0000040slTQAQ
  BLSV                   0019Y000005suRkQAI
  Friedrichshafen        00158000004xaynAAA
"""

import csv
import os
from datetime import datetime, timezone as dt_timezone

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import Account, AccountType, Activity, Contact
from core.models import CustomUser

# ---------------------------------------------------------------------------
# Salesforce ID → Import-Rolle
# ---------------------------------------------------------------------------

# Accounts, die als NEUE Accounts angelegt werden (getrennte Migration)
NEW_ACCOUNTS = {
    '0015800001cktzvAAA': 'Stadt Kassel',
    '0019Y000004mBxkQAE': 'Landkreis Kassel',
}

# Accounts, für die nur Kontakte neu importiert werden
CONTACT_REIMPORT = {
    '0011t00000g9wiLAAQ': 'Stadt Koblenz',
    '0016N0000040slTQAQ': 'Freinet-Online',
    '0019Y000005suRkQAI': 'Bayerischer Landes-Sportverband (BLSV)',
}

# Accounts, für die E-Mail-Aktivitäten importiert werden
EMAIL_ACTIVITY_IMPORT = {
    '00158000004xaynAAA': 'Friedrichshafen',
    '0011t00000g9wiLAAQ': 'Stadt Koblenz',
    '0015800000MNQufAAH': 'Dortmund',        # CRM-Name ohne "Stadt"-Präfix
    '0016N0000040slTQAQ': 'Freinet-Online',
    '0019Y000005suRkQAI': 'Bayerischer Landes-Sportverband (BLSV)',
    '00158000004EtMnAAK': 'Nürnberg',        # CRM-Name ohne "Stadt"-Präfix
    # Kassel-Accounts ebenfalls (werden im selben Lauf erstellt)
    '0015800001cktzvAAA': 'Stadt Kassel',
    '0019Y000004mBxkQAE': 'Landkreis Kassel',
}

# ---------------------------------------------------------------------------
# Mappings
# ---------------------------------------------------------------------------

BUNDESLAND_MAP = {
    'Baden-Württemberg': 'BW',
    'Bayern': 'BY',
    'Berlin': 'BE',
    'Brandenburg': 'BB',
    'Bremen': 'HB',
    'Hamburg': 'HH',
    'Hessen': 'HE',
    'Mecklenburg-Vorpommern': 'MV',
    'Niedersachsen': 'NI',
    'NRW': 'NW',
    'Nordrhein-Westfalen': 'NW',
    'Rheinland-Pfalz': 'RP',
    'Saarland': 'SL',
    'Sachsen': 'SN',
    'Sachsen-Anhalt': 'ST',
    'Schleswig-Holstein': 'SH',
    'Thüringen': 'TH',
    'Bodenseekreis': 'BW',  # Bodenseekreis liegt in Baden-Württemberg
}

ACCOUNT_TYPE_MAP = {
    'Kommune-kreisfrei': 'Stadt (kreisfrei)',
    'Kommune-LK': 'Kreis / Landkreis',
    'Kommune-kreisangehoerig': 'Stadt (kreisangehörig)',
    'Kommune-kreisangehörig': 'Stadt (kreisangehörig)',
}

EMAIL_SUBJECT_PREFIXES = ('E-Mail:', 'Unresolved Email', 'Nicht aufgelöste E-Mail',
                           'Nicht aufgelöste Email')
UNRESOLVED_PREFIXES = ('Unresolved Email', 'Nicht aufgelöste E-Mail', 'Nicht aufgelöste Email')
SKIP_PREFIXES = ('Call', 'Anruf', 'Nachhaken', 'Nachhacken', 'Wiederholt',
                 'Johanniter', 'Kontakt', 'Termin', 'Geburtstagsprotokoll',
                 'Persönliches Treffen', 'Ansprechpartner', 'Jobanruf')


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _read_csv(path, encoding='utf-8-sig'):
    with open(path, encoding=encoding) as f:
        return list(csv.DictReader(f))


def _parse_date(value):
    """Parse Salesforce date strings like '2024-01-15 00:00:00' to aware datetime."""
    if not value or not value.strip():
        return None
    value = value.strip()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.replace(tzinfo=dt_timezone.utc)
        except ValueError:
            continue
    return None


def _strip_email_header(description):
    """Remove Salesforce email header lines from Task Description."""
    if not description:
        return ''
    # Typically: "Weitere Empfänger: ... CC: ... BCC: ... Anhang: ... Thema: XYZ Text: ..."
    # or "Additional To: ... CC: ... Attachment: ... Subject: XYZ Text: ..."
    lines = description.splitlines()
    result_lines = []
    skip_header = True
    for line in lines:
        stripped = line.strip()
        if skip_header and any(stripped.startswith(p) for p in (
            'Weitere Empfänger:', 'Additional To:', 'CC:', 'BCC:',
            'Anhang:', 'Attachment:', 'Thema:', 'Subject:',
        )):
            # Keep "Thema:"/"Subject:" content as first line of body
            if stripped.startswith('Thema:'):
                pass  # skip – the subject is already in Activity.subject
            elif stripped.startswith('Subject:'):
                pass
            continue
        if skip_header and stripped.startswith('Text:'):
            skip_header = False
            body = stripped[5:].strip()
            if body:
                result_lines.append(body)
            continue
        skip_header = False
        result_lines.append(line)
    body = '\n'.join(result_lines).strip()
    # Fallback: if nothing was extracted, return raw description
    return body if body else description.strip()


def _is_from_integreat_info(description):
    return 'info@integreat-app.de' in (description or '')


def _subject_clean(raw_subject):
    """Strip 'E-Mail: ', 'Nicht aufgelöste E-Mail: ' etc. prefix from task subject."""
    for prefix in ('E-Mail: ', 'Unresolved Email: ', 'Nicht aufgelöste E-Mail: ',
                   'Nicht aufgelöste Email: '):
        if raw_subject.startswith(prefix):
            return raw_subject[len(prefix):].strip()
    return raw_subject.strip()


class Command(BaseCommand):
    help = 'Importiert ausgewählte Daten aus dem Salesforce-Export in das Custom CRM.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--owner', required=True,
            help='Username des CRM-Users, der als Besitzer neuer Accounts gesetzt wird.',
        )
        parser.add_argument(
            '--sf-dir', default='salesforce-export',
            help='Pfad zum Salesforce-Export-Verzeichnis (Standard: ./salesforce-export/).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Simuliert den Import ohne Datenbankänderungen.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        sf_dir = options['sf_dir']
        owner_username = options['owner']

        if dry_run:
            self.stdout.write(self.style.WARNING('=== DRY RUN – keine Änderungen werden gespeichert ==='))

        # Resolve owner
        try:
            owner = CustomUser.objects.get(username=owner_username)
        except CustomUser.DoesNotExist:
            raise CommandError(f'User "{owner_username}" nicht gefunden.')

        try:
            fritjof = CustomUser.objects.get(username='fritjof.knier')
        except CustomUser.DoesNotExist:
            fritjof = owner
            self.stdout.write(self.style.WARNING(
                'User "fritjof.knier" nicht gefunden – verwende owner für unaufgelöste E-Mails.'))

        # Load CSV data
        self.stdout.write('Lade Salesforce-CSV-Dateien...')
        try:
            sf_accounts = {r['Id']: r for r in _read_csv(os.path.join(sf_dir, 'Account.csv'))
                           if r['IsDeleted'] == '0'}
            sf_contacts = _read_csv(os.path.join(sf_dir, 'Contact.csv'))
            sf_tasks = _read_csv(os.path.join(sf_dir, 'Task.csv'))
            sf_notes = _read_csv(os.path.join(sf_dir, 'Note.csv'))
        except FileNotFoundError as e:
            raise CommandError(f'CSV-Datei nicht gefunden: {e}')

        sf_contacts = [r for r in sf_contacts if r['IsDeleted'] == '0']
        sf_tasks = [r for r in sf_tasks if r['IsDeleted'] == '0']

        self.stdout.write(f'  Accounts: {len(sf_accounts)}, Kontakte: {len(sf_contacts)}, '
                          f'Tasks: {len(sf_tasks)}, Notizen: {len(sf_notes)}')

        # Index contacts and tasks by account ID
        contacts_by_acc = {}
        for c in sf_contacts:
            acc_id = c.get('AccountId', '')
            contacts_by_acc.setdefault(acc_id, []).append(c)

        tasks_by_acc = {}
        for t in sf_tasks:
            acc_id = t.get('WhatId', '')
            tasks_by_acc.setdefault(acc_id, []).append(t)

        # Index tasks by contact (WhoId) for tasks not linked to an account (WhatId=null)
        NULL_ID = '000000000000000AAA'
        tasks_by_contact = {}
        for t in sf_tasks:
            who_id = t.get('WhoId', '')
            if who_id and who_id != NULL_ID and t.get('WhatId') == NULL_ID:
                tasks_by_contact.setdefault(who_id, []).append(t)

        # Cache account types
        account_types = {at.name: at for at in AccountType.objects.all()}

        # ---------------------------------------------------------------
        # Phase 1: Neue Accounts für Landkreis Kassel + Stadt Kassel
        # ---------------------------------------------------------------
        self.stdout.write(self.style.HTTP_INFO('\n[Phase 1] Neue Accounts für Kassel anlegen...'))
        kassel_crm_map = {}  # sf_id → CRM Account
        for sf_id, display_name in NEW_ACCOUNTS.items():
            sf_acc = sf_accounts.get(sf_id)
            if not sf_acc:
                self.stdout.write(self.style.WARNING(f'  Salesforce-Account nicht gefunden: {sf_id}'))
                continue

            bl_code = BUNDESLAND_MAP.get(sf_acc.get('BillingState', ''), '')
            type_name = ACCOUNT_TYPE_MAP.get(sf_acc.get('Type', ''), '')
            acc_type = account_types.get(type_name)

            notes_parts = self._collect_notes(sf_id, sf_notes, tasks_by_acc, contacts_by_acc)

            self.stdout.write(f'  Erstelle Account: {sf_acc["Name"]} '
                              f'(Bundesland: {bl_code}, Typ: {type_name})')

            if not dry_run:
                with transaction.atomic():
                    crm_acc = Account.objects.create(
                        name=sf_acc['Name'],
                        account_type=acc_type,
                        bundesland=bl_code,
                        owner=owner,
                        notes='\n\n'.join(notes_parts),
                    )
                    kassel_crm_map[sf_id] = crm_acc
                    n_contacts = self._import_contacts(
                        crm_acc, contacts_by_acc.get(sf_id, []), dry_run)
                    self.stdout.write(f'    → {crm_acc.name} (ID {crm_acc.pk}), '
                                      f'{n_contacts} Kontakte angelegt')
            else:
                contacts = contacts_by_acc.get(sf_id, [])
                self.stdout.write(f'    [dry-run] würde {len(contacts)} Kontakte anlegen, '
                                  f'{len(notes_parts)} Notizteile aggregieren')

        # ---------------------------------------------------------------
        # Phase 2: Kontakte neu importieren für Koblenz / Freinet / BLSV
        # ---------------------------------------------------------------
        self.stdout.write(self.style.HTTP_INFO('\n[Phase 2] Kontakte re-importieren...'))
        for sf_id, expected_name in CONTACT_REIMPORT.items():
            crm_acc = self._find_crm_account(expected_name)
            if not crm_acc:
                self.stdout.write(self.style.WARNING(f'  CRM-Account nicht gefunden: {expected_name}'))
                continue
            self.stdout.write(f'  {crm_acc.name} (ID {crm_acc.pk})')
            if not dry_run:
                with transaction.atomic():
                    n = self._import_contacts(crm_acc, contacts_by_acc.get(sf_id, []), dry_run)
                    self.stdout.write(f'    → {n} Kontakte neu angelegt (Duplikate übersprungen)')
            else:
                n = len(contacts_by_acc.get(sf_id, []))
                self.stdout.write(f'    [dry-run] würde bis zu {n} Kontakte prüfen')

        # ---------------------------------------------------------------
        # Phase 3: E-Mail-Aktivitäten importieren
        # ---------------------------------------------------------------
        self.stdout.write(self.style.HTTP_INFO('\n[Phase 3] E-Mail-Aktivitäten importieren...'))
        for sf_id, expected_name in EMAIL_ACTIVITY_IMPORT.items():
            if sf_id in kassel_crm_map:
                crm_acc = kassel_crm_map[sf_id]
            else:
                crm_acc = self._find_crm_account(expected_name)
            if not crm_acc:
                self.stdout.write(self.style.WARNING(f'  CRM-Account nicht gefunden: {expected_name}'))
                continue

            # Tasks direkt am Account + Tasks die nur am Kontakt hängen
            contact_ids = {c['Id'] for c in contacts_by_acc.get(sf_id, [])}
            contact_tasks = [
                t for cid in contact_ids
                for t in tasks_by_contact.get(cid, [])
            ]
            all_tasks = tasks_by_acc.get(sf_id, []) + contact_tasks
            seen_ids = set()
            email_tasks = []
            for t in all_tasks:
                if t['Id'] not in seen_ids and t.get('Subject', '').startswith(EMAIL_SUBJECT_PREFIXES):
                    seen_ids.add(t['Id'])
                    email_tasks.append(t)
            self.stdout.write(f'  {crm_acc.name}: {len(email_tasks)} E-Mail-Tasks '
                              f'({len(contact_tasks)} über Kontakt-Verknüpfung)')

            if not dry_run:
                with transaction.atomic():
                    n = self._import_email_activities(
                        crm_acc, email_tasks, owner, fritjof, dry_run)
                    self.stdout.write(f'    → {n} Aktivitäten angelegt')
            else:
                self.stdout.write(f'    [dry-run] würde {len(email_tasks)} Aktivitäten anlegen')

        # ---------------------------------------------------------------
        # Phase 4: Notizen für alle CRM-Accounts aggregieren
        # ---------------------------------------------------------------
        self.stdout.write(self.style.HTTP_INFO('\n[Phase 4] Notizen für alle Accounts importieren...'))
        n_updated = 0
        for sf_id, sf_acc in sf_accounts.items():
            # Skip Kassel – already handled in phase 1
            if sf_id in NEW_ACCOUNTS:
                continue
            crm_acc = self._find_crm_account(sf_acc['Name'])
            if not crm_acc:
                continue
            notes_parts = self._collect_notes(sf_id, sf_notes, tasks_by_acc, contacts_by_acc)
            if not notes_parts:
                continue
            combined = '\n\n'.join(notes_parts)
            # Prepend to existing notes, avoid duplicates
            existing = crm_acc.notes.strip()
            if combined in existing:
                continue  # already imported
            new_notes = f'{combined}\n\n{existing}'.strip() if existing else combined
            if not dry_run:
                crm_acc.notes = new_notes
                crm_acc.save(update_fields=['notes'])
            n_updated += 1
            self.stdout.write(f'  {crm_acc.name}: {len(notes_parts)} Notizteile hinzugefügt')

        self.stdout.write(f'  Gesamt: {n_updated} Accounts mit Notizen aktualisiert')

        self.stdout.write(self.style.SUCCESS('\nImport abgeschlossen.'))

    # -------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------

    def _find_crm_account(self, name):
        """Find a CRM account by exact name, then by partial match."""
        acc = Account.objects.filter(name=name, is_archived=False).first()
        if acc:
            return acc
        # Try partial match for minor name differences
        acc = Account.objects.filter(name__icontains=name, is_archived=False).first()
        return acc

    def _import_contacts(self, crm_acc, sf_contacts_list, dry_run):
        """Create contacts from Salesforce data; skip duplicates by email."""
        existing_emails = set(
            crm_acc.contacts.filter(is_archived=False).values_list('email', flat=True)
        )
        existing_names = set(
            crm_acc.contacts.filter(is_archived=False).values_list('name', flat=True)
        )
        created = 0
        for c in sf_contacts_list:
            name = f"{c.get('FirstName', '')} {c.get('LastName', '')}".strip()
            email = c.get('Email', '').strip()
            if not name:
                continue
            # Skip if already exists by email or name
            if email and email in existing_emails:
                continue
            if name in existing_names:
                continue
            phone = (c.get('Phone') or c.get('MobilePhone') or '').strip()
            position = (c.get('Title') or '').strip()[:200]
            if not dry_run:
                Contact.objects.create(
                    account=crm_acc,
                    name=name,
                    email=email,
                    phone=phone,
                    position=position,
                    is_primary=False,
                )
            existing_emails.add(email)
            existing_names.add(name)
            created += 1
        return created

    def _import_email_activities(self, crm_acc, email_tasks, default_owner, fritjof, dry_run):
        """Create Activity records (type='email') from Salesforce Task records."""
        created = 0
        existing_subjects = set(
            crm_acc.activities.filter(activity_type='email').values_list('subject', flat=True)
        )
        for t in email_tasks:
            raw_subject = t.get('Subject', '').strip()
            subject = _subject_clean(raw_subject)[:300]
            description = _strip_email_header(t.get('Description', ''))
            activity_date = _parse_date(t.get('ActivityDate', '')) or timezone.now()
            is_unresolved = raw_subject.startswith(UNRESOLVED_PREFIXES)
            from_info = _is_from_integreat_info(t.get('Description', ''))
            assigned_user = fritjof if (is_unresolved and from_info) else default_owner

            # Skip exact duplicate (same subject already exists)
            if subject in existing_subjects:
                continue

            if not dry_run:
                Activity.objects.create(
                    account=crm_acc,
                    activity_type='email',
                    subject=subject,
                    description=description,
                    date=activity_date,
                    created_by=assigned_user,
                )
            existing_subjects.add(subject)
            created += 1
        return created

    def _collect_notes(self, sf_account_id, sf_notes, tasks_by_acc, contacts_by_acc):
        """Aggregate Note.csv entries and non-email Task descriptions for an account."""
        parts = []

        # 1. Note.csv: notes linked to contacts of this account
        contact_ids = {c['Id'] for c in contacts_by_acc.get(sf_account_id, [])}
        for note in sf_notes:
            parent_id = note.get('ParentId', '')
            if parent_id in contact_ids:
                title = note.get('Title', '').strip()
                body = note.get('Body', '').strip()
                date = (note.get('CreatedDate', '') or '')[:10]
                if body and title not in ('Email', 'Phone', 'Department', 'Title', 'Last Name'):
                    parts.append(f'{date} – {title}: {body}' if title else f'{date}: {body}')

        # 2. Task descriptions (non-email, non-call tasks with content)
        for t in tasks_by_acc.get(sf_account_id, []):
            subject = t.get('Subject', '').strip()
            description = t.get('Description', '').strip()
            if not description:
                continue
            # Skip email tasks (handled as Activities)
            if subject.startswith(EMAIL_SUBJECT_PREFIXES):
                continue
            # Skip pure call/phone tasks (already covered by Activity type 'call' if needed)
            if subject in ('Call', 'Anruf', 'Email'):
                continue
            date_str = (t.get('ActivityDate', '') or '')[:10]
            entry = f'{date_str} – {subject}: {description}' if subject else f'{date_str}: {description}'
            parts.append(entry[:1000])  # cap per entry

        return parts
