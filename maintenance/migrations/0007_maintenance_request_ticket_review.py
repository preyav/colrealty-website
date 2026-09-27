from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("maintenance", "0006_vendor_estimate_amount_form_optional"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="maintenancerequest",
            name="status",
            field=models.CharField(
                choices=[
                    ("new", "New"),
                    ("triaged", "Triaged"),
                    ("under_review", "Under Review"),
                    ("pending_information", "Pending Information"),
                    ("approved", "Approved"),
                    ("declined", "Declined"),
                    ("converted", "Converted to Work Order"),
                    ("completed", "Completed"),
                    ("cancelled", "Cancelled"),
                ],
                db_index=True,
                default="new",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="maintenancerequest",
            name="pending_reason",
            field=models.CharField(
                blank=True,
                choices=[
                    ("tenant_details", "Contact tenant / obtain more details"),
                    ("owner_authorization", "Owner authorization"),
                    ("budget_review", "Budget / accounting review"),
                    ("warranty_check", "Warranty verification"),
                    ("property_inspection", "Property inspection"),
                    ("other", "Other"),
                ],
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="maintenancerequest",
            name="assigned_reviewer",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assigned_maintenance_reviews",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="maintenancerequest",
            name="review_due_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
    ]
