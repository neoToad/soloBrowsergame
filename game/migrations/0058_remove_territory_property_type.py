from django.db import migrations, models


def remove_legacy_territory_properties(apps, schema_editor):
    Property = apps.get_model("game", "Property")
    Property.objects.filter(property_type="territory").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0057_migrate_territory_data_from_property"),
    ]

    operations = [
        migrations.RunPython(remove_legacy_territory_properties, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="property",
            name="property_type",
            field=models.CharField(
                choices=[("safehouse", "Safe House"), ("business", "Business")],
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name="property",
            constraint=models.CheckConstraint(
                condition=models.Q(("property_type__in", ["safehouse", "business"])),
                name="property_type_no_territory",
            ),
        ),
    ]
