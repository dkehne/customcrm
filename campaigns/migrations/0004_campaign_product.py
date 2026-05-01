import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('campaigns', '0003_accountcampaign'),
        ('products', '0009_accountproduct_primary_contacts'),
    ]

    operations = [
        migrations.AddField(
            model_name='campaign',
            name='product',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='campaigns',
                to='products.product',
                verbose_name='Produkt',
            ),
        ),
    ]
