from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0053_remove_combatstate_pending_enemy_attack_json"),
    ]

    operations = [
        migrations.AlterField(
            model_name="scene",
            name="quest",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="scenes",
                to="game.quest",
            ),
        ),
    ]
