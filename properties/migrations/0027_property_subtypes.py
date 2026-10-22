from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('properties', '0026_ownership_types')]
    operations = [
        migrations.AlterField(model_name='property', name='property_type', field=models.CharField(max_length=50, choices=[('single_family_residential', 'Single Family Residential'), ('condominium', 'Condominium'), ('manufactured_home', 'Manufactured Home'), ('mobile_home', 'Mobile Home'), ('modular', 'Modular'), ('townhouse', 'Townhouse'), ('apartments', 'Apartments'), ('duplex', 'Duplex'), ('triplex', 'Triplex'), ('quadruplex', 'Quadruplex'), ('other', 'Other')], verbose_name='Property Sub Type')),
        migrations.AlterField(model_name='propertyprofile', name='ownership_type', field=models.CharField(max_length=30, blank=True, default='', choices=[('freehold', 'Fee Simple'), ('condominium', 'Condo Ownership (Airspace + Common Interest)'), ('fee_simple_or_pud', 'Fee Simple or PUD (Planned Unit Development)'), ('attached_fee_simple', 'Fee Simple (once permanently attached)'), ('chattel_or_real', 'Personal Property (Chattel) OR Real Property'), ('chattel_or_leasehold', 'Personal Property (Chattel) or Leasehold'), ('apartment_leasehold', 'No direct ownership of the real estate unit (leasehold/tenant rights only).'), ('duplex_ownership', 'Two residential dwelling units attached in one building.'), ('triplex_ownership', 'Three residential dwelling units contained within a single property.'), ('quadruplex_ownership', 'Four residential dwelling units contained within a single property.'), ('leasehold', 'Leasehold'), ('other', 'Other')])),
    ]
