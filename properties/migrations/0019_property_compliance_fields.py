from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("properties", "0018_levels_and_room_counts")]
    operations = [
        migrations.AddField(model_name="propertyprofile", name="fema_flood_plain", field=models.CharField(max_length=255, blank=True, default="")),
        migrations.AddField(model_name="propertyprofile", name="housing_vouchers", field=models.CharField(max_length=3, blank=True, default="", choices=[("yes", "Yes"), ("no", "No")])),
        migrations.AddField(model_name="propertyprofile", name="etj", field=models.CharField(max_length=255, blank=True, default="")),
    ]
