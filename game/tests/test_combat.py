from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from game.models import CompletedQuest, Enemy, GameSession, Scene

from game.tests.factories import ChoiceFactory, EnemyFactory, SceneFactory, bootstrap_game_session


class CombatTest(TestCase):
    def setUp(self):
        from game.models import CombatEncounter, CombatState

        self.client = Client()
        self.session = bootstrap_game_session(self.client)
        self.combat_scene = SceneFactory(key="debt__corner_fight", title="Corner Fight", body="", scene_type="combat")
        victory_scene = SceneFactory(key="debt__enforcer_fight", title="After Fight", body="", scene_type="normal")
        enemy = EnemyFactory(
            key="debt__corner_thug",
            name="Corner Thug",
            description="",
            max_hp=20,
            attack_modifier=0,
            defense=8,
            damage_min=2,
            damage_max=4,
        )
        CombatEncounter.objects.create(scene=self.combat_scene, enemy=enemy, victory_scene=victory_scene)
        self.session.current_scene = self.combat_scene
        self.session.save()
        encounter = CombatEncounter.objects.get(scene=self.combat_scene)
        self.combat_state = CombatState.objects.create(
            session=self.session, enemy=encounter.enemy, enemy_hp=encounter.enemy.max_hp, is_active=True
        )

    def test_player_attack_non_killing_blow_returns_combat_panel(self):
        self.combat_state.enemy_hp = 100
        self.combat_state.save()

        with patch("game.services.combat.roll_d20", return_value=20):
            response = self.client.post(reverse("combat_attack"), HTTP_HX_REQUEST="true")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "combat-panel")
        self.assertContains(response, self.combat_state.enemy.name.upper())
        self.combat_state.refresh_from_db()
        self.assertLess(self.combat_state.enemy_hp, 100)

    def test_combat_victory_awards_xp_and_transitions_to_victory_scene(self):
        from game.services.progression import XP_AWARDS

        self.combat_state.enemy_hp = 1
        self.combat_state.save()
        self.session.stats.strength = 20
        self.session.stats.save()
        starting_xp = self.session.stats.experience
        starting_completed_quests = CompletedQuest.objects.filter(session=self.session).count()

        with patch("game.services.combat.roll_d20", return_value=20):
            self.client.post(reverse("combat_attack"), HTTP_HX_REQUEST="true")

        self.combat_state.refresh_from_db()
        self.assertTrue(self.combat_state.pending_victory)

        response = self.client.post(reverse("combat_continue"), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.session.stats.refresh_from_db()
        victory_scene = Scene.objects.get(key="debt__enforcer_fight")
        self.assertEqual(self.session.current_scene, victory_scene)
        self.assertEqual(self.session.stats.experience, starting_xp + XP_AWARDS["combat_victory"])
        self.assertTrue(
            self.session.log.filter(text__icontains=f"You gained {XP_AWARDS['combat_victory']} XP.").exists()
        )
        self.assertEqual(
            CompletedQuest.objects.filter(session=self.session).count(),
            starting_completed_quests,
        )


class CombatServiceTest(TestCase):
    def setUp(self):
        from game.models.combat import CombatEncounter

        self.client = Client()
        self.session = bootstrap_game_session(self.client)
        self.stats = self.session.stats

        self.enemy = EnemyFactory(
            key="cs__enemy",
            name="Corner Thug",
            description="",
            max_hp=20,
            attack_modifier=0,
            defense=8,
            damage_min=2,
            damage_max=4,
        )
        self.defeat_scene = SceneFactory(
            key="cs__defeat", title="Defeat", body="", scene_type="ending", ending_type="defeat"
        )
        self.victory_scene = SceneFactory(
            key="cs__victory", title="Victory", body="", scene_type="normal"
        )
        self.combat_scene = SceneFactory(
            key="cs__combat", title="Combat", body="", scene_type="combat"
        )
        self.encounter = CombatEncounter.objects.create(
            scene=self.combat_scene,
            enemy=self.enemy,
            victory_scene=self.victory_scene,
            defeat_scene=self.defeat_scene,
        )
        self.session.current_scene = self.combat_scene
        self.session.save()

    def _make_combat_state(self, **kwargs):
        from game.models.combat import CombatState

        defaults = dict(session=self.session, enemy=self.enemy, enemy_hp=20, turn_number=1, is_active=True)
        defaults.update(kwargs)
        return CombatState.objects.create(**defaults)

    def test_enemy_attack_hit_reduces_player_hp(self):
        from game.services.combat import execute_enemy_attack

        cs = self._make_combat_state(
            pending_enemy_roll=10,
            pending_enemy_total=12,
            pending_enemy_hit=True,
            pending_enemy_damage=3,
        )
        self.stats.hp = 10
        self.stats.save()

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

        cs = self._make_combat_state(
            pending_enemy_roll=1,
            pending_enemy_total=1,
            pending_enemy_hit=False,
            pending_enemy_damage=0,
        )
        self.stats.hp = 10
        self.stats.save()

        logs, _context = execute_enemy_attack(self.session, self.stats, {}, {}, cs, self.stats)

        self.stats.refresh_from_db()
        self.assertEqual(self.stats.hp, 10)
        cs.refresh_from_db()
        self.assertEqual(cs.turn_number, 2)
        self.assertTrue(any("Missed." in line for line in logs))
        self.assertEqual(self.session.log.count(), 0)

    def test_enemy_attack_reduces_player_to_zero_transitions_to_defeat_scene(self):
        from game.services.combat import execute_enemy_attack

        cs = self._make_combat_state(
            pending_enemy_roll=15,
            pending_enemy_total=17,
            pending_enemy_hit=True,
            pending_enemy_damage=5,
        )
        self.stats.hp = 2
        self.stats.save()

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
        defeat_line_index = logs.index("You're down. You lose consciousness.")
        arrival_line_index = logs.index("You wake up in a cold alley.")
        self.assertLess(defeat_line_index, arrival_line_index)
        self.assertEqual(self.session.log.count(), 0)

    def test_run_enemy_attack_keeps_destination_scene_choices_after_defeat(self):
        from game.services.gameplay import run_enemy_attack

        ChoiceFactory(scene=self.defeat_scene, label="Regain your footing", target_scene=self.victory_scene)

        cs = self._make_combat_state(
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

    def test_resolve_combat_end_returns_logs_and_does_not_persist_events(self):
        from game.services.combat import resolve_combat_end

        cs = self._make_combat_state()
        self.encounter.victory_arrival_flavor = "The crowd clears out."
        self.encounter.save(update_fields=["victory_arrival_flavor"])
        self.stats.heat = 5
        self.stats.save(update_fields=["heat"])
        self.victory_scene.cash_change = 7
        self.victory_scene.heat_change = -2
        self.victory_scene.rep_change = 3
        self.victory_scene.save(update_fields=["cash_change", "heat_change", "rep_change"])

        logs, context = resolve_combat_end(
            self.session,
            self.stats,
            {},
            {},
            self.victory_scene,
            cs,
            xp_award=1,
            ending_type="victory",
        )

        self.assertIn("The crowd clears out. You gained 1 XP, +$7 cash, -2 heat, +3 rep.", logs)
        self.assertNotIn("+1 XP.", logs)
        self.assertIn("scene", context)
        self.assertEqual(self.session.log.count(), 0)

    def test_resolve_combat_end_without_victory_flavor_still_logs_combined_rewards(self):
        from game.services.combat import resolve_combat_end

        cs = self._make_combat_state()
        self.victory_scene.cash_change = 4
        self.victory_scene.heat_change = 1
        self.victory_scene.rep_change = 2
        self.victory_scene.save(update_fields=["cash_change", "heat_change", "rep_change"])

        logs, _context = resolve_combat_end(
            self.session,
            self.stats,
            {},
            {},
            self.victory_scene,
            cs,
            xp_award=50,
            ending_type="victory",
        )

        self.assertIn("You gained 50 XP, +$4 cash, +1 heat, +2 rep.", logs)

    def test_initialize_combat_state_deactivates_when_entering_non_combat_scene(self):
        from game.services.combat import initialize_combat_state

        cs = self._make_combat_state()
        normal_scene = SceneFactory(key="cs__normal", title="Normal", body="", scene_type="normal")

        result = initialize_combat_state(self.session, normal_scene)

        self.assertEqual(result, (None, None))
        cs.refresh_from_db()
        self.assertFalse(cs.is_active)

    def test_initialize_combat_state_recreates_deleted_inactive_state(self):
        from game.models.combat import CombatState
        from game.services.combat import initialize_combat_state

        old_cs = self._make_combat_state(is_active=False)
        old_pk = old_cs.pk

        new_cs, init_log = initialize_combat_state(self.session, self.combat_scene)

        self.assertFalse(CombatState.objects.filter(pk=old_pk).exists())
        self.assertIsNotNone(new_cs)
        self.assertTrue(new_cs.is_active)
        self.assertIn(self.enemy.name, init_log)

    def test_consume_enemy_attack_raises_when_pending_attack_is_incomplete(self):
        from game.services.combat import consume_enemy_attack

        cs = self._make_combat_state(
            pending_enemy_roll=10,
            pending_enemy_total=12,
            pending_enemy_hit=None,
            pending_enemy_damage=3,
        )

        with self.assertRaises(ValueError) as ctx:
            consume_enemy_attack(cs)

        self.assertEqual(str(ctx.exception), "No pending enemy attack to consume.")




class CombatGameplayServiceGuardsTest(TestCase):
    def setUp(self):
        from game.models.combat import CombatEncounter

        self.client = Client()
        self.session = bootstrap_game_session(self.client)
        self.stats = self.session.stats

        self.enemy = EnemyFactory(
            key="cguard__enemy",
            name="Guard Thug",
            description="",
            max_hp=20,
            attack_modifier=0,
            defense=8,
            damage_min=2,
            damage_max=4,
        )
        self.victory_scene = SceneFactory(key="cguard__victory", title="Victory", body="", scene_type="normal")
        self.combat_scene = SceneFactory(key="cguard__combat", title="Combat", body="", scene_type="combat")
        self.encounter = CombatEncounter.objects.create(
            scene=self.combat_scene,
            enemy=self.enemy,
            victory_scene=self.victory_scene,
        )
        self.session.current_scene = self.combat_scene
        self.session.save(update_fields=["current_scene"])

    def _make_combat_state(self, **kwargs):
        from game.models.combat import CombatState

        defaults = dict(session=self.session, enemy=self.enemy, enemy_hp=20, turn_number=1, is_active=True)
        defaults.update(kwargs)
        return CombatState.objects.create(**defaults)

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

        self._make_combat_state(is_active=False)

        with self.assertRaises(GameplayError) as ctx:
            _require_active_combat(self.session)

        self.assertEqual(str(ctx.exception), "Combat is not active.")
        self.assertEqual(ctx.exception.status, 400)

    def test_run_enemy_attack_raises_when_no_pending_enemy_attack(self):
        from game.services.gameplay.combat import run_enemy_attack
        from game.services.types import GameplayError

        self._make_combat_state()

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

        self._make_combat_state(
            pending_enemy_roll=10,
            pending_enemy_total=12,
            pending_enemy_hit=True,
            pending_enemy_damage=3,
        )
        CombatEncounter.objects.filter(pk=self.encounter.pk).delete()

        with patch("game.services.gameplay.combat.flush_event_log") as flush_mock:
            with self.assertRaises(GameplayError) as ctx:
                run_enemy_attack((self.session, self.stats, {}, self.stats, {}))

        self.assertEqual(
            str(ctx.exception),
            "No combat encounter configured for this scene. Check quest content.",
        )
        self.assertEqual(ctx.exception.status, 400)
        flush_mock.assert_not_called()

    def test_run_enemy_attack_clears_choices_when_combat_remains_active(self):
        from game.services.gameplay.combat import run_enemy_attack

        self._make_combat_state(
            pending_enemy_roll=10,
            pending_enemy_total=12,
            pending_enemy_hit=True,
            pending_enemy_damage=3,
        )
        expected_context = {
            "combat_state": self.session.combat_state,
            "choices": [object()],
            "scene": self.combat_scene,
        }

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

        self._make_combat_state(pending_victory=False)

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

        self._make_combat_state(pending_victory=True)
        CombatEncounter.objects.filter(pk=self.encounter.pk).delete()

        with patch("game.services.gameplay.combat.flush_event_log") as flush_mock:
            with self.assertRaises(GameplayError) as ctx:
                run_combat_continue((self.session, self.stats, {}, self.stats, {}))

        self.assertEqual(
            str(ctx.exception),
            "No combat encounter configured for this scene. Check quest content.",
        )
        self.assertEqual(ctx.exception.status, 400)
        flush_mock.assert_not_called()

    def test_run_combat_continue_clears_choices_when_combat_remains_active(self):
        from game.services.gameplay.combat import run_combat_continue

        self._make_combat_state(pending_victory=True)
        expected_context = {
            "combat_state": self.session.combat_state,
            "choices": [object()],
            "scene": self.victory_scene,
        }

        with patch("game.services.gameplay.combat.resolve_combat_end", return_value=(["victory"], expected_context)):
            with patch("game.services.gameplay.combat.flush_event_log") as flush_mock:
                context = run_combat_continue((self.session, self.stats, {}, self.stats, {}))

        flush_mock.assert_called_once_with(self.session, ["victory"])
        self.assertEqual(context["choices"], [])


class CombatViewTest(TestCase):
    def setUp(self):
        from game.models.combat import CombatEncounter, CombatState

        self.client = Client()
        self.session = bootstrap_game_session(self.client)
        self.stats = self.session.stats

        self.enemy = EnemyFactory(
            key="cview__enemy",
            name="View Thug",
            description="",
            max_hp=20,
            attack_modifier=0,
            defense=8,
            damage_min=2,
            damage_max=2,
        )
        self.victory_scene = SceneFactory(
            key="cview__victory", title="Victory", body="", scene_type="normal"
        )
        self.combat_scene = SceneFactory(
            key="cview__combat", title="Combat", body="", scene_type="combat"
        )
        CombatEncounter.objects.create(
            scene=self.combat_scene, enemy=self.enemy, victory_scene=self.victory_scene
        )
        self.session.current_scene = self.combat_scene
        self.session.save()

        CombatState.objects.create(
            session=self.session,
            enemy=self.enemy,
            enemy_hp=self.enemy.max_hp,
            turn_number=1,
            is_active=True,
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

    def test_combat_attack_rejects_get_with_405(self):
        response = self.client.get(reverse("combat_attack"))
        self.assertEqual(response.status_code, 405)

    def test_combat_resolve_enemy_rejects_get_with_405(self):
        response = self.client.get(reverse("combat_resolve_enemy"))
        self.assertEqual(response.status_code, 405)

    def test_combat_continue_rejects_get_with_405(self):
        response = self.client.get(reverse("combat_continue"))
        self.assertEqual(response.status_code, 405)

    def test_combat_attack_miss_renders_your_turn_badge_from_latest_event(self):
        from game.models.combat import CombatState

        cs = CombatState.objects.get(session=self.session)
        cs.pending_enemy_roll = None
        cs.pending_enemy_total = None
        cs.pending_enemy_hit = None
        cs.pending_enemy_damage = None
        cs.enemy_hp = self.enemy.max_hp
        cs.save(
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
        from game.models.combat import CombatState

        cs = CombatState.objects.get(session=self.session)
        cs.pending_enemy_roll = None
        cs.pending_enemy_total = None
        cs.pending_enemy_hit = None
        cs.pending_enemy_damage = None
        cs.save(
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

    def test_combat_continue_returns_400_when_victory_scene_missing(self):
        from game.models.combat import CombatEncounter, CombatState

        encounter = CombatEncounter.objects.get(scene=self.combat_scene)
        encounter.victory_scene = None
        encounter.save(update_fields=["victory_scene"])

        cs = CombatState.objects.get(session=self.session)
        cs.pending_victory = True
        cs.save(update_fields=["pending_victory"])

        response = self.client.post(reverse("combat_continue"), HTTP_HX_REQUEST="true")

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "missing victory_scene", status_code=400)
        self.session.refresh_from_db()
        self.assertEqual(self.session.current_scene, self.combat_scene)
        cs.refresh_from_db()
        self.assertTrue(cs.is_active)

    def test_combat_continue_shows_victory_scene_choices_without_refresh(self):
        from game.models.combat import CombatState

        ChoiceFactory(scene=self.victory_scene, label="Take the payout", target_scene=self.victory_scene)

        cs = CombatState.objects.get(session=self.session)
        cs.pending_victory = True
        cs.save(update_fields=["pending_victory"])

        response = self.client.post(reverse("combat_continue"), HTTP_HX_REQUEST="true")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Take the payout")
        self.assertNotContains(response, "No choices available.")

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
        cs.save(update_fields=[
            "pending_enemy_roll",
            "pending_enemy_total",
            "pending_enemy_hit",
            "pending_enemy_damage",
        ])
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
        cs.save(update_fields=[
            "pending_enemy_roll",
            "pending_enemy_total",
            "pending_enemy_hit",
            "pending_enemy_damage",
        ])
        self.stats.hp = 1
        self.stats.save(update_fields=["hp"])

        encounter = self.combat_scene.combat_encounter
        encounter.defeat_scene = self.victory_scene
        encounter.save(update_fields=["defeat_scene"])

        response = self.client.post(reverse("combat_resolve_enemy"), HTTP_HX_REQUEST="true")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Press the edge")
        self.assertNotContains(response, "No choices available.")


