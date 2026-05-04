from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("game", "0060_scene_discover_territory_and_scene_gang_standing"),
    ]

    operations = [
        migrations.DeleteModel(
            name="JobRun",
        ),
        migrations.DeleteModel(
            name="PlayerContactOfferState",
        ),
        migrations.DeleteModel(
            name="PlayerJobState",
        ),
        migrations.DeleteModel(
            name="JobBeatVariant",
        ),
        migrations.DeleteModel(
            name="JobApproach",
        ),
        migrations.DeleteModel(
            name="ContactJobOffer",
        ),
        migrations.DeleteModel(
            name="Job",
        ),
    ]
