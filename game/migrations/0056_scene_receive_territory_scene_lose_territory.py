from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0055_territory_playerterritory"),
    ]

    operations = [
        migrations.AddField(
            model_name="scene",
            name="lose_territory",
            field=models.ForeignKey(
                blank=True,
                help_text="Territory lost when arriving at this scene.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="game.territory",
            ),
        ),
        migrations.AddField(
            model_name="scene",
            name="receive_territory",
            field=models.ForeignKey(
                blank=True,
                help_text="Territory awarded when arriving at this scene.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="game.territory",
            ),
        ),
    ]
