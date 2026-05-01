from django.db import migrations, models


def copy_primary_contact_to_m2m(apps, schema_editor):
    AccountProduct = apps.get_model('products', 'AccountProduct')
    for ap in AccountProduct.objects.filter(primary_contact__isnull=False):
        ap.primary_contacts.add(ap.primary_contact_id)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0012_accountproduct_primary_contact'),
        ('products', '0008_accountproduct_primary_contact'),
    ]

    operations = [
        migrations.AddField(
            model_name='accountproduct',
            name='primary_contacts',
            field=models.ManyToManyField(
                blank=True,
                related_name='primary_for_products',
                to='accounts.contact',
                verbose_name='Hauptansprechpersonen',
            ),
        ),
        migrations.RunPython(copy_primary_contact_to_m2m, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='accountproduct',
            name='primary_contact',
        ),
    ]
