from types import SimpleNamespace
from unittest import TestCase

from game.services.combat_engine import (
    build_enemy_attack_log,
    build_player_attack_log,
    resolve_enemy_attack_roll,
    resolve_player_attack_roll,
)


class CombatEngineTest(TestCase):
    def test_resolve_player_attack_hit_applies_strength_modifier(self):
        stats = SimpleNamespace(strength=14)
        enemy = SimpleNamespace(defense=12)

        result = resolve_player_attack_roll(stats, enemy, roll=10, damage_die=4)

        self.assertTrue(result.hit)
        self.assertEqual(result.total, 12)
        self.assertEqual(result.damage_die, 4)
        self.assertEqual(result.damage, 6)

    def test_resolve_player_attack_miss_zeroes_damage_outputs(self):
        stats = SimpleNamespace(strength=8)
        enemy = SimpleNamespace(defense=20)

        result = resolve_player_attack_roll(stats, enemy, roll=10, damage_die=5)

        self.assertFalse(result.hit)
        self.assertEqual(result.total, 9)
        self.assertEqual(result.damage_die, 0)
        self.assertEqual(result.damage, 0)

    def test_resolve_enemy_attack_hit_uses_enemy_attack_modifier(self):
        enemy = SimpleNamespace(attack_modifier=3)
        stats = SimpleNamespace(agility=10)

        result = resolve_enemy_attack_roll(enemy, stats, roll=8, damage_die=3)

        self.assertTrue(result.hit)
        self.assertEqual(result.total, 11)
        self.assertEqual(result.damage, 3)
        self.assertEqual(result.damage_die, 3)

    def test_resolve_enemy_attack_miss_zeroes_damage_outputs(self):
        enemy = SimpleNamespace(attack_modifier=0)
        stats = SimpleNamespace(agility=18)

        result = resolve_enemy_attack_roll(enemy, stats, roll=5, damage_die=4)

        self.assertFalse(result.hit)
        self.assertEqual(result.total, 5)
        self.assertEqual(result.damage, 0)
        self.assertEqual(result.damage_die, 0)

    def test_build_player_attack_log_hit_and_miss(self):
        hit_log = build_player_attack_log(roll=14, mod_str="+2", total=16, defense=12, hit=True, damage=5)
        miss_log = build_player_attack_log(roll=3, mod_str="-1", total=2, defense=12, hit=False, damage=0)

        self.assertEqual(hit_log, "You move on him — roll 14 (+2) = 16 vs 12 — Hit! 5 damage.")
        self.assertEqual(miss_log, "You move on him — roll 3 (-1) = 2 vs 12 — Missed.")

    def test_build_enemy_attack_log_hit_and_miss(self):
        hit_log = build_enemy_attack_log(
            enemy_name="Corner Thug", roll=12, mod_str="+1", total=13, defense=11, hit=True, damage=3
        )
        miss_log = build_enemy_attack_log(
            enemy_name="Corner Thug", roll=2, mod_str="+1", total=3, defense=11, hit=False, damage=0
        )

        self.assertEqual(hit_log, "Corner Thug comes at you — roll 12 (+1) = 13 vs 11 — Hit! 3 damage.")
        self.assertEqual(miss_log, "Corner Thug comes at you — roll 2 (+1) = 3 vs 11 — Missed.")
