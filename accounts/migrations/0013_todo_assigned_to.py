from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def assign_todos_to_creator_or_owner(apps, schema_editor):
    Todo = apps.get_model('accounts', 'Todo')
    for todo in Todo.objects.select_related('created_by', 'account__owner').all():
        if todo.created_by_id:
            todo.assigned_to_id = todo.created_by_id
        elif todo.account.owner_id:
            todo.assigned_to_id = todo.account.owner_id
        else:
            continue
        todo.save(update_fields=['assigned_to_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0012_accountproduct_primary_contact'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='todo',
            name='assigned_to',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='assigned_todos',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Zugewiesen an',
            ),
        ),
        migrations.RunPython(assign_todos_to_creator_or_owner, migrations.RunPython.noop),
    ]
