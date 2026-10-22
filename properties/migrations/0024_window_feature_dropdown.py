from django.db import migrations, models


def preserve_values(apps, schema_editor):
    Profile = apps.get_model("properties", "PropertyProfile")
    alias = schema_editor.connection.alias
    for profile in Profile.objects.using(alias).all().iterator():
        value = profile.window_features or ""
        profile.window_features_types = [value] if value else []
        profile.save(using=alias, update_fields=["window_features_types"])


class Migration(migrations.Migration):
    dependencies = [("properties", "0023_physical_feature_dropdowns")]
    operations = [
        migrations.AddField(model_name="propertyprofile", name="window_features_types", field=models.JSONField(default=list, blank=True)),
        migrations.RunPython(preserve_values, migrations.RunPython.noop),
    ]
