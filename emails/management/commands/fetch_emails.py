import email
import email.policy
import imaplib
import signal
import time
import uuid
from email.utils import getaddresses, parseaddr, parsedate_to_datetime

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import close_old_connections, transaction
from django.utils import timezone

from accounts.models import Activity, Contact
from emails.models import (
    EmailAttachment,
    InboundEmail,
    UserEmailAddress,
    UserInboundAddress,
)


class Command(BaseCommand):
    help = 'Fetch unread emails via IMAP and process them into the CRM.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Parse and display emails without saving to the database.',
        )
        parser.add_argument(
            '--daemon', action='store_true',
            help='Run continuously, polling for new emails at a regular interval.',
        )
        parser.add_argument(
            '--interval', type=int, default=300,
            help='Polling interval in seconds when running in daemon mode (default: 300).',
        )

    def handle(self, *args, **options):
        if options['daemon']:
            self._run_daemon(options)
        else:
            self._fetch_once(options)

    def _run_daemon(self, options):
        interval = options['interval']
        self._shutdown = False

        def _handle_signal(signum, frame):
            self._shutdown = True

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

        self.stdout.write(f'Starting email daemon (polling every {interval}s). '
                          f'Send SIGINT/SIGTERM to stop.')

        while not self._shutdown:
            try:
                close_old_connections()
                self._fetch_once(options)
            except Exception as exc:
                self.stderr.write(f'Fetch cycle failed: {exc}')
            if not self._shutdown:
                time.sleep(interval)

        self.stdout.write('Email daemon stopped.')

    def _fetch_once(self, options):
        dry_run = options['dry_run']
        host = settings.IMAP_HOST
        port = settings.IMAP_PORT
        user = settings.IMAP_USER
        password = settings.IMAP_PASSWORD
        use_ssl = settings.IMAP_USE_SSL

        if not host or not user:
            self.stderr.write('IMAP settings not configured. Set IMAP_HOST and IMAP_USER.')
            return

        if use_ssl:
            conn = imaplib.IMAP4_SSL(host, port)
        else:
            conn = imaplib.IMAP4(host, port)

        try:
            conn.login(user, password)
            conn.select('INBOX')

            status, data = conn.search(None, 'UNSEEN')
            if status != 'OK' or not data[0]:
                self.stdout.write('No unread messages.')
                return

            msg_nums = data[0].split()
            self.stdout.write(f'Found {len(msg_nums)} unread message(s).')

            for num in msg_nums:
                try:
                    self._process_message(conn, num, dry_run)
                except Exception as exc:
                    self.stderr.write(f'Error processing message {num}: {exc}')
        finally:
            try:
                conn.close()
            except Exception:
                pass
            conn.logout()

    def _process_message(self, conn, num, dry_run):
        status, data = conn.fetch(num, '(RFC822)')
        if status != 'OK':
            return

        raw_email = data[0][1]
        parsed = self._parse_email(raw_email)

        if not dry_run and InboundEmail.objects.filter(message_id=parsed['message_id']).exists():
            self.stdout.write(f'  Skipping duplicate: {parsed["message_id"]}')
            return

        if dry_run:
            self._print_dry_run(parsed)
            return

        crm_user = self._match_user(parsed['all_recipients'], parsed['from_email'])
        if not crm_user:
            self.stderr.write(f'  No CRM user found for message: {parsed["message_id"]}')
            return

        matched_account = self._match_account(parsed['all_recipients'], parsed['from_email'])
        self._save_email(raw_email, parsed, crm_user, matched_account)

        status = 'resolved' if matched_account else 'unresolved'
        self.stdout.write(
            f'  Processed: {parsed["subject"][:60]} -> {status}'
            f'{" (" + matched_account.name + ")" if matched_account else ""}'
        )
        conn.store(num, '+FLAGS', '\\Seen')

    def _parse_email(self, raw_email):
        msg = email.message_from_bytes(raw_email, policy=email.policy.default)

        message_id = msg.get('Message-ID', '').strip()
        if not message_id:
            message_id = f'<generated-{uuid.uuid4()}>'

        from_name, from_email = parseaddr(msg.get('From', ''))
        subject = msg.get('Subject', '') or ''

        all_recipients = []
        for header in ('To', 'Cc', 'Delivered-To', 'X-Original-To'):
            vals = msg.get_all(header, [])
            for _, addr in getaddresses(vals):
                if addr:
                    all_recipients.append(addr.lower())

        date_str = msg.get('Date', '')
        try:
            received_at = parsedate_to_datetime(date_str)
            if timezone.is_naive(received_at):
                received_at = timezone.make_aware(received_at)
        except Exception:
            received_at = timezone.now()

        body_text, body_html, attachments = self._parse_body(msg)

        return {
            'message_id': message_id,
            'from_email': from_email,
            'subject': subject,
            'all_recipients': all_recipients,
            'recipient_str': ', '.join(all_recipients),
            'received_at': received_at,
            'body_text': body_text,
            'body_html': body_html,
            'attachments': attachments,
        }

    def _parse_body(self, msg):
        body_text = ''
        body_html = ''
        attachments = []

        if msg.is_multipart():
            for part in msg.walk():
                disposition = str(part.get('Content-Disposition', ''))
                content_type = part.get_content_type()

                if 'attachment' in disposition:
                    payload = part.get_payload(decode=True)
                    if payload:
                        attachments.append({
                            'filename': part.get_filename() or 'attachment',
                            'content_type': content_type,
                            'data': payload,
                        })
                elif content_type == 'text/plain' and not body_text:
                    body_text = self._decode_payload(part)
                elif content_type == 'text/html' and not body_html:
                    body_html = self._decode_payload(part)
        else:
            decoded = self._decode_payload(msg)
            if msg.get_content_type() == 'text/html':
                body_html = decoded
            else:
                body_text = decoded

        return body_text, body_html, attachments

    def _decode_payload(self, part):
        payload = part.get_payload(decode=True)
        if not payload:
            return ''
        charset = part.get_content_charset() or 'utf-8'
        try:
            return payload.decode(charset)
        except (UnicodeDecodeError, LookupError):
            return payload.decode('latin-1')

    def _match_user(self, all_recipients, from_email):
        for addr in all_recipients:
            local_part = addr.split('@')[0]
            if local_part.startswith('crm+'):
                local_part = local_part[4:]
            try:
                uuid_token = uuid.UUID(local_part)
                inbound_addr = UserInboundAddress.objects.select_related('user').get(token=uuid_token)
                user = inbound_addr.user
                if UserEmailAddress.objects.filter(user=user, email__iexact=from_email).exists():
                    return user
                self.stderr.write(
                    f'  Absender {from_email!r} ist nicht unter "Meine E-Mail-Adressen" '
                    f'für {user.get_username()!r} hinterlegt – E-Mail wird ignoriert.'
                )
                return None
            except (ValueError, UserInboundAddress.DoesNotExist):
                continue

        user_email = UserEmailAddress.objects.select_related('user').filter(
            email__iexact=from_email,
        ).first()
        if user_email:
            return user_email.user

        return None

    def _match_account(self, all_recipients, from_email):
        for addr in all_recipients:
            contact = Contact.objects.filter(
                email__iexact=addr, is_archived=False,
            ).select_related('account').first()
            if contact:
                return contact.account

        contact = Contact.objects.filter(
            email__iexact=from_email, is_archived=False,
        ).select_related('account').first()
        if contact:
            return contact.account

        return None

    def _save_email(self, raw_email, parsed, crm_user, matched_account):
        status = 'resolved' if matched_account else 'unresolved'

        with transaction.atomic():
            inbound = InboundEmail.objects.create(
                user=crm_user,
                account=matched_account,
                status=status,
                message_id=parsed['message_id'],
                sender_email=parsed['from_email'],
                recipient_emails=parsed['recipient_str'],
                subject=parsed['subject'][:500],
                body_text=parsed['body_text'],
                body_html=parsed['body_html'],
                received_at=parsed['received_at'],
            )

            inbound.eml_file.save(
                f'{inbound.pk}.eml',
                ContentFile(raw_email),
                save=True,
            )

            for att in parsed['attachments']:
                ea = EmailAttachment(
                    inbound_email=inbound,
                    filename=att['filename'][:300],
                    content_type=att['content_type'][:200],
                )
                ea.file.save(att['filename'], ContentFile(att['data']), save=True)

            if matched_account:
                Activity.objects.create(
                    account=matched_account,
                    activity_type='email',
                    subject=parsed['subject'][:300] or '(Kein Betreff)',
                    description=f'Von: {parsed["from_email"]}',
                    date=parsed['received_at'],
                    created_by=crm_user,
                    inbound_email=inbound,
                )

    def _print_dry_run(self, parsed):
        self.stdout.write(f'  Message-ID: {parsed["message_id"]}')
        self.stdout.write(f'  From: {parsed["from_email"]}')
        self.stdout.write(f'  To: {parsed["recipient_str"]}')
        self.stdout.write(f'  Subject: {parsed["subject"]}')
        self.stdout.write(f'  Date: {parsed["received_at"]}')
        self.stdout.write(f'  Attachments: {len(parsed["attachments"])}')
        self.stdout.write(f'  Body length: {len(parsed["body_text"])} chars')
        self.stdout.write('---')
