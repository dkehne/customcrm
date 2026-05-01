from django.db import migrations


def seed_integreat(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    ProductPhase = apps.get_model('products', 'ProductPhase')
    ProductField = apps.get_model('products', 'ProductField')

    product, _ = Product.objects.get_or_create(name='Integreat')

    phases = [
        ('Informationen verschickt', 1, False),
        ('Produkt vorgestellt', 2, False),
        ('Vertrag verschickt', 3, False),
        ('Abgeschlossen', 4, True),
        ('Verloren', 5, True),
    ]
    for name, order, is_final in phases:
        ProductPhase.objects.get_or_create(
            product=product, name=name,
            defaults={'order': order, 'is_final_phase': is_final},
        )

    fields = [
        ('Go-Live-Datum', 'date'),
        ('Supportstunden', 'integer'),
        ('MT-Vertrag 1 Mio', 'boolean'),
        ('MT-Vertrag 5 Mio', 'boolean'),
        ('Suchassistent', 'boolean'),
        ('Beratungssystem', 'boolean'),
        ('Go-Offline-Datum', 'date'),
    ]
    for name, field_type in fields:
        ProductField.objects.get_or_create(
            product=product, name=name,
            defaults={'field_type': field_type},
        )


def remove_integreat(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    Product.objects.filter(name='Integreat').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0003_rename_gewonnen_to_abgeschlossen'),
    ]

    operations = [
        migrations.RunPython(seed_integreat, remove_integreat),
    ]
