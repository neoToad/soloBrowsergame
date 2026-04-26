from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("game", "0048_property_description"),
    ]

    operations = [
        migrations.AddField(
            model_name="requirementgroup",
            name="group_key",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="requirementgroup",
            name="scope_key",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="requirementgroup",
            name="scope_type",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddConstraint(
            model_name="requirementgroup",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("scope_key__isnull", False),
                    ("scope_type__isnull", False),
                    ("group_key__isnull", False),
                ),
                fields=("scope_type", "scope_key", "group_key"),
                name="uq_requirement_group_scoped_identity",
            ),
        ),
    ]
