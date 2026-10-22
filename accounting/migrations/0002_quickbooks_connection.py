import django.conf
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounting", "0001_initial"),
        migrations.swappable_dependency(django.conf.settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="QuickBooksConnection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("realm_id", models.CharField(max_length=100, unique=True)),
                ("company_name", models.CharField(blank=True, max_length=255)),
                ("environment", models.CharField(choices=[("sandbox", "Sandbox"), ("production", "Production")], max_length=20)),
                ("access_token_encrypted", models.TextField()),
                ("refresh_token_encrypted", models.TextField()),
                ("access_token_expires_at", models.DateTimeField()),
                ("refresh_token_expires_at", models.DateTimeField(blank=True, null=True)),
                ("connected_at", models.DateTimeField(auto_now_add=True)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("connected_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="quickbooks_connections", to=django.conf.settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-connected_at"]},
        ),
    ]
