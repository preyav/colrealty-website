from django.db import migrations, models


def backfill_started_at(apps, schema_editor):
    WorkOrder = apps.get_model("maintenance", "WorkOrder")
    StatusHistory = apps.get_model("maintenance", "WorkOrderStatusHistory")

    for work_order in WorkOrder.objects.filter(
        status__in=["in_progress", "completed"]
    ).iterator():
        started_event = StatusHistory.objects.filter(
            work_order_id=work_order.pk,
            to_status="in_progress",
        ).order_by("changed_at").first()
        if started_event:
            WorkOrder.objects.filter(pk=work_order.pk).update(
                started_at=started_event.changed_at
            )


class Migration(migrations.Migration):
    dependencies = [
        ("maintenance", "0011_scheduling_arrival_window"),
    ]

    operations = [
        migrations.AddField(
            model_name="workorder",
            name="started_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Actual date and time work began.",
                null=True,
            ),
        ),
        migrations.RunPython(backfill_started_at, migrations.RunPython.noop),
    ]
