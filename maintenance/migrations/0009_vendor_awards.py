from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


def migrate_vendor_decisions(apps, schema_editor):
    WorkOrder = apps.get_model("maintenance", "WorkOrder")
    VendorEstimate = apps.get_model("maintenance", "VendorEstimate")
    VendorAssignment = apps.get_model("maintenance", "VendorAssignment")
    VendorAward = apps.get_model("maintenance", "VendorAward")

    for work_order in WorkOrder.objects.all().iterator():
        estimate = (
            VendorEstimate.objects.filter(work_order=work_order, status="approved")
            .order_by("-approved_at", "-submitted_at")
            .first()
        )
        assignment = (
            VendorAssignment.objects.filter(work_order=work_order)
            .exclude(status__in=["cancelled", "declined"])
            .order_by("-assigned_at")
            .first()
        )
        vendor_id = estimate.vendor_id if estimate else (
            assignment.vendor_id if assignment else None
        )
        if vendor_id:
            VendorAward.objects.create(
                work_order=work_order,
                vendor_id=vendor_id,
                estimate=estimate,
                method="quote" if estimate else "direct",
                decision_reason="migrated_existing_decision",
                status="active",
            )

    # Selection is now represented by VendorAward. Quotes return to their
    # neutral, received state so alternatives remain reusable.
    VendorEstimate.objects.filter(status__in=["approved", "rejected"]).update(
        status="pending", approved_at=None, approved_by=None
    )


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("maintenance", "0008_work_order_replacements"),
        ("vendors", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="VendorAward",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("method", models.CharField(choices=[("quote", "Selected Quote"), ("direct", "Direct Assignment / Quote Waived")], max_length=20)),
                ("status", models.CharField(choices=[("active", "Active"), ("revoked", "Revoked")], db_index=True, default="active", max_length=20)),
                ("decision_reason", models.CharField(blank=True, max_length=50)),
                ("decision_notes", models.TextField(blank=True)),
                ("awarded_at", models.DateTimeField(auto_now_add=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("revocation_reason", models.CharField(blank=True, choices=[("vendor_unavailable", "Vendor unavailable"), ("vendor_declined", "Vendor declined the work"), ("missed_schedule", "Vendor missed the schedule"), ("price_changed", "Price or terms changed"), ("scope_issue", "Scope or capability issue"), ("compliance_issue", "Insurance or compliance issue"), ("other", "Other")], max_length=30)),
                ("revocation_notes", models.TextField(blank=True)),
                ("awarded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="vendor_awards_made", to=settings.AUTH_USER_MODEL)),
                ("estimate", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="awards", to="maintenance.vendorestimate")),
                ("revoked_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="vendor_awards_revoked", to=settings.AUTH_USER_MODEL)),
                ("vendor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="work_order_awards", to="vendors.vendor")),
                ("work_order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="vendor_awards", to="maintenance.workorder")),
            ],
            options={"ordering": ["-awarded_at"]},
        ),
        migrations.AddConstraint(
            model_name="vendoraward",
            constraint=models.UniqueConstraint(condition=Q(status="active"), fields=("work_order",), name="maintenance_one_active_vendor_award"),
        ),
        migrations.RunPython(migrate_vendor_decisions, migrations.RunPython.noop),
    ]
