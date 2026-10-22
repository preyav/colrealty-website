from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('properties', '0025_bedroom_level_counts')]
    operations = [
        migrations.AlterField(
            model_name='propertyprofile',
            name='ownership_type',
            field=models.CharField(max_length=30, blank=True, default='', choices=[('freehold', 'Fee Simple'), ('condominium', 'Condo Ownership (Airspace + Common Interest)'), ('fee_simple_or_pud', 'Fee Simple or PUD (Planned Unit Development)'), ('attached_fee_simple', 'Fee Simple (once permanently attached)'), ('chattel_or_real', 'Personal Property (Chattel) OR Real Property'), ('chattel_or_leasehold', 'Personal Property (Chattel) or Leasehold'), ('leasehold', 'Leasehold'), ('other', 'Other')]),
        ),
    ]
