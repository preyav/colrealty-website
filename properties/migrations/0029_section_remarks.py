from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('properties', '0028_address_fields_and_drafts')]
    operations = [
        migrations.AddField(model_name='propertyprofile', name='ownership_management_remarks', field=models.TextField(blank=True, default='', max_length=4000)),
        migrations.AddField(model_name='propertyprofile', name='property_overview_remarks', field=models.TextField(blank=True, default='', max_length=4000)),
        migrations.AddField(model_name='propertyprofile', name='physical_features_remarks', field=models.TextField(blank=True, default='', max_length=4000)),
        migrations.AddField(model_name='propertyprofile', name='utilities_services_remarks', field=models.TextField(blank=True, default='', max_length=4000)),
        migrations.AddField(model_name='propertyprofile', name='rules_compliance_remarks', field=models.TextField(blank=True, default='', max_length=4000)),
        migrations.AddField(model_name='propertyprofile', name='green_energy_remarks', field=models.TextField(blank=True, default='', max_length=4000)),
    ]
