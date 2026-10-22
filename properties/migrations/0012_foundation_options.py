from django.db import migrations, models


INITIAL_OPTIONS = [('none', 'None'), ('see-remarks', 'See Remarks'), ('block', 'Block'), ('brickmortar', 'Brick/Mortar'), ('combination', 'Combination'), ('concrete-perimeter', 'Concrete Perimeter'), ('permanent', 'Permanent'), ('pillarpostpier', 'Pillar/Post/Pier'), ('raised', 'Raised'), ('slab', 'Slab'), ('other', 'Other')]


def seed_options(apps, schema_editor):
    Option = apps.get_model("properties", "FoundationOption")
    for order, (code, label) in enumerate(INITIAL_OPTIONS):
        Option.objects.using(schema_editor.connection.alias).get_or_create(
            code=code, defaults={"label": label, "sort_order": order},
        )


class Migration(migrations.Migration):
    dependencies = [("properties", "0011_construction_material_options")]
    operations = [
        migrations.CreateModel(
            name="FoundationOption",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.SlugField(max_length=80, unique=True)),
                ("label", models.CharField(max_length=120)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ("sort_order", "label", "pk")},
        ),
        migrations.AddField(model_name="propertyprofile", name="foundation_types", field=models.JSONField(blank=True, default=list)),
        migrations.RunPython(seed_options, migrations.RunPython.noop),
    ]
