from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("game", "0052_combatstate_pending_enemy_attack_fields"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="combatstate",
            name="pending_enemy_attack",
        ),
    ]
