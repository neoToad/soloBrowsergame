from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from game.tests.factories import ChoiceFactory
from game.tests.helpers import create_active_combat_state, setup_combat_context


class CombatEnemyResolveServiceTest(TestCase):
    def setUp(self):
        self.ctx = setup_combat_context("cer")
        self.session = self.ctx["session"]
        self.stats = self.ctx["stats"]
        self.enemy = self.ctx["enemy"]
        self.defeat_scene = self.ctx["defeat_scene"]
        self.victory_scene = self.ctx["victory_scene"]
        self.encounter = self.ctx["encounter"]

    def test_enemy_attack_hit_reduces_player_hp(self):
        from game.services.combat import execute_enemy_attack

        cs = create_active_combat_state(
            self.session,
            self.enemy,
            pending_enemy_roll=10,
            pending_enemy_total=12,
            pending_enemy_hit=True,
            pending_enemy_damage=3,
        )
        self.stats.hp = 10
        self.stats.save(update_fields=["hp"])

        logs, _context = execute_enemy_attack(self.session, self.stats, {}, {}, cs, self.stats)

        self.stats.refresh_from_db()
        self.assertEqual(self.stats.hp, 7)
        cs.refresh_from_db()
        self.assertEqual(cs.turn_number, 2)
        self.assertFalse(cs.enemy_attack_pending)
        self.assertTrue(any("Hit! 3 damage." in line for line in logs))
        self.assertEqual(self.session.log.count(), 0)

    def test_enemy_attack_miss_leaves_hp_unchanged(self):
        from game.services.combat import execute_enemy_attack

        cs = create_active_combat_state(
            self.session,
            self.enemy,
            pending_enemy_roll=1,
            pending_enemy_total=1,
            pending_enemy_hit=False,
            pending_enemy_damage=0,
        )
        self.stats.hp = 10
        self.stats.save(update_fields=["hp"])

        logs, _context = execute_enemy_attack(self.session, self.stats, {}, {}, cs, self.stats)

        self.stats.refresh_from_db()
        self.assertEqual(self.stats.hp, 10)
        cs.refresh_from_db()
        self.assertEqual(cs.turn_number, 2)
        self.assertTrue(any("Missed." in line for line in logs))
        self.assertEqual(self.session.log.count(), 0)

    def test_enemy_attack_reduces_player_to_zero_transitions_to_defeat_scene(self):
        from game.services.combat import execute_enemy_attack

        cs = create_active_combat_state(
            self.session,
            self.enemy,
            pending_enemy_roll=15,
            pending_enemy_total=17,
            pending_enemy_hit=True,
            pending_enemy_damage=5,
        )
        self.stats.hp = 2
        self.stats.save(update_fields=["hp"])

        self.encounter.defeat_arrival_flavor = "You wake up in a cold alley."
        self.encounter.save(update_fields=["defeat_arrival_flavor"])

        logs, _context = execute_enemy_attack(self.session, self.stats, {}, {}, cs, self.stats)

        self.stats.refresh_from_db()
        self.assertEqual(self.stats.hp, 0)
        self.session.refresh_from_db()
        self.assertEqual(self.session.current_scene, self.defeat_scene)
        cs.refresh_from_db()
        self.assertFalse(cs.is_active)
        self.assertTrue(any("You're down. You lose consciousness." == line for line in logs))
        self.assertIn("You wake up in a cold alley.", logs)
        self.assertLess(logs.index("You're down. You lose consciousness."), logs.index("You wake up in a cold alley."))
        self.assertEqual(self.session.log.count(), 0)

    def test_run_enemy_attack_keeps_destination_scene_choices_after_defeat(self):
        from game.services.gameplay import run_enemy_attack

        ChoiceFactory(scene=self.defeat_scene, label="Regain your footing", target_scene=self.victory_scene)
        create_active_combat_state(
            self.session,
            self.enemy,
            pending_enemy_roll=15,
            pending_enemy_total=17,
            pending_enemy_hit=True,
            pending_enemy_damage=5,
        )
        self.stats.hp = 2
        self.stats.save(update_fields=["hp"])

        context = run_enemy_attack((self.session, self.stats, {}, self.stats, {}))

        self.assertEqual(context["scene"], self.defeat_scene)
        self.assertGreater(len(context["choices"]), 0)
        self.assertIn("Regain your footing", [choice.label for choice in context["choices"]])

    def test_consume_enemy_attack_raises_when_pending_attack_is_incomplete(self):
        from game.services.combat import consume_enemy_attack

        cs = create_active_combat_state(
            self.session,
            self.enemy,
            pending_enemy_roll=10,
            pending_enemy_total=12,
            pending_enemy_hit=None,
            pending_enemy_damage=3,
        )

        with self.assertRaises(ValueError) as ctx:
            consume_enemy_attack(cs)

        self.assertEqual(str(ctx.exception), "No pending enemy attack to consume.")


