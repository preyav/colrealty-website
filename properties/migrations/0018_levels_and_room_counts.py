from django.db import migrations, models


def preserve_levels(apps, schema_editor):
    Profile = apps.get_model("properties", "PropertyProfile")
    for profile in Profile.objects.using(schema_editor.connection.alias).exclude(levels=None).iterator():
        profile.level_types = [str(profile.levels)]
        profile.save(update_fields=["level_types"], using=schema_editor.connection.alias)


class Migration(migrations.Migration):
    dependencies = [("properties", "0017_tax_legal_description")]
    operations = [
        migrations.AddField(model_name="propertyprofile", name="level_types", field=models.JSONField(default=list, blank=True)),
        migrations.AddField(model_name="propertyprofile", name="living_areas", field=models.PositiveSmallIntegerField(null=True, blank=True)),
        migrations.AddField(model_name="propertyprofile", name="dining_areas", field=models.PositiveSmallIntegerField(null=True, blank=True)),
        migrations.RunPython(preserve_levels, migrations.RunPython.noop),
    ]
