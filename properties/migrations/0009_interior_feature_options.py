from django.db import migrations, models


INITIAL_OPTIONS = [('none', 'None'), ('see-remarks', 'See Remarks'), ('2-primary-baths', '2 Primary Baths'), ('2-primary-suites', '2 Primary Suites'), ('bar', 'Bar'), ('bidet', 'Bidet'), ('bookcases', 'Bookcases'), ('breakfast-bar', 'Breakfast Bar'), ('built-in-features', 'Built-in Features'), ('cedar-closets', 'Cedar Closet(s)'), ('ceiling-fans', 'Ceiling Fan(s)'), ('ceilings-beamed', 'Ceiling(s)-Beamed'), ('ceilings-cathedral', 'Ceiling(s)-Cathedral'), ('ceilings-coffered', 'Ceiling(s)-Coffered'), ('ceilings-high', 'Ceiling(s)-High'), ('ceilings-tray', 'Ceiling(s)-Tray'), ('ceilings-vaulted', 'Ceiling(s)-Vaulted'), ('central-vacuum', 'Central Vacuum'), ('chandelier', 'Chandelier'), ('counter-corian', 'Counter-Corian'), ('counter-granite', 'Counter-Granite'), ('counter-laminate', 'Counter-Laminate'), ('counter-quartz', 'Counter-Quartz'), ('counter-stone', 'Counter-Stone'), ('counter-tile', 'Counter-Tile'), ('crown-molding', 'Crown Molding'), ('double-vanity', 'Double Vanity'), ('dry-bar', 'Dry Bar'), ('dryer-electric-hookup', 'Dryer-Electric Hookup'), ('dryer-gas-hookup', 'Dryer-Gas Hookup'), ('dumbwaiter', 'Dumbwaiter'), ('eat-in-kitchen', 'Eat-in Kitchen'), ('elevator', 'Elevator'), ('entrance-foyer', 'Entrance Foyer'), ('french-doors', 'French Doors'), ('high-speed-internet', 'High Speed Internet'), ('in-law-floorplan', 'In-Law Floorplan'), ('intercom', 'Intercom'), ('interior-steps', 'Interior Steps'), ('kitchen-island', 'Kitchen Island'), ('low-flow-plumbing-fixtures', 'Low Flow Plumbing Fixtures'), ('multiple-dining-areas', 'Multiple Dining Areas'), ('multiple-living-areas', 'Multiple Living Areas'), ('murphy-bed', 'Murphy Bed'), ('natural-woodwork', 'Natural Woodwork'), ('no-interior-steps', 'No Interior Steps'), ('open-floorplan', 'Open Floorplan'), ('pantry', 'Pantry'), ('primary-bedroom-on-main', 'Primary Bedroom on Main'), ('recessed-lighting', 'Recessed Lighting'), ('sauna', 'Sauna'), ('smart-home', 'Smart Home'), ('smart-thermostat', 'Smart Thermostat'), ('soaking-tub', 'Soaking Tub'), ('solar-tubes', 'Solar Tube(s)'), ('sound-system', 'Sound System'), ('stackable-wd-connections', 'Stackable W/D Connections'), ('storage', 'Storage'), ('studyhome-office', 'Study/Home Office'), ('track-lighting', 'Track Lighting'), ('two-primary-closets', 'Two Primary Closets'), ('walk-in-closets', 'Walk-In Closet(s)'), ('washer-hookup', 'Washer Hookup'), ('watersense-fixtures', 'WaterSense Fixture(s)'), ('wet-bar', 'Wet Bar'), ('wired-for-data', 'Wired for Data'), ('wired-for-sound', 'Wired for Sound'), ('other', 'Other')]


def seed_options(apps, schema_editor):
    Option = apps.get_model("properties", "InteriorFeatureOption")
    for order, (code, label) in enumerate(INITIAL_OPTIONS):
        Option.objects.using(schema_editor.connection.alias).get_or_create(
            code=code, defaults={"label": label, "sort_order": order},
        )


class Migration(migrations.Migration):
    dependencies = [("properties", "0008_flooring_options")]
    operations = [
        migrations.CreateModel(
            name="InteriorFeatureOption",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.SlugField(max_length=80, unique=True)),
                ("label", models.CharField(max_length=120)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ("sort_order", "label", "pk")},
        ),
        migrations.AddField(model_name="propertyprofile", name="interior_feature_types", field=models.JSONField(blank=True, default=list)),
        migrations.RunPython(seed_options, migrations.RunPython.noop),
    ]
