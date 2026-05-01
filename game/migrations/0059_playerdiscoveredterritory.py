from django.db import migrations, models
import django.db.models.deletion


def backfill_discovered_territories(apps, schema_editor):
    PlayerTerritory = apps.get_model("game", "PlayerTerritory")
    PlayerDiscoveredTerritory = apps.get_model("game", "PlayerDiscoveredTerritory")
    for pt in PlayerTerritory.objects.all().iterator():
        PlayerDiscoveredTerritory.objects.get_or_create(
            session_id=pt.session_id,
            territory_id=pt.territory_id,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("game", "0058_remove_territory_property_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlayerDiscoveredTerritory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("discovered_at", models.DateTimeField(auto_now_add=True)),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="discovered_territories",
                        to="game.gamesession",
                    ),
                ),
                ("territory", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="discovered_by", to="game.territory")),
            ],
            options={
                "ordering": ["discovered_at"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("session", "territory"),
                        name="uq_playerdiscoveredterritory_session_territory",
                    ),
                ],
            },
        ),
        migrations.RunPython(backfill_discovered_territories, migrations.RunPython.noop),
    ]
