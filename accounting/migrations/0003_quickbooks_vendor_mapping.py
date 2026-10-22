from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounting", "0002_quickbooks_connection"),
        ("vendors", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="QuickBooksVendorMapping",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quickbooks_vendor_id", models.CharField(max_length=100)),
                ("sync_token", models.CharField(blank=True, max_length=50)),
                ("display_name", models.CharField(max_length=255)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("connection", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="vendor_mappings", to="accounting.quickbooksconnection")),
                ("vendor", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="quickbooks_mappings", to="vendors.vendor")),
            ],
            options={"ordering": ["vendor__company_name", "vendor__name"]},
        ),
        migrations.AddConstraint(
            model_name="quickbooksvendormapping",
            constraint=models.UniqueConstraint(fields=("connection", "vendor"), name="accounting_unique_qb_vendor_mapping"),
        ),
        migrations.AddConstraint(
            model_name="quickbooksvendormapping",
            constraint=models.UniqueConstraint(fields=("connection", "quickbooks_vendor_id"), name="accounting_unique_qb_vendor_id"),
        ),
    ]
