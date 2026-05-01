import csv
import os
import re
from collections import defaultdict

from django.core.management.base import BaseCommand

from accounts.models import Contact, SurveyFeature, SurveySnapshot


# Manuell zugeordnete E-Mails → Account-ID (bestätigt)
MANUAL_ACCOUNT_OVERRIDES = {
    'ehrenamt-asyl@lra-oal.bayern.de':                    96,   # Ostallgäu
    'julia.jaekel@lra-oal.bayern.de':                     96,   # Ostallgäu
    'amt33.bildungskoordination@landratsamt-karlsruhe.de': 61,   # Karlsruhe
    'soziales.kanava@segeberg.de':                        122,  # Segeberg
    'n.stasko@hameln-pyrmont.de':                          51,  # Hameln-Pyrmont
    'vitali.hermann@kreis-bergstrasse.de':                 16,  # Bergstraße
    'soziales.heidhoff@segeberg.de':                      122,  # Segeberg
    'karsten.tersteegen@bocholt.de':                       18,  # Bocholt
    'antje.jahn@dahme-spreewald.de':                       27,  # Dahme-Spreewald
    'whandt@gmail.com':                                    30,  # Donnersbergkreis
    # Nachträglich ergänzt (2020–2025)
    'dcharlier@bochum.de':                                 19,  # Bochum
    'anna-katharina.helwig@lra-a.bayern.de':                9,  # LK Augsburg
    'eva.ziegler@krefeld.de':                              65,  # Krefeld
    'tietze.sara@blk.de':                                  22,  # Burgenlandkreis
    'limpert.anne@blk.de':                                 22,  # Burgenlandkreis
    'sabine.kapfhamer@lra-aic-fdb.de':                      2,  # Aichach-Friedberg
    'inga.boekmann@kreis-soest.de':                       124,  # Soest
    'andreas.preuss@ingolstadt.de':                        59,  # Stadt Ingolstadt
    'mikael.evdokimov@tirschenreuth.de':                  993,  # Landkreis Tirschenreuth (ggf. 86 = Nordoberpfalz)
    'simon.letzing@landratsamt.dillingen.de':              28,  # Dillingen an der Donau
}

# E-Mails komplett überspringen (intern oder anonym nicht zuordenbar)
SKIP_EMAILS = {
    'daniel.kehne@tuerantuer.org',
}

SCALE_MAP = {
    '5': 5, '5 (sehr zufrieden)': 5, '++': 5, '++ (sehr zufrieden)': 5,
    '4': 4, '+': 4, '+ (zufrieden)': 4,
    '3': 3, '0': 3, '0 (neutral)': 3,
    '2': 2, '-': 2, '- (unzufrieden)': 2,
    '1': 1, '--': 1, '-- (sehr unzufrieden)': 1, '1 (sehr unzufrieden)': 1,
}

HOURS_WEEK_MAP = {
    'unter 2 stunden': 1.0,
    '2-4 stunden': 3.0,
    '4-6 stunden': 5.0,
    'mehr als 6 stunden': 8.0,
}

HOURS_MONTH_MAP = {
    'daran arbeite ich nicht': 0.0,
    'unter 1 stunde': 0.5,
    '1-2 stunden': 1.5,
    '2-3 stunden': 2.5,
    '3-4 stunden': 3.5,
    '4-5 stunden': 4.5,
    '5-6 stunden': 5.5,
    'mehr als 6 stunden': 7.0,
}

COLUMN_MATCHERS = {
    'satisfaction_app':               'Smartphone-App von Integreat',
    'satisfaction_cms':               'Redaktionssystem zum Verwalten',
    'satisfaction_support':           'Betreuung und Unterstützung durch das Integreat-Team',
    'satisfaction_overall':           'Gesamtangebot von Integreat',
    'satisfaction_content_quality':   'Qualität Ihrer Inhalte',
    'satisfaction_content_freshness': 'Aktualität Ihrer Inhalte',
    'free_text_positive':             'gefällt Ihnen besonders gut',
    'free_text_improvement':          'Verbesserungspotential',
    'respondent_email':               'E-Mail-Adresse',
    'respondent_first_name':          'Vorname',
    'respondent_last_name':           'Nachname',
}


