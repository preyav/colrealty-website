# rentals/migrations/0002_rental_rich_fields.py
# Run: python manage.py migrate

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rentals', '0001_initial'),
    ]

    operations = [
        migrations.AddField(model_name='rental', name='county', field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name='rental', name='subdivision', field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name='rental', name='deposit', field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
        migrations.AddField(model_name='rental', name='lease_term', field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name='rental', name='pets_allowed', field=models.BooleanField(blank=True, null=True)),
        migrations.AddField(model_name='rental', name='utilities_included', field=models.TextField(blank=True)),
        migrations.AddField(model_name='rental', name='baths_full', field=models.IntegerField(blank=True, null=True)),
        migrations.AddField(model_name='rental', name='baths_half', field=models.IntegerField(blank=True, null=True)),
        migrations.AddField(model_name='rental', name='lot_size', field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
        migrations.AddField(model_name='rental', name='year_built', field=models.IntegerField(blank=True, null=True)),
        migrations.AddField(model_name='rental', name='stories', field=models.IntegerField(blank=True, null=True)),
        migrations.AddField(model_name='rental', name='garage_spaces', field=models.IntegerField(blank=True, null=True)),
        migrations.AddField(model_name='rental', name='interior_features', field=models.TextField(blank=True)),
        migrations.AddField(model_name='rental', name='exterior_features', field=models.TextField(blank=True)),
        migrations.AddField(model_name='rental', name='community_features', field=models.TextField(blank=True)),
        migrations.AddField(model_name='rental', name='appliances', field=models.TextField(blank=True)),
        migrations.AddField(model_name='rental', name='flooring', field=models.TextField(blank=True)),
        migrations.AddField(model_name='rental', name='laundry_features', field=models.TextField(blank=True)),
        migrations.AddField(model_name='rental', name='has_fireplace', field=models.BooleanField(blank=True, null=True)),
        migrations.AddField(model_name='rental', name='has_pool', field=models.BooleanField(blank=True, null=True)),
        migrations.AddField(model_name='rental', name='has_garage', field=models.BooleanField(blank=True, null=True)),
        migrations.AddField(model_name='rental', name='heating', field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name='rental', name='cooling', field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name='rental', name='school_district', field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name='rental', name='elementary_school', field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name='rental', name='middle_school', field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name='rental', name='high_school', field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name='rental', name='available_date', field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name='rental', name='open_house_date', field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name='rental', name='open_house_start_time', field=models.TimeField(blank=True, null=True)),
        migrations.AddField(model_name='rental', name='open_house_end_time', field=models.TimeField(blank=True, null=True)),
        migrations.AddField(model_name='rental', name='virtual_tour_url', field=models.URLField(blank=True, max_length=1000)),
        migrations.AddField(model_name='rental', name='days_on_market', field=models.IntegerField(blank=True, null=True)),
        migrations.AddField(model_name='rental', name='directions', field=models.TextField(blank=True)),
    ]
