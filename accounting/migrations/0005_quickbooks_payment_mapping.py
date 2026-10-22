from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounting", "0004_quickbooks_bill_mapping"),
        ("maintenance", "0015_vendor_payment_financial_account"),
    ]

    operations = [
        migrations.CreateModel(
            name="QuickBooksPaymentMapping",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quickbooks_payment_id", models.CharField(blank=True, max_length=100)),
                ("sync_token", models.CharField(blank=True, max_length=50)),
                ("document_number", models.CharField(max_length=100)),
                ("payment_account_id", models.CharField(max_length=100)),
                ("payment_account_name", models.CharField(max_length=255)),
                ("payment_account_type", models.CharField(max_length=50)),
                ("status", models.CharField(choices=[("pending", "Pending synchronization"), ("synced", "Synchronized"), ("deleted", "Removed from QuickBooks"), ("error", "Synchronization error")], db_index=True, default="pending", max_length=20)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("bill_mapping", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payment_mappings", to="accounting.quickbooksbillmapping")),
                ("connection", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payment_mappings", to="accounting.quickbooksconnection")),
                ("payment", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="quickbooks_payment_mapping", to="maintenance.vendorpayment")),
            ],
            options={"ordering": ["-last_synced_at", "-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="quickbookspaymentmapping",
            constraint=models.UniqueConstraint(condition=~models.Q(quickbooks_payment_id=""), fields=("connection", "quickbooks_payment_id"), name="accounting_unique_qb_payment_id"),
        ),
    ]
