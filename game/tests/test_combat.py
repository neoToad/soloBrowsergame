from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from game.models import Enemy, GameSession, Scene

from game.tests.factories import ChoiceFactory, EnemyFactory, SceneFactory, bootstrap_game_session


class CombatTest(TestCase):
    fixtures = [
        "game/fixtures/property.json",
        "game/fixtures/scene.json",
        "game/fixtures/enemy.json",
        "game/fixtures/combatencounter.json",
    ]

    def setUp(self):
        from game.models import CombatEncounter, CombatState

        self.client = Client()
        self.client.get("/game/")
        session_id = self.client.session.session_key
        self.session = GameSession.objects.get(session_key=session_id)
        self.combat_scene = Scene.objects.get(key="debt__corner_fight")
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

    def test_combat_victory_and_quest_completion(self):
        self.combat_state.enemy_hp = 1
        self.combat_state.save()
        self.session.stats.strength = 20
        self.session.stats.save()

        with patch("game.services.combat.roll_d20", return_value=20):
            self.client.post(reverse("combat_attack"), HTTP_HX_REQUEST="true")

        self.combat_state.refresh_from_db()
        self.assertTrue(self.combat_state.pending_victory)

        response = self.client.post(reverse("combat_continue"), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        victory_scene = Scene.objects.get(key="debt__enforcer_fight")
        self.assertEqual(self.session.current_scene, victory_scene)


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

        self.assertIn("The crowd clears out.", logs)
        self.assertIn("+1 XP.", logs)
        self.assertLess(logs.index("The crowd clears out."), logs.index("+1 XP."))
        self.assertIn("scene", context)
        self.assertEqual(self.session.log.count(), 0)

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


