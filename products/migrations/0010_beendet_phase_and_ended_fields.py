from django.db import migrations, models


def rename_abgeschlossen_and_add_beendet(apps, schema_editor):
    ProductPhase = apps.get_model('products', 'ProductPhase')
    Product = apps.get_model('products', 'Product')

    # Rename "Abgeschlossen" → "Aktiv" across all products
    ProductPhase.objects.filter(name='Abgeschlossen').update(name='Aktiv')

    # Add "Beendet" phase to every product that doesn't already have one
    for product in Product.objects.all():
        max_order = product.phases.aggregate(
            m=models.Max('order')
        )['m'] or 0
        ProductPhase.objects.get_or_create(
            product=product,
            name='Beendet',
            defaults={'order': max_order + 1, 'is_final_phase': True},
        )


def reverse_rename(apps, schema_editor):
    ProductPhase = apps.get_model('products', 'ProductPhase')
    ProductPhase.objects.filter(name='Aktiv').update(name='Abgeschlossen')
    ProductPhase.objects.filter(name='Beendet').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0009_accountproduct_primary_contacts'),
    ]

    operations = [
        migrations.AddField(
            model_name='accountproduct',
            name='ended_at',
            field=models.DateField(blank=True, null=True, verbose_name='Beendet zum'),
        ),
        migrations.AddField(
            model_name='accountproduct',
            name='ended_reason',
            field=models.CharField(
                blank=True,
                choices=[
                    ('price', 'Preis'),
                    ('competitor', 'Wechsel zu Wettbewerber'),
                    ('performance', 'Leistung nicht gepasst'),
                    ('internal', 'Interner Grund beim Partner'),
                    ('other', 'Sonstiges (bitte Notiz schreiben)'),
                ],
                max_length=20,
                null=True,
                verbose_name='Beendigungsgrund',
            ),
        ),
        migrations.AlterField(
            model_name='productphase',
            name='is_final_phase',
            field=models.BooleanField(
                default=False,
                verbose_name='Endphase (Aktiv/Verloren/Beendet)',
            ),
        ),
        migrations.RunPython(
            rename_abgeschlossen_and_add_beendet,
            reverse_code=reverse_rename,
        ),
    ]
