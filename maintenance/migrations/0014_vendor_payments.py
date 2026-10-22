import decimal
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def migrate_legacy_paid_invoices(apps, schema_editor):
    VendorInvoice = apps.get_model("maintenance", "VendorInvoice")
    VendorPayment = apps.get_model("maintenance", "VendorPayment")
    for invoice in VendorInvoice.objects.filter(status="paid").iterator():
        payment_date = invoice.invoice_date
        if invoice.paid_at:
            payment_date = invoice.paid_at.date()
        if payment_date is None:
            continue
        VendorPayment.objects.create(
            invoice_id=invoice.pk,
            amount=invoice.amount,
            payment_date=payment_date,
            payment_method="other",
            payment_account="Legacy payment record",
            notes="Migrated from the prior paid-invoice status.",
            status="recorded",
            recorded_by_id=invoice.approved_by_id,
        )


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("maintenance", "0013_single_current_vendor_invoice"),
    ]

    operations = [
        migrations.AlterField(
            model_name="vendorinvoice",
            name="status",
            field=models.CharField(
                choices=[
                    ("submitted", "Submitted"),
                    ("approved", "Approved"),
                    ("partially_paid", "Partially Paid"),
                    ("paid", "Paid"),
                    ("disputed", "Disputed"),
                    ("void", "Void"),
                ],
                db_index=True,
                default="submitted",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="VendorPayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.01"))])),
                ("payment_date", models.DateField()),
                ("payment_method", models.CharField(choices=[("ach", "ACH"), ("check", "Check"), ("card", "Card"), ("cash", "Cash"), ("electronic_transfer", "Electronic Transfer"), ("other", "Other")], max_length=30)),
                ("reference_number", models.CharField(blank=True, max_length=150)),
                ("payment_account", models.CharField(blank=True, max_length=150)),
                ("notes", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("recorded", "Recorded"), ("void", "Void")], db_index=True, default="recorded", max_length=20)),
                ("recorded_at", models.DateTimeField(auto_now_add=True)),
                ("voided_at", models.DateTimeField(blank=True, null=True)),
                ("void_reason", models.TextField(blank=True)),
                ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payments", to="maintenance.vendorinvoice")),
                ("recorded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="recorded_vendor_payments", to=settings.AUTH_USER_MODEL)),
                ("voided_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="voided_vendor_payments", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-payment_date", "-recorded_at"],
                "constraints": [models.CheckConstraint(condition=models.Q(("amount__gt", 0)), name="vendor_payment_amount_positive")],
            },
        ),
        migrations.RunPython(migrate_legacy_paid_invoices, migrations.RunPython.noop),
    ]
