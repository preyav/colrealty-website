from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('properties', '0029_section_remarks')]
    operations = [migrations.AddField(model_name='propertyprofile', name='spa', field=models.CharField(max_length=3, blank=True, default='', choices=[('yes', 'Yes'), ('no', 'No')]))]
