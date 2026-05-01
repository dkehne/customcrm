from django.core.management.base import BaseCommand

from accounts.models import Contact, Todo


class Command(BaseCommand):
    help = (
        'Erstellt Aufgaben für alle Hauptansprechpersonen ohne Anrede. '
        'Die Aufgabe geht an den jeweiligen Produktverantwortlichen, '
        'bei Einzel-Produkt-Accounts an den Account-Inhaber.'
    )

    def handle(self, *args, **options):
        contacts = (
            Contact.objects
            .filter(is_primary=True, is_archived=False, anrede='')
            .select_related('account', 'account__owner')
            .prefetch_related(
                'primary_for_products',
                'primary_for_products__responsible',
                'primary_for_products__account',
                'primary_for_products__account__owner',
            )
        )

        created = 0
        skipped = 0

        for contact in contacts:
            recipients = self._get_recipients(contact)
            for recipient in recipients:
                title = f'Anrede für {contact.name} pflegen'
                already_exists = Todo.objects.filter(
                    account=contact.account,
                    title=title,
                    assigned_to=recipient,
                    is_completed=False,
                ).exists()
                if already_exists:
                    skipped += 1
                    continue
                Todo.objects.create(
                    account=contact.account,
                    title=title,
                    assigned_to=recipient,
                    created_by=None,
                )
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f'{created} Aufgabe(n) erstellt, {skipped} bereits vorhanden übersprungen.'
        ))

    def _get_recipients(self, contact):
        """
        Determine who should receive the todo for filling in the salutation.

        - If the contact is explicitly assigned to one or more AccountProducts
          as a primary contact: use each AP's responsible (ap.get_responsible()).
        - Otherwise (single-product account or no explicit assignment):
          use the single active AP's responsible, falling back to account owner.
        """
        aps = list(contact.primary_for_products.filter(is_archived=False))

        if aps:
            recipients = set()
            for ap in aps:
                responsible = ap.get_responsible() or contact.account.owner
                if responsible:
                    recipients.add(responsible)
            return recipients

        # No explicit product assignment — look at the account's active products
        account_aps = contact.account.account_products.filter(is_archived=False)
        if account_aps.count() == 1:
            ap = account_aps.first()
            responsible = ap.get_responsible() or contact.account.owner
            return {responsible} if responsible else set()

        # Multiple products, no explicit assignment → account owner
        if contact.account.owner:
            return {contact.account.owner}
        return set()
