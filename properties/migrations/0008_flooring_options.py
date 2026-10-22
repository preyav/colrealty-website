from django.db import migrations, models


def seed_options(apps, schema_editor):
    Option = apps.get_model("properties", "FlooringOption")
    # Initial vocabulary only; administrators can add, relabel, reorder or retire it.
    labels = ["Adobe", "Bamboo", "Brick", "Carpet", "Concrete", "Cork", "Laminate", "Linoleum", "Marble", "Parquet", "Slate", "Stone", "Terrazzo", "Tile", "Vinyl", "Wood", "Other"]
    for order, label in enumerate(labels):
        Option.objects.using(schema_editor.connection.alias).get_or_create(
            code=label.lower(), defaults={"label": label, "sort_order": order},
        )


class Migration(migrations.Migration):
    dependencies = [("properties", "0007_property_profile_sections")]
    operations = [
        migrations.CreateModel(
            name="FlooringOption",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.SlugField(max_length=80, unique=True)),
                ("label", models.CharField(max_length=120)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ("sort_order", "label", "pk")},
        ),
        migrations.AddField(model_name="propertyprofile", name="flooring_types", field=models.JSONField(blank=True, default=list)),
        migrations.RunPython(seed_options, migrations.RunPython.noop),
    ]
