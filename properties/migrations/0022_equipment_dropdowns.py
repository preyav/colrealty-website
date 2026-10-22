from django.db import migrations, models


FIELDS = ("appliances", "cooling", "heating", "utility_services")


def preserve_values(apps, schema_editor):
    Profile = apps.get_model("properties", "PropertyProfile")
    alias = schema_editor.connection.alias
    for profile in Profile.objects.using(alias).all().iterator():
        for name in FIELDS:
            value = getattr(profile, name) or ""
            setattr(profile, name + "_types", [value] if value else [])
        profile.save(using=alias, update_fields=[name + "_types" for name in FIELDS])
        # Keep the original text columns as archives.


class Migration(migrations.Migration):
    dependencies = [("properties", "0021_merge_hoa_management_company")]
    operations = [
        migrations.AddField(model_name="propertyprofile", name=name + "_types", field=models.JSONField(default=list, blank=True))
        for name in FIELDS
    ] + [migrations.RunPython(preserve_values, migrations.RunPython.noop)]