class CombatEnemyResolveViewTest(TestCase):
    def setUp(self):
        self.ctx = setup_combat_context("cerv")
        self.client = self.ctx["client"]
        self.session = self.ctx["session"]
        self.stats = self.ctx["stats"]
        self.enemy = self.ctx["enemy"]
        self.victory_scene = self.ctx["victory_scene"]
        self.combat_scene = self.ctx["combat_scene"]
        self.combat_narrative = "A siren wails somewhere beyond the rooftops."
        self.combat_scene.body = self.combat_narrative
        self.combat_scene.save(update_fields=["body"])
        create_active_combat_state(
            self.session,
            self.enemy,
            enemy_hp=self.enemy.max_hp,
            pending_enemy_roll=5,
            pending_enemy_total=5,
            pending_enemy_hit=False,
            pending_enemy_damage=0,
        )

    def test_combat_enemy_attack_view_applies_queued_attack(self):
        from game.models.combat import CombatState

        initial_hp = self.stats.hp
        response = self.client.post(reverse("combat_resolve_enemy"), HTTP_HX_REQUEST="true")

        self.assertEqual(response.status_code, 200)
        cs = CombatState.objects.get(session=self.session)
        self.assertFalse(cs.enemy_attack_pending)
        self.assertEqual(cs.turn_number, 2)
        self.stats.refresh_from_db()
        self.assertEqual(self.stats.hp, initial_hp)
        self.assertContains(response, "Your Turn")
        self.assertNotContains(response, self.combat_narrative)

    def test_combat_resolve_enemy_rejects_get_with_405(self):
        response = self.client.get(reverse("combat_resolve_enemy"))
        self.assertEqual(response.status_code, 405)

    def test_combat_enemy_resolve_returns_400_when_defeat_scene_missing(self):
        from game.models.combat import CombatEncounter, CombatState

        encounter = CombatEncounter.objects.get(scene=self.combat_scene)
        encounter.defeat_scene = None
        encounter.save(update_fields=["defeat_scene"])

        cs = CombatState.objects.get(session=self.session)
        cs.pending_enemy_roll = 18
        cs.pending_enemy_total = 18
        cs.pending_enemy_hit = True
        cs.pending_enemy_damage = 5
        cs.save(update_fields=["pending_enemy_roll", "pending_enemy_total", "pending_enemy_hit", "pending_enemy_damage"])
        self.stats.hp = 1
        self.stats.save(update_fields=["hp"])

        response = self.client.post(reverse("combat_resolve_enemy"), HTTP_HX_REQUEST="true")

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "missing defeat_scene", status_code=400)
        self.session.refresh_from_db()
        self.assertEqual(self.session.current_scene, self.combat_scene)
        cs.refresh_from_db()
        self.assertTrue(cs.is_active)

    def test_combat_enemy_resolve_shows_defeat_scene_choices_without_refresh(self):
        from game.models.combat import CombatState

        ChoiceFactory(scene=self.victory_scene, label="Press the edge", target_scene=self.victory_scene)

        cs = CombatState.objects.get(session=self.session)
        cs.pending_enemy_roll = 18
        cs.pending_enemy_total = 18
        cs.pending_enemy_hit = True
        cs.pending_enemy_damage = 999
        cs.save(update_fields=["pending_enemy_roll", "pending_enemy_total", "pending_enemy_hit", "pending_enemy_damage"])
        self.stats.hp = 1
        self.stats.save(update_fields=["hp"])

        encounter = self.combat_scene.combat_encounter
        encounter.defeat_scene = self.victory_scene
        encounter.save(update_fields=["defeat_scene"])

        response = self.client.post(reverse("combat_resolve_enemy"), HTTP_HX_REQUEST="true")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Press the edge")
        self.assertNotContains(response, "No choices available.")
