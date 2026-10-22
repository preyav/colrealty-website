from django.db import migrations, models


INITIAL_OPTIONS = [('none', 'None'), ('see-remarks', 'See Remarks'), ('aluminum', 'Aluminum'), ('asbestos-shingle', 'Asbestos Shingle'), ('asphalt', 'Asphalt'), ('bahama', 'Bahama'), ('barrel', 'Barrel'), ('bituthene', 'Bituthene'), ('built-up', 'Built-Up'), ('composition', 'Composition'), ('concrete', 'Concrete'), ('copper', 'Copper'), ('elastomeric', 'Elastomeric'), ('fiberglass', 'Fiberglass'), ('flat-tile', 'Flat Tile'), ('foam', 'Foam'), ('green-roof', 'Green Roof'), ('mansard', 'Mansard'), ('membrane', 'Membrane'), ('metal', 'Metal'), ('mixed', 'Mixed'), ('rolledhot-mop', 'Rolled/Hot Mop'), ('rubber', 'Rubber'), ('shake', 'Shake'), ('shingle', 'Shingle'), ('slate', 'Slate'), ('spanish-tile', 'Spanish Tile'), ('stone', 'Stone'), ('synthetic', 'Synthetic'), ('targravel', 'Tar/Gravel'), ('tile', 'Tile'), ('wood', 'Wood'), ('other', 'Other')]


def seed_options(apps, schema_editor):
    Option = apps.get_model("properties", "RoofOption")
    for order, (code, label) in enumerate(INITIAL_OPTIONS):
        Option.objects.using(schema_editor.connection.alias).get_or_create(
            code=code, defaults={"label": label, "sort_order": order},
        )


class Migration(migrations.Migration):
    dependencies = [("properties", "0012_foundation_options")]
    operations = [
        migrations.CreateModel(
            name="RoofOption",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.SlugField(max_length=80, unique=True)),
                ("label", models.CharField(max_length=120)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ("sort_order", "label", "pk")},
        ),
        migrations.AddField(model_name="propertyprofile", name="roof_types", field=models.JSONField(blank=True, default=list)),
        migrations.RunPython(seed_options, migrations.RunPython.noop),
    ]
