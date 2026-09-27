from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("maintenance", "0005_vendor_quote_requests"),
    ]

    operations = [
        migrations.AlterField(
            model_name="vendorestimate",
            name="amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=12,
                validators=[
                    django.core.validators.MinValueValidator(
                        Decimal("0.00")
                    )
                ],
            ),
        ),
    ]