def _extract_feature_name(header):
    match = re.search(r'\[([^\[\]]+)\]\s*$', header)
    if match:
        return match.group(1).strip()
    return header.strip()


def _find_columns(headers):
    col_map = {}
    for field, matcher in COLUMN_MATCHERS.items():
        for i, h in enumerate(headers):
            if matcher in h:
                col_map[field] = i
                break

    feature_request_cols = [
        (i, _extract_feature_name(h))
        for i, h in enumerate(headers)
        if ('zukünftig gewünschte Funktionen' in h or 'priorisieren' in h)
        and '[Kommentar]' not in h
    ]

    not_used_cols = [
        (i, _extract_feature_name(h))
        for i, h in enumerate(headers)
        if ('Angebote und Funktionen kennen' in h or 'Funktionen kennen' in h
            or 'Funktionen/Angebote kennen' in h)
    ]

    time_week_cols = [
        i for i, h in enumerate(headers)
        if 'investieren' in h and 'Woche' in h and 'Minuten' not in h and '[Kommentar]' not in h
    ] or [
        i for i, h in enumerate(headers)
        if 'Zeit investieren' in h and '[Kommentar]' not in h
    ]

    time_month_cols = [
        i for i, h in enumerate(headers)
        if 'Zeit' in h and 'Monat' in h and 'wünschen' not in h and '[Kommentar]' not in h
    ]

    time_minutes_cols = [
        i for i, h in enumerate(headers)
        if 'Zeit (in Minuten)' in h and '[Kommentar]' not in h
    ]

    promotes_simple_col = next(
        (i for i, h in enumerate(headers)
         if h.strip() == 'Bewerben Sie die Integreat-App aktuell bereits online?'),
        None
    )

    promotes_channel_cols = [
        i for i, h in enumerate(headers)
        if 'online beworben' in h and '[Kommentar]' not in h
    ]

    return {
        'col_map': col_map,
        'feature_request_cols': feature_request_cols,
        'not_used_cols': not_used_cols,
        'time_week_cols': time_week_cols,
        'time_month_cols': time_month_cols,
        'time_minutes_cols': time_minutes_cols,
        'promotes_simple_col': promotes_simple_col,
        'promotes_channel_cols': promotes_channel_cols,
    }


def _get_val(row, idx):
    if idx is None or idx >= len(row):
        return ''
    return row[idx].strip()


def _parse_satisfaction(value):
    return SCALE_MAP.get(value.strip()) if value.strip() else None


def _parse_weekly_hours(row, col_info):
    if col_info['time_minutes_cols']:
        total = 0.0
        found = False
        for idx in col_info['time_minutes_cols']:
            try:
                total += float(_get_val(row, idx))
                found = True
            except ValueError:
                pass
        return total / 60.0 if found and total > 0 else None

    if col_info['time_month_cols']:
        total = 0.0
        found = False
        for idx in col_info['time_month_cols']:
            val = _get_val(row, idx).lower()
            if val in HOURS_MONTH_MAP:
                total += HOURS_MONTH_MAP[val]
                found = True
        return round(total / 4.0, 2) if found else None

    for idx in col_info['time_week_cols']:
        val = _get_val(row, idx).lower()
        if val in HOURS_WEEK_MAP:
            return HOURS_WEEK_MAP[val]
    return None


def _parse_promotes(row, col_info):
    if col_info['promotes_simple_col'] is not None:
        val = _get_val(row, col_info['promotes_simple_col']).lower()
        if 'ja' in val:
            return True
        if val:
            return False
        return None

    if col_info['promotes_channel_cols']:
        for idx in col_info['promotes_channel_cols']:
            if _get_val(row, idx).strip().lower() == 'ja':
                return True
        return False

    return None


