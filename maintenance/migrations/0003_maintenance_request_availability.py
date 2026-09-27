from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("maintenance", "0002_maintenancephoto_vendorestimate_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="maintenancerequest",
            name="availability_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="maintenancerequest",
            name="availability_start_time",
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="maintenancerequest",
            name="availability_end_time",
            field=models.TimeField(blank=True, null=True),
        ),
    ]
