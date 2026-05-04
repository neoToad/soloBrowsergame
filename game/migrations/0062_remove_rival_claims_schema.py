from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0061_remove_jobs_schema"),
    ]

    operations = [
        migrations.DeleteModel(
            name="RivalClaim",
        ),
        migrations.RemoveField(
            model_name="playerproperty",
            name="is_contested",
        ),
        migrations.RemoveField(
            model_name="playerterritory",
            name="is_contested",
        ),
        migrations.RemoveField(
            model_name="property",
            name="is_contestable",
        ),
        migrations.RemoveField(
            model_name="property",
            name="resolution_scene",
        ),
        migrations.RemoveField(
            model_name="territory",
            name="is_contestable",
        ),
        migrations.RemoveField(
            model_name="territory",
            name="resolution_scene",
        ),
    ]
