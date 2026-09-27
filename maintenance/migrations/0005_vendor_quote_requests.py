from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        ("maintenance", "0004_maintenance_request_review"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="VendorQuoteRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("draft", "Draft"), ("sent", "Sent"), ("viewed", "Viewed"), ("quote_received", "Quote Received"), ("declined", "Declined"), ("expired", "Expired"), ("cancelled", "Cancelled")], db_index=True, default="draft", max_length=20)),
                ("scope", models.TextField()),
                ("instructions", models.TextField(blank=True)),
                ("response_due", models.DateField(blank=True, null=True)),
                ("delivery_channel", models.CharField(default="email", max_length=20)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("requested_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="requested_vendor_quotes", to=settings.AUTH_USER_MODEL)),
                ("vendor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="quote_requests", to="vendors.vendor")),
                ("work_order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="quote_requests", to="maintenance.workorder")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddField(
            model_name="vendorestimate",
            name="attachment",
            field=models.FileField(blank=True, null=True, upload_to="maintenance/vendor_quotes/%Y/%m/"),
        ),
        migrations.AddField(
            model_name="vendorestimate",
            name="discount_amount",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, validators=[django.core.validators.MinValueValidator(Decimal("0.00"))]),
        ),
        migrations.AddField(
            model_name="vendorestimate",
            name="entry_method",
            field=models.CharField(choices=[("total", "Total amount only"), ("itemized", "Itemized cost breakdown")], default="total", max_length=20),
        ),
        migrations.AddField(
            model_name="vendorestimate",
            name="labor_amount",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, validators=[django.core.validators.MinValueValidator(Decimal("0.00"))]),
        ),
        migrations.AddField(
            model_name="vendorestimate",
            name="materials_amount",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, validators=[django.core.validators.MinValueValidator(Decimal("0.00"))]),
        ),
        migrations.AddField(
            model_name="vendorestimate",
            name="other_fees",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, validators=[django.core.validators.MinValueValidator(Decimal("0.00"))]),
        ),
        migrations.AddField(
            model_name="vendorestimate",
            name="quote_request",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="estimates", to="maintenance.vendorquoterequest"),
        ),
        migrations.AddField(
            model_name="vendorestimate",
            name="received_date",
            field=models.DateField(default=django.utils.timezone.localdate),
        ),
        migrations.AddField(
            model_name="vendorestimate",
            name="source",
            field=models.CharField(choices=[("col360", "COL360 Quote Request"), ("phone", "Phone"), ("email", "Email"), ("text", "Text Message"), ("in_person", "In Person"), ("vendor_portal", "Vendor Portal"), ("other", "Other")], default="other", max_length=20),
        ),
        migrations.AddField(
            model_name="vendorestimate",
            name="tax_amount",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, validators=[django.core.validators.MinValueValidator(Decimal("0.00"))]),
        ),
        migrations.AddField(
            model_name="vendorestimate",
            name="valid_through",
            field=models.DateField(blank=True, null=True),
        ),
    ]
