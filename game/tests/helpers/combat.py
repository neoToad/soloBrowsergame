from django.test import Client

from game.tests.factories import EnemyFactory, SceneFactory, bootstrap_game_session


def setup_combat_context(key_prefix):
    from game.models.combat import CombatEncounter

    client = Client()
    session = bootstrap_game_session(client)
    stats = session.stats

    enemy = EnemyFactory(
        key=f"{key_prefix}__enemy",
        name="Test Thug",
        description="",
        max_hp=20,
        attack_modifier=0,
        defense=8,
        damage_min=2,
        damage_max=4,
    )
    victory_scene = SceneFactory(
        key=f"{key_prefix}__victory", title="Victory", body="", scene_type="normal"
    )
    defeat_scene = SceneFactory(
        key=f"{key_prefix}__defeat",
        title="Defeat",
        body="",
        scene_type="ending",
        ending_type="defeat",
    )
    combat_scene = SceneFactory(
        key=f"{key_prefix}__combat", title="Combat", body="", scene_type="combat"
    )
    encounter = CombatEncounter.objects.create(
        scene=combat_scene,
        enemy=enemy,
        victory_scene=victory_scene,
        defeat_scene=defeat_scene,
    )
    session.current_scene = combat_scene
    session.save(update_fields=["current_scene"])

    return {
        "client": client,
        "session": session,
        "stats": stats,
        "enemy": enemy,
        "victory_scene": victory_scene,
        "defeat_scene": defeat_scene,
        "combat_scene": combat_scene,
        "encounter": encounter,
    }


def create_active_combat_state(session, enemy, **kwargs):
    from game.models.combat import CombatState

    defaults = dict(session=session, enemy=enemy, enemy_hp=20, turn_number=1, is_active=True)
    defaults.update(kwargs)
    return CombatState.objects.create(**defaults)
