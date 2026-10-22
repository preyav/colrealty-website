from django.db import migrations, models


INITIAL_OPTIONS = [('none', 'None'), ('see-remarks', 'See Remarks'), ('balcony', 'Balcony'), ('barbecue', 'Barbecue'), ('basketball-court', 'Basketball Court'), ('boat-dock-private', 'Boat Dock - Private'), ('boat-dock-shared', 'Boat Dock - Shared'), ('boat-lift', 'Boat Lift'), ('boat-lock', 'Boat Lock'), ('boat-ramp', 'Boat Ramp'), ('boat-slip', 'Boat Slip'), ('courtyard-covered', 'Courtyard-Covered'), ('courtyard-uncovered', 'Courtyard-Uncovered'), ('dog-run', 'Dog Run'), ('electric-car-plug-in', 'Electric Car Plug-in'), ('exterior-steps', 'Exterior Steps'), ('garden', 'Garden'), ('gray-water-system', 'Gray Water System'), ('grill-electric', 'Grill-Electric'), ('grill-gas', 'Grill-Gas'), ('gutters-full', 'Gutters-Full'), ('gutters-partial', 'Gutters-Partial'), ('kennel', 'Kennel'), ('lighting', 'Lighting'), ('misting-system', 'Misting System'), ('no-exterior-steps', 'No Exterior Steps'), ('outdoor-grill', 'Outdoor Grill'), ('permeable-paving', 'Permeable Paving'), ('pest-tubes-in-walls', 'Pest Tubes in Walls'), ('playground', 'Playground'), ('private-entrance', 'Private Entrance'), ('private-yard', 'Private Yard'), ('restricted-access', 'Restricted Access'), ('rv-hookup', 'RV Hookup'), ('satellite-dish-leased', 'Satellite Dish Leased'), ('satellite-dish-owned', 'Satellite Dish Owned'), ('sport-court', 'Sport Court'), ('tennis-courts', 'Tennis Court(s)'), ('other', 'Other')]


def seed_options(apps, schema_editor):
    Option = apps.get_model("properties", "ExteriorFeatureOption")
    for order, (code, label) in enumerate(INITIAL_OPTIONS):
        Option.objects.using(schema_editor.connection.alias).get_or_create(
            code=code, defaults={"label": label, "sort_order": order},
        )


class Migration(migrations.Migration):
    dependencies = [("properties", "0009_interior_feature_options")]
    operations = [
        migrations.CreateModel(
            name="ExteriorFeatureOption",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.SlugField(max_length=80, unique=True)),
                ("label", models.CharField(max_length=120)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ("sort_order", "label", "pk")},
        ),
        migrations.AddField(model_name="propertyprofile", name="exterior_feature_types", field=models.JSONField(blank=True, default=list)),
        migrations.RunPython(seed_options, migrations.RunPython.noop),
    ]
