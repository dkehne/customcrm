# Generated manually on 2026-02-05

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_add_todo_description'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='account',
            name='parent_account',
        ),
    ]
