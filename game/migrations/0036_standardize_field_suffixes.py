from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0035_combatstate_pending_enemy_attack'),
    ]

    operations = [
        # Scene: cash_reward → cash_change, rep_reward → rep_change
        migrations.RenameField(
            model_name='scene',
            old_name='cash_reward',
            new_name='cash_change',
        ),
        migrations.RenameField(
            model_name='scene',
            old_name='rep_reward',
            new_name='rep_change',
        ),
        # Property: income_per_turn → cash_per_turn, heat_reduction → heat_per_turn, rep_bonus → rep_per_turn
        migrations.RenameField(
            model_name='property',
            old_name='income_per_turn',
            new_name='cash_per_turn',
        ),
        migrations.RenameField(
            model_name='property',
            old_name='heat_reduction',
            new_name='heat_per_turn',
        ),
        migrations.RenameField(
            model_name='property',
            old_name='rep_bonus',
            new_name='rep_per_turn',
        ),
    ]
