from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("properties", "0024_window_feature_dropdown")]
    operations = [
        migrations.AddField(model_name="property", name="main_level_bedrooms", field=models.PositiveSmallIntegerField(null=True, blank=True)),
        migrations.AddField(model_name="property", name="other_level_beds", field=models.PositiveSmallIntegerField(null=True, blank=True)),
    ]
