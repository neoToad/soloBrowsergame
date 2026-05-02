from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("game", "0059_playerdiscoveredterritory"),
    ]

    operations = [
        migrations.AddField(
            model_name="scene",
            name="discover_territory",
            field=models.ForeignKey(
                blank=True,
                help_text="Territory discovered when arriving at this scene.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="game.territory",
            ),
        ),
        migrations.CreateModel(
            name="SceneGangStanding",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("standing_change", models.IntegerField(default=0)),
                (
                    "gang",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="scene_standing_changes",
                        to="game.gang",
                    ),
                ),
                (
                    "scene",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="scene_gang_standings",
                        to="game.scene",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("scene", "gang"), name="uq_scenegangstanding_scene_gang"),
                ],
            },
        ),
    ]
