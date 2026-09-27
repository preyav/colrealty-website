# Initial COL360 Audit Ledger migration.

import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditLedgerState",
            fields=[
                ("id", models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ("last_event_id", models.UUIDField(blank=True, null=True)),
                ("last_hash", models.CharField(blank=True, default="", max_length=64)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "audit ledger state",
                "verbose_name_plural": "audit ledger state",
            },
        ),
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_id", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ("occurred_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, editable=False)),
                ("actor_display", models.CharField(blank=True, default="", max_length=255)),
                ("action", models.CharField(db_index=True, max_length=100)),
                ("entity_type", models.CharField(db_index=True, max_length=100)),
                ("entity_id", models.CharField(db_index=True, max_length=100)),
                ("entity_display", models.CharField(blank=True, default="", max_length=500)),
                ("property_id", models.CharField(blank=True, db_index=True, default="", max_length=100)),
                ("old_values", models.JSONField(blank=True, default=dict)),
                ("new_values", models.JSONField(blank=True, default=dict)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("reason", models.TextField(blank=True, default="")),
                ("source", models.CharField(blank=True, default="COL360 Web Portal", max_length=100)),
                ("request_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("previous_hash", models.CharField(blank=True, default="", max_length=64)),
                ("event_hash", models.CharField(editable=False, max_length=64, unique=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_events", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-occurred_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(fields=["entity_type", "entity_id", "-occurred_at"], name="audit_audit_entity__57c671_idx"),
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(fields=["property_id", "-occurred_at"], name="audit_audit_propert_0f4217_idx"),
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(fields=["action", "-occurred_at"], name="audit_audit_action_1c69a4_idx"),
        ),
    ]
