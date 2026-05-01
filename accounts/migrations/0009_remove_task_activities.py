# Data migration to remove task activities from activity log

from django.db import migrations


def remove_task_activities(apps, schema_editor):
    """Remove all activities with type 'task' - they now only appear in completed todos."""
    Activity = apps.get_model('accounts', 'Activity')
    deleted_count, _ = Activity.objects.filter(activity_type='task').delete()
    if deleted_count:
        print(f"Removed {deleted_count} task activities from activity log")


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_remove_parent_account'),
    ]

    operations = [
        migrations.RunPython(remove_task_activities, migrations.RunPython.noop),
    ]
