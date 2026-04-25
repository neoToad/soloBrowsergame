from django.db import migrations, models


def forwards_copy_pending_attack(apps, schema_editor):
    CombatState = apps.get_model("game", "CombatState")
    for state in CombatState.objects.all().iterator():
        if state.pending_e_roll is None:
            state.pending_enemy_attack = None
        else:
            state.pending_enemy_attack = {
                "roll": state.pending_e_roll,
                "total": state.pending_e_total,
                "hit": state.pending_e_hit,
                "damage": state.pending_e_dmg,
            }
        state.save(update_fields=["pending_enemy_attack"])


def backwards_copy_pending_attack(apps, schema_editor):
    CombatState = apps.get_model("game", "CombatState")
    for state in CombatState.objects.all().iterator():
        attack = state.pending_enemy_attack or {}
        state.pending_e_roll = attack.get("roll")
        state.pending_e_total = attack.get("total")
        state.pending_e_hit = attack.get("hit")
        state.pending_e_dmg = attack.get("damage")
        state.save(
            update_fields=[
                "pending_e_roll",
                "pending_e_total",
                "pending_e_hit",
                "pending_e_dmg",
            ]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("game", "0042_gamesession_turn_counter_job_contactjoboffer_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="combatstate",
            name="pending_enemy_attack",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.RunPython(
            forwards_copy_pending_attack,
            backwards_copy_pending_attack,
        ),
        migrations.RemoveField(
            model_name="combatstate",
            name="pending_e_roll",
        ),
        migrations.RemoveField(
            model_name="combatstate",
            name="pending_e_total",
        ),
        migrations.RemoveField(
            model_name="combatstate",
            name="pending_e_hit",
        ),
        migrations.RemoveField(
            model_name="combatstate",
            name="pending_e_dmg",
        ),
    ]
