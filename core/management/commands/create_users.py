import csv

from django.core.management.base import BaseCommand

from core.models import CustomUser


class Command(BaseCommand):
    help = 'Create users from a CSV file (for OIDC pre-provisioning)'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file',
            help='Path to CSV with columns: username,email,first_name,last_name,is_superuser',
        )

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        created = 0
        skipped = 0

        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                username = row['username'].strip()
                if not username:
                    continue

                if CustomUser.objects.filter(username=username).exists():
                    self.stdout.write(f'  Skipped (exists): {username}')
                    skipped += 1
                    continue

                is_superuser = row.get('is_superuser', '').strip().upper() in (
                    'TRUE', '1', 'YES', 'T',
                )

                user = CustomUser(
                    username=username,
                    email=row.get('email', '').strip(),
                    first_name=row.get('first_name', '').strip(),
                    last_name=row.get('last_name', '').strip(),
                    is_superuser=is_superuser,
                    role=(
                        CustomUser.Role.SUPERUSER if is_superuser
                        else CustomUser.Role.VERWALTER
                    ),
                )
                user.set_unusable_password()
                user.save()
                created += 1
                self.stdout.write(f'  Created: {username} ({"superuser" if is_superuser else "verwalter"})')

        self.stdout.write(self.style.SUCCESS(
            f'Done. Created {created}, skipped {skipped}.'
        ))
