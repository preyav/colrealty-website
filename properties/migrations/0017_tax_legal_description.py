from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("properties", "0016_ownership_management_fields")]

    operations = [
        migrations.AddField(
            model_name="propertyprofile",
            name="tax_legal_description",
            field=models.CharField(max_length=255, blank=True, default=""),
        ),
    ]
