from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("maintenance", "0009_vendor_awards"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="vendoraward",
            name="maintenance_one_active_vendor_award",
        ),
        migrations.AlterField(
            model_name="vendoraward",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending_confirmation", "Pending Vendor Confirmation"),
                    ("active", "Active"),
                    ("revoked", "Revoked"),
                ],
                db_index=True,
                default="active",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="vendoraward",
            name="confirmed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="vendoraward",
            name="confirmed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="vendor_awards_confirmed",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="vendoraward",
            constraint=models.UniqueConstraint(
                condition=models.Q(status__in=["pending_confirmation", "active"]),
                fields=("work_order",),
                name="maintenance_one_current_vendor_award",
            ),
        ),
    ]
