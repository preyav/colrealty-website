from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("listings", "0005_merge_20260225_2139"),
    ]

    operations = [
        migrations.AddField(
            model_name="listing",
            name="image_urls",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
