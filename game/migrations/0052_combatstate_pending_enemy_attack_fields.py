from django.db import migrations, models


def copy_pending_enemy_attack_json_to_fields(apps, schema_editor):
    CombatState = apps.get_model("game", "CombatState")
    for state in CombatState.objects.filter(pending_enemy_attack__isnull=False).iterator():
        payload = state.pending_enemy_attack
        if not isinstance(payload, dict):
            continue
        state.pending_enemy_roll = payload.get("roll")
        state.pending_enemy_total = payload.get("total")
        state.pending_enemy_hit = payload.get("hit")
        state.pending_enemy_damage = payload.get("damage")
        state.save(
            update_fields=[
                "pending_enemy_roll",
                "pending_enemy_total",
                "pending_enemy_hit",
                "pending_enemy_damage",
            ]
        )


def copy_pending_enemy_attack_fields_to_json(apps, schema_editor):
    CombatState = apps.get_model("game", "CombatState")
    for state in CombatState.objects.iterator():
        if (
            state.pending_enemy_roll is None
            or state.pending_enemy_total is None
            or state.pending_enemy_hit is None
            or state.pending_enemy_damage is None
        ):
            continue
        state.pending_enemy_attack = {
            "roll": state.pending_enemy_roll,
            "total": state.pending_enemy_total,
            "hit": state.pending_enemy_hit,
            "damage": state.pending_enemy_damage,
        }
        state.save(update_fields=["pending_enemy_attack"])


class Migration(migrations.Migration):
    dependencies = [
        ("game", "0051_property_key"),
    ]

    operations = [
        migrations.AddField(
            model_name="combatstate",
            name="pending_enemy_damage",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="combatstate",
            name="pending_enemy_hit",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="combatstate",
            name="pending_enemy_roll",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="combatstate",
            name="pending_enemy_total",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.RunPython(
            copy_pending_enemy_attack_json_to_fields,
            copy_pending_enemy_attack_fields_to_json,
        ),
    ]
