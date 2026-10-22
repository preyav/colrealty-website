from django.db import migrations, models


def merge_hoa_names(apps, schema_editor):
    Profile = apps.get_model("properties", "PropertyProfile")
    alias = schema_editor.connection.alias
    for profile in Profile.objects.using(alias).all().iterator():
        name = profile.association_name or ""
        company = profile.hoa_management_company or ""
        if name and name != company:
            profile.hoa_management_company = name + ("\n\n" + company if company else "")
            profile.save(using=alias, update_fields=["hoa_management_company"])
        # Keep association_name as an archive; the editor uses only the merged field.


class Migration(migrations.Migration):
    dependencies = [("properties", "0020_compliance_dropdowns_and_notes")]
    operations = [
        migrations.AlterField(model_name="propertyprofile", name="hoa_management_company", field=models.TextField(blank=True, default="")),
        migrations.RunPython(merge_hoa_names, migrations.RunPython.noop),
    ]
