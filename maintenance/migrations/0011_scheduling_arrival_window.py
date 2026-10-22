from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("maintenance", "0010_separate_vendor_award_assignment"),
    ]

    operations = [
        migrations.AddField(
            model_name="workorder",
            name="scheduled_until",
            field=models.DateTimeField(
                blank=True,
                help_text="End of the vendor's scheduled arrival window.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="vendorassignment",
            name="scheduled_until",
            field=models.DateTimeField(
                blank=True,
                help_text="End of the vendor's scheduled arrival window.",
                null=True,
            ),
        ),
    ]
