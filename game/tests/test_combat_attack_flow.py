from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from game.models import CompletedQuest
from game.tests.factories import SceneFactory
from game.tests.helpers import create_active_combat_state, setup_combat_context


class CombatAttackFlowTest(TestCase):
    def setUp(self):
        self.ctx = setup_combat_context("catk")
        self.client = self.ctx["client"]
        self.session = self.ctx["session"]
        self.stats = self.ctx["stats"]
        self.enemy = self.ctx["enemy"]
        self.combat_scene = self.ctx["combat_scene"]
        self.victory_scene = self.ctx["victory_scene"]
        self.cs = create_active_combat_state(self.session, self.enemy, enemy_hp=self.enemy.max_hp)

    def test_player_attack_non_killing_blow_returns_combat_panel(self):
        self.cs.enemy_hp = 100
        self.cs.save(update_fields=["enemy_hp"])

        with patch("game.services.combat.roll_d20", return_value=20):
            response = self.client.post(reverse("combat_attack"), HTTP_HX_REQUEST="true")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "combat-panel")
        self.assertContains(response, self.cs.enemy.name.upper())
        self.cs.refresh_from_db()
        self.assertLess(self.cs.enemy_hp, 100)

    def test_combat_victory_awards_xp_and_transitions_to_victory_scene(self):
        from game.services.progression import XP_AWARDS

        self.cs.enemy_hp = 1
        self.cs.save(update_fields=["enemy_hp"])
        self.stats.strength = 20
        self.stats.save(update_fields=["strength"])
        starting_xp = self.stats.experience
        starting_completed_quests = CompletedQuest.objects.filter(session=self.session).count()

        with patch("game.services.combat.roll_d20", return_value=20):
            self.client.post(reverse("combat_attack"), HTTP_HX_REQUEST="true")

        self.cs.refresh_from_db()
        self.assertTrue(self.cs.pending_victory)

        response = self.client.post(reverse("combat_continue"), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.stats.refresh_from_db()
        self.assertEqual(self.session.current_scene, self.victory_scene)
        self.assertEqual(self.stats.experience, starting_xp + XP_AWARDS["combat_victory"])
        self.assertTrue(
            self.session.log.filter(text__icontains=f"You gained {XP_AWARDS['combat_victory']} XP.").exists()
        )
        self.assertEqual(CompletedQuest.objects.filter(session=self.session).count(), starting_completed_quests)

    def test_combat_attack_rejects_get_with_405(self):
        response = self.client.get(reverse("combat_attack"))
        self.assertEqual(response.status_code, 405)

    def test_combat_attack_miss_renders_your_turn_badge_from_latest_event(self):
        self.cs.pending_enemy_roll = None
        self.cs.pending_enemy_total = None
        self.cs.pending_enemy_hit = None
        self.cs.pending_enemy_damage = None
        self.cs.enemy_hp = self.enemy.max_hp
        self.cs.save(
            update_fields=[
                "pending_enemy_roll",
                "pending_enemy_total",
                "pending_enemy_hit",
                "pending_enemy_damage",
                "enemy_hp",
            ]
        )

        with patch("game.services.combat.roll_d20", return_value=1):
            response = self.client.post(reverse("combat_attack"), HTTP_HX_REQUEST="true")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your Turn")
        self.assertContains(response, "roll-result--miss")

    def test_combat_attack_roll_header_uses_display_stat_name(self):
        self.cs.pending_enemy_roll = None
        self.cs.pending_enemy_total = None
        self.cs.pending_enemy_hit = None
        self.cs.pending_enemy_damage = None
        self.cs.save(
            update_fields=[
                "pending_enemy_roll",
                "pending_enemy_total",
                "pending_enemy_hit",
                "pending_enemy_damage",
            ]
        )

        with patch("game.services.combat.roll_d20", return_value=1):
            response = self.client.post(reverse("combat_attack"), HTTP_HX_REQUEST="true")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MUSCLE CHECK")

    def test_initialize_combat_state_deactivates_when_entering_non_combat_scene(self):
        from game.services.combat import initialize_combat_state

        normal_scene = SceneFactory(key="catk__normal", title="Normal", body="", scene_type="normal")

        result = initialize_combat_state(self.session, normal_scene)

        self.assertEqual(result, (None, None))
        self.cs.refresh_from_db()
        self.assertFalse(self.cs.is_active)

    def test_initialize_combat_state_recreates_deleted_inactive_state(self):
        from game.models.combat import CombatState
        from game.services.combat import initialize_combat_state

        self.cs.is_active = False
        self.cs.save(update_fields=["is_active"])
        old_pk = self.cs.pk

        new_cs, init_log = initialize_combat_state(self.session, self.combat_scene)

        self.assertFalse(CombatState.objects.filter(pk=old_pk).exists())
        self.assertIsNotNone(new_cs)
        self.assertTrue(new_cs.is_active)
        self.assertIn(self.enemy.name, init_log)
