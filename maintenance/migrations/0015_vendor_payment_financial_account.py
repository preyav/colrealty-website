import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounting", "0001_initial"),
        ("maintenance", "0014_vendor_payments"),
    ]
    operations = [
        migrations.AddField(
            model_name="vendorpayment",
            name="financial_account",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="vendor_payments",
                to="accounting.financialaccount",
            ),
        ),
    ]