def _find_account_id(email, first, last):
    if email and email.lower() in SKIP_EMAILS:
        return None

    if email:
        override = MANUAL_ACCOUNT_OVERRIDES.get(email.lower())
        if override:
            return override

    if email:
        contact = (
            Contact.objects
            .filter(email__iexact=email, is_archived=False)
            .select_related('account')
            .first()
        )
        if contact:
            return contact.account_id

    # Name fallback
    full = f'{first} {last}'.strip()
    if full:
        matches = list(
            Contact.objects
            .filter(name__icontains=full, is_archived=False)
            .values_list('account_id', flat=True)
            .distinct()
        )
        if len(matches) == 1:
            return matches[0]
    if first:
        matches = list(
            Contact.objects
            .filter(name__icontains=first, is_archived=False)
            .values_list('account_id', flat=True)
            .distinct()
        )
        if len(matches) == 1:
            return matches[0]

    return None


def _parse_row(row, col_info):
    """Parse a single CSV row into a dict of raw values."""
    col_map = col_info['col_map']
    return {
        'satisfaction_app':               _parse_satisfaction(_get_val(row, col_map.get('satisfaction_app'))),
        'satisfaction_cms':               _parse_satisfaction(_get_val(row, col_map.get('satisfaction_cms'))),
        'satisfaction_support':           _parse_satisfaction(_get_val(row, col_map.get('satisfaction_support'))),
        'satisfaction_overall':           _parse_satisfaction(_get_val(row, col_map.get('satisfaction_overall'))),
        'satisfaction_content_quality':   _parse_satisfaction(_get_val(row, col_map.get('satisfaction_content_quality'))),
        'satisfaction_content_freshness': _parse_satisfaction(_get_val(row, col_map.get('satisfaction_content_freshness'))),
        'free_text_positive':             _get_val(row, col_map.get('free_text_positive')),
        'free_text_improvement':          _get_val(row, col_map.get('free_text_improvement')),
        'respondent_email':               _get_val(row, col_map.get('respondent_email')),
        'respondent_name':                f"{_get_val(row, col_map.get('respondent_first_name'))} {_get_val(row, col_map.get('respondent_last_name'))}".strip(),
        'weekly_hours':                   _parse_weekly_hours(row, col_info),
        'promotes_online':                _parse_promotes(row, col_info),
        'features_request':               [
            name for idx, name in col_info['feature_request_cols']
            if _get_val(row, idx).strip().lower() == 'ja'
        ],
        'features_not_used':              [
            name for idx, name in col_info['not_used_cols']
            if 'kenne ich, aber' in _get_val(row, idx).lower()
        ],
    }


def _aggregate(parsed_rows):
    """Aggregate multiple parsed rows for the same account+year."""
    if len(parsed_rows) == 1:
        return parsed_rows[0]

    def avg_int(field):
        vals = [r[field] for r in parsed_rows if r[field] is not None]
        return round(sum(vals) / len(vals)) if vals else None

    def avg_float(field):
        vals = [r[field] for r in parsed_rows if r[field] is not None]
        return round(sum(vals) / len(vals), 2) if vals else None

    def concat_text(field):
        parts = [r[field] for r in parsed_rows if r[field]]
        return '\n---\n'.join(parts) if parts else ''

    def any_true(field):
        vals = [r[field] for r in parsed_rows if r[field] is not None]
        if not vals:
            return None
        return any(vals)

    # Union of features (deduplicated)
    features_request = list({
        name for r in parsed_rows for name in r['features_request']
    })
    features_not_used = list({
        name for r in parsed_rows for name in r['features_not_used']
    })

    return {
        'satisfaction_app':               avg_int('satisfaction_app'),
        'satisfaction_cms':               avg_int('satisfaction_cms'),
        'satisfaction_support':           avg_int('satisfaction_support'),
        'satisfaction_overall':           avg_int('satisfaction_overall'),
        'satisfaction_content_quality':   avg_int('satisfaction_content_quality'),
        'satisfaction_content_freshness': avg_int('satisfaction_content_freshness'),
        'free_text_positive':             concat_text('free_text_positive'),
        'free_text_improvement':          concat_text('free_text_improvement'),
        'respondent_email':               parsed_rows[0]['respondent_email'],
        'respondent_name':                parsed_rows[0]['respondent_name'],
        'weekly_hours':                   avg_float('weekly_hours'),
        'promotes_online':                any_true('promotes_online'),
        'features_request':               features_request,
        'features_not_used':              features_not_used,
    }


