from django.db import migrations, models


def preserve_values(apps, schema_editor):
    alias = schema_editor.connection.alias
    Profile = apps.get_model("properties", "PropertyProfile")
    Marketing = apps.get_model("properties", "PropertyMarketingDefaults")
    Property = apps.get_model("properties", "Property")
    fema_codes = {"see remarks": "see_remarks", "partial": "partial", "yes-500 yr": "yes_500_year", "no": "no", "yes-100 yr": "yes_100_year"}
    etj_codes = {"see remarks": "see_remarks", "yes": "yes", "no": "no"}
    for profile in Profile.objects.using(alias).all().iterator():
        previous = profile.fema_flood_plain or ""
        profile.fema_flood_plain_types = [fema_codes.get(previous.strip().lower(), previous)] if previous else []
        profile.etj = etj_codes.get((profile.etj or "").strip().lower(), profile.etj)
        profile.save(using=alias, update_fields=["fema_flood_plain_types", "etj"])
    for marketing in Marketing.objects.using(alias).exclude(private_remarks="").iterator():
        prop = Property.objects.using(alias).get(pk=marketing.property_id)
        remarks = marketing.private_remarks
        if prop.notes != remarks:
            prop.notes = (prop.notes + "\n\n" if prop.notes else "") + remarks
            prop.save(using=alias, update_fields=["notes"])
        # Retain the old column as an archive; it is no longer an editor field.


class Migration(migrations.Migration):
    dependencies = [("properties", "0019_property_compliance_fields")]
    operations = [
        migrations.AddField(model_name="propertyprofile", name="fema_flood_plain_types", field=models.JSONField(default=list, blank=True)),
        migrations.RunPython(preserve_values, migrations.RunPython.noop),
    ]
