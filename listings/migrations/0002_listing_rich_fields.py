# listings/migrations/0002_listing_rich_fields.py
# Run: python manage.py migrate

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0001_initial'),
    ]

    operations = [
        migrations.AddField(model_name='listing', name='county', field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name='listing', name='subdivision', field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name='listing', name='original_list_price', field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
        migrations.AddField(model_name='listing', name='tax_amount', field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
        migrations.AddField(model_name='listing', name='tax_year', field=models.IntegerField(blank=True, null=True)),
        migrations.AddField(model_name='listing', name='hoa_fee', field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
        migrations.AddField(model_name='listing', name='hoa_frequency', field=models.CharField(blank=True, max_length=50)),
        migrations.AddField(model_name='listing', name='buyer_agent_compensation', field=models.CharField(blank=True, max_length=50)),
        migrations.AddField(model_name='listing', name='baths_full', field=models.IntegerField(blank=True, null=True)),
        migrations.AddField(model_name='listing', name='baths_half', field=models.IntegerField(blank=True, null=True)),
        migrations.AddField(model_name='listing', name='lot_size_sqft', field=models.IntegerField(blank=True, null=True)),
        migrations.AddField(model_name='listing', name='stories', field=models.IntegerField(blank=True, null=True)),
        migrations.AddField(model_name='listing', name='garage_spaces', field=models.IntegerField(blank=True, null=True)),
        migrations.AddField(model_name='listing', name='parking_total', field=models.IntegerField(blank=True, null=True)),
        migrations.AddField(model_name='listing', name='interior_features', field=models.TextField(blank=True)),
        migrations.AddField(model_name='listing', name='exterior_features', field=models.TextField(blank=True)),
        migrations.AddField(model_name='listing', name='community_features', field=models.TextField(blank=True)),
        migrations.AddField(model_name='listing', name='parking_features', field=models.TextField(blank=True)),
        migrations.AddField(model_name='listing', name='appliances', field=models.TextField(blank=True)),
        migrations.AddField(model_name='listing', name='flooring', field=models.TextField(blank=True)),
        migrations.AddField(model_name='listing', name='laundry_features', field=models.TextField(blank=True)),
        migrations.AddField(model_name='listing', name='window_features', field=models.TextField(blank=True)),
        migrations.AddField(model_name='listing', name='patio_porch_features', field=models.TextField(blank=True)),
        migrations.AddField(model_name='listing', name='has_fireplace', field=models.BooleanField(blank=True, null=True)),
        migrations.AddField(model_name='listing', name='has_pool', field=models.BooleanField(blank=True, null=True)),
        migrations.AddField(model_name='listing', name='has_garage', field=models.BooleanField(blank=True, null=True)),
        migrations.AddField(model_name='listing', name='is_waterfront', field=models.BooleanField(blank=True, null=True)),
        migrations.AddField(model_name='listing', name='is_new_construction', field=models.BooleanField(blank=True, null=True)),
        migrations.AddField(model_name='listing', name='construction_materials', field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name='listing', name='foundation', field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name='listing', name='roof', field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name='listing', name='fencing', field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name='listing', name='direction_faces', field=models.CharField(blank=True, max_length=50)),
        migrations.AddField(model_name='listing', name='heating', field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name='listing', name='cooling', field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name='listing', name='sewer', field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name='listing', name='water_source', field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name='listing', name='school_district', field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name='listing', name='elementary_school', field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name='listing', name='middle_school', field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name='listing', name='high_school', field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name='listing', name='open_house_date', field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name='listing', name='open_house_start_time', field=models.TimeField(blank=True, null=True)),
        migrations.AddField(model_name='listing', name='open_house_end_time', field=models.TimeField(blank=True, null=True)),
        migrations.AddField(model_name='listing', name='virtual_tour_url', field=models.URLField(blank=True, max_length=1000)),
        migrations.AddField(model_name='listing', name='days_on_market', field=models.IntegerField(blank=True, null=True)),
        migrations.AddField(model_name='listing', name='directions', field=models.TextField(blank=True)),
    ]
