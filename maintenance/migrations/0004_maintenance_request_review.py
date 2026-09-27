from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("maintenance", "0003_maintenance_request_availability"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="maintenancerequest",
            name="review_notes",
            field=models.TextField(
                blank=True,
                help_text="Internal notes recorded when the request is reviewed.",
            ),
        ),
        migrations.AddField(
            model_name="maintenancerequest",
            name="reviewed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="maintenancerequest",
            name="reviewed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reviewed_maintenance_requests",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
