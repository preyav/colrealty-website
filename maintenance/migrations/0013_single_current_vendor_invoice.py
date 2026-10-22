from django.db import migrations, models


def void_duplicate_current_invoices(apps, schema_editor):
    VendorInvoice = apps.get_model("maintenance", "VendorInvoice")
    work_order_ids = (
        VendorInvoice.objects.exclude(status="void")
        .values_list("work_order_id", flat=True)
        .distinct()
    )
    for work_order_id in work_order_ids:
        invoices = list(
            VendorInvoice.objects.filter(work_order_id=work_order_id)
            .exclude(status="void")
            .order_by("created_at", "id")
        )
        for duplicate in invoices[1:]:
            note = "Automatically voided as a duplicate during invoice cleanup."
            duplicate.status = "void"
            duplicate.notes = (
                f"{duplicate.notes.rstrip()}\n\n{note}"
                if duplicate.notes.strip()
                else note
            )
            duplicate.save(update_fields=["status", "notes"])


class Migration(migrations.Migration):
    dependencies = [
        ("maintenance", "0012_work_order_started_at"),
    ]

    operations = [
        migrations.RunPython(
            void_duplicate_current_invoices,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="vendorinvoice",
            constraint=models.UniqueConstraint(
                fields=("work_order",),
                condition=~models.Q(status="void"),
                name="maintenance_one_current_vendor_invoice",
            ),
        ),
    ]
