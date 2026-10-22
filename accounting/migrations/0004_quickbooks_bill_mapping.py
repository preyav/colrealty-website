from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounting", "0003_quickbooks_vendor_mapping"),
        ("maintenance", "0014_vendor_payments"),
    ]

    operations = [
        migrations.CreateModel(
            name="QuickBooksBillMapping",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quickbooks_bill_id", models.CharField(max_length=100)),
                ("sync_token", models.CharField(blank=True, max_length=50)),
                ("document_number", models.CharField(max_length=100)),
                ("expense_account_id", models.CharField(max_length=100)),
                ("expense_account_name", models.CharField(max_length=255)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("connection", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bill_mappings", to="accounting.quickbooksconnection")),
                ("invoice", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="quickbooks_bill_mapping", to="maintenance.vendorinvoice")),
            ],
            options={"ordering": ["-last_synced_at", "-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="quickbooksbillmapping",
            constraint=models.UniqueConstraint(fields=("connection", "quickbooks_bill_id"), name="accounting_unique_qb_bill_id"),
        ),
    ]
