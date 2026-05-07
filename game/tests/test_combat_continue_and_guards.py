from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from game.tests.factories import ChoiceFactory
from game.tests.helpers import create_active_combat_state, setup_combat_context


class CombatContinueFlowTest(TestCase):
    def setUp(self):
        self.ctx = setup_combat_context("ccont")
        self.client = self.ctx["client"]
        self.session = self.ctx["session"]
        self.stats = self.ctx["stats"]
        self.enemy = self.ctx["enemy"]
        self.victory_scene = self.ctx["victory_scene"]
        self.combat_scene = self.ctx["combat_scene"]
        self.encounter = self.ctx["encounter"]

    def test_resolve_combat_end_returns_logs_and_does_not_persist_events(self):
        from game.services.combat import resolve_combat_end

        cs = create_active_combat_state(self.session, self.enemy)
        self.encounter.victory_arrival_flavor = "The crowd clears out."
        self.encounter.save(update_fields=["victory_arrival_flavor"])
        self.stats.heat = 5
        self.stats.save(update_fields=["heat"])
        self.victory_scene.cash_change = 7
        self.victory_scene.heat_change = -2
        self.victory_scene.rep_change = 3
        self.victory_scene.save(update_fields=["cash_change", "heat_change", "rep_change"])

        logs, context = resolve_combat_end(
            self.session, self.stats, {}, {}, self.victory_scene, cs, xp_award=1, ending_type="victory"
        )

        self.assertIn("The crowd clears out. You gained 1 XP, +$7 cash, -2 heat, +3 rep.", logs)
        self.assertNotIn("+1 XP.", logs)
        self.assertIn("scene", context)
        self.assertEqual(self.session.log.count(), 0)

    def test_resolve_combat_end_without_victory_flavor_still_logs_combined_rewards(self):
        from game.services.combat import resolve_combat_end

        cs = create_active_combat_state(self.session, self.enemy)
        self.victory_scene.cash_change = 4
        self.victory_scene.heat_change = 1
        self.victory_scene.rep_change = 2
        self.victory_scene.save(update_fields=["cash_change", "heat_change", "rep_change"])

        logs, _context = resolve_combat_end(
            self.session, self.stats, {}, {}, self.victory_scene, cs, xp_award=50, ending_type="victory"
        )
        self.assertIn("You gained 50 XP, +$4 cash, +1 heat, +2 rep.", logs)

    def test_combat_continue_rejects_get_with_405(self):
        response = self.client.get(reverse("combat_continue"))
        self.assertEqual(response.status_code, 405)

    def test_combat_continue_returns_400_when_victory_scene_missing(self):
        from game.models.combat import CombatEncounter

        encounter = CombatEncounter.objects.get(scene=self.combat_scene)
        encounter.victory_scene = None
        encounter.save(update_fields=["victory_scene"])
        cs = create_active_combat_state(self.session, self.enemy, pending_victory=True)

        response = self.client.post(reverse("combat_continue"), HTTP_HX_REQUEST="true")

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "missing victory_scene", status_code=400)
        self.session.refresh_from_db()
        self.assertEqual(self.session.current_scene, self.combat_scene)
        cs.refresh_from_db()
        self.assertTrue(cs.is_active)

    def test_combat_continue_shows_victory_scene_choices_without_refresh(self):
        ChoiceFactory(scene=self.victory_scene, label="Take the payout", target_scene=self.victory_scene)
        create_active_combat_state(self.session, self.enemy, pending_victory=True)

        response = self.client.post(reverse("combat_continue"), HTTP_HX_REQUEST="true")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Take the payout")
        self.assertNotContains(response, "No choices available.")


