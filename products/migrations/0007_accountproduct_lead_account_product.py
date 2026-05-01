import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0006_add_accountproduct_responsible'),
    ]

    operations = [
        migrations.AddField(
            model_name='accountproduct',
            name='lead_account_product',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='partner_products',
                to='products.accountproduct',
                verbose_name='Leit-Account-Produkt (Produktverbund)',
            ),
        ),
    ]
