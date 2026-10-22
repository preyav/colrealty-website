from django.db import migrations, models


FIELDS = ("lot_features", "accessibility_features", "pool_features", "spa_features", "security_features", "fireplace_features")


def preserve_values(apps, schema_editor):
    Profile = apps.get_model("properties", "PropertyProfile")
    alias = schema_editor.connection.alias
    for profile in Profile.objects.using(alias).all().iterator():
        for name in FIELDS:
            value = getattr(profile, name) or ""
            setattr(profile, name + "_types", [value] if value else [])
        profile.save(using=alias, update_fields=[name + "_types" for name in FIELDS])


class Migration(migrations.Migration):
    dependencies = [("properties", "0022_equipment_dropdowns")]
    operations = [
        migrations.AddField(model_name="propertyprofile", name="move_in_special_yn", field=models.CharField(max_length=3, blank=True, default="", choices=[("yes", "Yes"), ("no", "No")])),
        migrations.AddField(model_name="propertyprofile", name="move_in_special_description", field=models.TextField(max_length=1000, blank=True, default="")),
    ] + [migrations.AddField(model_name="propertyprofile", name=name + "_types", field=models.JSONField(default=list, blank=True)) for name in FIELDS] + [migrations.RunPython(preserve_values, migrations.RunPython.noop)]