class Command(BaseCommand):
    help = 'Import LimeSurvey Umfragedaten aus YYYY.csv Dateien'

    def add_arguments(self, parser):
        parser.add_argument('directory', help='Verzeichnis mit YYYY.csv Dateien')

    def handle(self, *args, **options):
        directory = options['directory']
        if not os.path.isdir(directory):
            self.stderr.write(f'Verzeichnis nicht gefunden: {directory}')
            return

        csv_files = sorted([
            f for f in os.listdir(directory)
            if re.match(r'^\d{4}\.csv$', f)
        ])

        if not csv_files:
            self.stdout.write('Keine YYYY.csv Dateien gefunden.')
            return

        total_saved = 0
        total_no_match = 0

        for filename in csv_files:
            year = int(filename[:4])
            filepath = os.path.join(directory, filename)

            with open(filepath, encoding='utf-8-sig') as f:
                reader = csv.reader(f, delimiter=',')
                headers = next(reader)
                rows = list(reader)

            col_info = _find_columns(headers)
            col_map = col_info['col_map']

            self.stdout.write(f'Importiere {filename} ({len(rows)} Zeilen)...')

            # Phase 1: Zeilen zu Accounts zuordnen und gruppieren
            grouped = defaultdict(list)   # account_id -> [parsed_row]
            no_match = 0

            for row in rows:
                email = _get_val(row, col_map.get('respondent_email'))
                first = _get_val(row, col_map.get('respondent_first_name'))
                last  = _get_val(row, col_map.get('respondent_last_name'))

                if email and email.lower() in SKIP_EMAILS:
                    continue

                account_id = _find_account_id(email, first, last)

                if account_id is None:
                    if email or (first and last):
                        display = f'{email or "–"} | {(first + " " + last).strip() or "–"}'
                        self.stdout.write(f'  KEIN MATCH: {display} | Jahr {year}')
                    no_match += 1
                    continue

                grouped[account_id].append(_parse_row(row, col_info))

            # Phase 2: Aggregieren und speichern
            for account_id, parsed_rows in grouped.items():
                data = _aggregate(parsed_rows)

                snapshot, _ = SurveySnapshot.objects.update_or_create(
                    account_id=account_id,
                    year=year,
                    defaults={
                        'satisfaction_app':               data['satisfaction_app'],
                        'satisfaction_cms':               data['satisfaction_cms'],
                        'satisfaction_support':           data['satisfaction_support'],
                        'satisfaction_overall':           data['satisfaction_overall'],
                        'satisfaction_content_quality':   data['satisfaction_content_quality'],
                        'satisfaction_content_freshness': data['satisfaction_content_freshness'],
                        'free_text_positive':             data['free_text_positive'],
                        'free_text_improvement':          data['free_text_improvement'],
                        'respondent_email':               data['respondent_email'],
                        'respondent_name':                data['respondent_name'],
                        'weekly_hours':                   data['weekly_hours'],
                        'promotes_online':                data['promotes_online'],
                    },
                )

                snapshot.features.all().delete()
                for name in data['features_request']:
                    SurveyFeature.objects.create(
                        snapshot=snapshot,
                        feature_name=name,
                        kind=SurveyFeature.Kind.REQUEST,
                    )
                for name in data['features_not_used']:
                    SurveyFeature.objects.create(
                        snapshot=snapshot,
                        feature_name=name,
                        kind=SurveyFeature.Kind.NOT_USED,
                    )

                total_saved += 1

            matched = len(grouped)
            self.stdout.write(
                f'  ✓ {matched} Accounts verknüpft ({len(rows) - no_match} Antworten) '
                f'| ✗ {no_match} kein Match'
            )
            total_no_match += no_match

        self.stdout.write(
            f'\nFertig. {total_saved} SurveySnapshots erstellt/aktualisiert, '
            f'{total_no_match} ohne Match.'
        )
