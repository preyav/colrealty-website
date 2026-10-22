from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('properties', '0027_property_subtypes'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name='property', name='street_number', field=models.CharField(max_length=40, blank=True, default='')),
        migrations.AddField(model_name='property', name='street_dir_prefix', field=models.CharField(max_length=2, blank=True, default='')),
        migrations.AddField(model_name='property', name='street_name', field=models.CharField(max_length=180, blank=True, default='')),
        migrations.AddField(model_name='property', name='street_suffix', field=models.CharField(max_length=40, blank=True, default='')),
        migrations.AddField(model_name='property', name='street_dir_suffix', field=models.CharField(max_length=2, blank=True, default='')),
        migrations.AddField(model_name='property', name='out_of_state_county', field=models.CharField(max_length=100, blank=True, default='')),
        migrations.AddField(model_name='property', name='out_of_state_city', field=models.CharField(max_length=100, blank=True, default='')),
        migrations.AddField(model_name='property', name='country', field=models.CharField(max_length=100, blank=True, default='United States of America')),
        migrations.AddField(model_name='property', name='zip_plus_four', field=models.CharField(max_length=4, blank=True, default='')),
        migrations.AddField(model_name='property', name='tax_block', field=models.CharField(max_length=100, blank=True, default='')),
        migrations.AddField(model_name='property', name='tax_lot', field=models.CharField(max_length=100, blank=True, default='')),
        migrations.AddField(model_name='property', name='parcel_number', field=models.CharField(max_length=255, blank=True, default='')),
        migrations.AddField(model_name='property', name='mls_area', field=models.CharField(max_length=100, blank=True, default='')),
        migrations.CreateModel(name='PropertyEditorDraft', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('payload', models.JSONField(default=dict)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='property_editor_drafts', to=settings.AUTH_USER_MODEL)),
            ('property', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='editor_drafts', to='properties.property')),
        ], options={'ordering': ['-updated_at']}),
    ]