class CombatGameplayGuardTest(TestCase):
    def setUp(self):
        self.ctx = setup_combat_context("cguard")
        self.session = self.ctx["session"]
        self.stats = self.ctx["stats"]
        self.enemy = self.ctx["enemy"]
        self.combat_scene = self.ctx["combat_scene"]
        self.victory_scene = self.ctx["victory_scene"]
        self.encounter = self.ctx["encounter"]

    def test_require_active_combat_raises_when_missing_state(self):
        from game.services.gameplay.combat import _require_active_combat
        from game.services.types import GameplayError

        with self.assertRaises(GameplayError) as ctx:
            _require_active_combat(self.session)
        self.assertEqual(str(ctx.exception), "No active combat.")
        self.assertEqual(ctx.exception.status, 400)

    def test_require_active_combat_raises_when_state_inactive(self):
        from game.services.gameplay.combat import _require_active_combat
        from game.services.types import GameplayError

        create_active_combat_state(self.session, self.enemy, is_active=False)
        with self.assertRaises(GameplayError) as ctx:
            _require_active_combat(self.session)
        self.assertEqual(str(ctx.exception), "Combat is not active.")
        self.assertEqual(ctx.exception.status, 400)

    def test_run_enemy_attack_raises_when_no_pending_enemy_attack(self):
        from game.services.gameplay.combat import run_enemy_attack
        from game.services.types import GameplayError

        create_active_combat_state(self.session, self.enemy)
        with patch("game.services.gameplay.combat.flush_event_log") as flush_mock:
            with self.assertRaises(GameplayError) as ctx:
                run_enemy_attack((self.session, self.stats, {}, self.stats, {}))
        self.assertEqual(str(ctx.exception), "No pending enemy attack.")
        self.assertEqual(ctx.exception.status, 400)
        flush_mock.assert_not_called()

    def test_run_enemy_attack_raises_when_encounter_missing(self):
        from game.models.combat import CombatEncounter
        from game.services.gameplay.combat import run_enemy_attack
        from game.services.types import GameplayError

        create_active_combat_state(
            self.session,
            self.enemy,
            pending_enemy_roll=10,
            pending_enemy_total=12,
            pending_enemy_hit=True,
            pending_enemy_damage=3,
        )
        CombatEncounter.objects.filter(pk=self.encounter.pk).delete()

        with patch("game.services.gameplay.combat.flush_event_log") as flush_mock:
            with self.assertRaises(GameplayError) as ctx:
                run_enemy_attack((self.session, self.stats, {}, self.stats, {}))
        self.assertEqual(str(ctx.exception), "No combat encounter configured for this scene. Check quest content.")
        self.assertEqual(ctx.exception.status, 400)
        flush_mock.assert_not_called()

    def test_run_enemy_attack_clears_choices_when_combat_remains_active(self):
        from game.services.gameplay.combat import run_enemy_attack

        create_active_combat_state(
            self.session,
            self.enemy,
            pending_enemy_roll=10,
            pending_enemy_total=12,
            pending_enemy_hit=True,
            pending_enemy_damage=3,
        )
        expected_context = {"combat_state": self.session.combat_state, "choices": [object()], "scene": self.combat_scene}

        with patch("game.services.gameplay.combat.execute_enemy_attack", return_value=(["enemy acts"], expected_context)):
            with patch("game.services.gameplay.combat.flush_event_log") as flush_mock:
                context = run_enemy_attack((self.session, self.stats, {}, self.stats, {}))
        flush_mock.assert_called_once_with(self.session, ["enemy acts"])
        self.assertEqual(context["choices"], [])

    def test_run_combat_continue_raises_when_no_combat_state(self):
        from game.services.gameplay.combat import run_combat_continue
        from game.services.types import GameplayError

        with patch("game.services.gameplay.combat.flush_event_log") as flush_mock:
            with self.assertRaises(GameplayError) as ctx:
                run_combat_continue((self.session, self.stats, {}, self.stats, {}))
        self.assertEqual(str(ctx.exception), "No combat state.")
        self.assertEqual(ctx.exception.status, 400)
        flush_mock.assert_not_called()

    def test_run_combat_continue_raises_when_no_pending_victory(self):
        from game.services.gameplay.combat import run_combat_continue
        from game.services.types import GameplayError

        create_active_combat_state(self.session, self.enemy, pending_victory=False)
        with patch("game.services.gameplay.combat.flush_event_log") as flush_mock:
            with self.assertRaises(GameplayError) as ctx:
                run_combat_continue((self.session, self.stats, {}, self.stats, {}))
        self.assertEqual(str(ctx.exception), "No pending victory.")
        self.assertEqual(ctx.exception.status, 400)
        flush_mock.assert_not_called()

    def test_run_combat_continue_raises_when_encounter_missing(self):
        from game.models.combat import CombatEncounter
        from game.services.gameplay.combat import run_combat_continue
        from game.services.types import GameplayError

        create_active_combat_state(self.session, self.enemy, pending_victory=True)
        CombatEncounter.objects.filter(pk=self.encounter.pk).delete()

        with patch("game.services.gameplay.combat.flush_event_log") as flush_mock:
            with self.assertRaises(GameplayError) as ctx:
                run_combat_continue((self.session, self.stats, {}, self.stats, {}))
        self.assertEqual(str(ctx.exception), "No combat encounter configured for this scene. Check quest content.")
        self.assertEqual(ctx.exception.status, 400)
        flush_mock.assert_not_called()

    def test_run_combat_continue_clears_choices_when_combat_remains_active(self):
        from game.services.gameplay.combat import run_combat_continue

        create_active_combat_state(self.session, self.enemy, pending_victory=True)
        expected_context = {"combat_state": self.session.combat_state, "choices": [object()], "scene": self.victory_scene}

        with patch("game.services.gameplay.combat.resolve_combat_end", return_value=(["victory"], expected_context)):
            with patch("game.services.gameplay.combat.flush_event_log") as flush_mock:
                context = run_combat_continue((self.session, self.stats, {}, self.stats, {}))
        flush_mock.assert_called_once_with(self.session, ["victory"])
        self.assertEqual(context["choices"], [])
