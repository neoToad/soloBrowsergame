from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0054_scene_quest_cascade_delete"),
    ]

    operations = [
        migrations.CreateModel(
            name="Territory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.SlugField(unique=True)),
                ("name", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True, null=True)),
                ("cash_per_turn", models.IntegerField(default=0)),
                ("heat_per_turn", models.IntegerField(default=0)),
                ("rep_per_turn", models.IntegerField(default=0)),
                ("is_contestable", models.BooleanField(default=False)),
                (
                    "resolution_scene",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="game.scene",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="PlayerTerritory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_contested", models.BooleanField(default=False)),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="territories",
                        to="game.gamesession",
                    ),
                ),
                ("territory", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="game.territory")),
            ],
        ),
    ]
