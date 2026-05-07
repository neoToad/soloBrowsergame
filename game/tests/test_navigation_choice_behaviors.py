from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from game.models import Choice, Scene
from game.tests.factories import HubSceneFactory
from game.tests.helpers import start_game_session


class NavigationChoiceBehaviorTest(TestCase):
    def setUp(self):
        self.client = Client()
        HubSceneFactory()
        self.session = start_game_session(self.client)

    def test_choice_flag_effects_update_gated_choice_visibility(self):
        from game.models import Requirement, RequirementGroup

        current_scene = self.session.current_scene
        next_scene = Scene.objects.create(key="phase6__flag_next", title="Flag Next", body="next", scene_type="normal")
        final_scene = Scene.objects.create(key="phase6__flag_final", title="Flag Final", body="final", scene_type="normal")
        set_flag_choice = Choice.objects.create(
            scene=current_scene, label="Set Secret Flag", target_scene=next_scene, set_flag_name="phase6_secret", order=9000
        )
        clear_flag_choice = Choice.objects.create(
            scene=current_scene, label="Clear Secret Flag", target_scene=next_scene, clear_flag_name="phase6_secret", order=9001
        )
        gated_choice = Choice.objects.create(scene=current_scene, label="Secret Route", target_scene=final_scene, order=9002)

        gate_req = Requirement.objects.create(condition_type="has_flag", flag_name="phase6_secret")
        gate_group = RequirementGroup.objects.create(label="Requires phase6_secret", logic="all")
        gate_group.requirements.add(gate_req)
        gated_choice.requirements.add(gate_group)

        response = self.client.get(reverse("scene_detail", kwargs={"scene_key": current_scene.key}))
        self.assertNotContains(response, gated_choice.label)

        self.client.post(reverse("choice_resolve", kwargs={"choice_id": set_flag_choice.pk}), HTTP_HX_REQUEST="true")
        self.session.refresh_from_db()
        self.assertTrue(self.session.flags.get("phase6_secret"))

        self.session.current_scene = current_scene
        self.session.save(update_fields=["current_scene"])
        response = self.client.get(reverse("scene_detail", kwargs={"scene_key": current_scene.key}))
        self.assertContains(response, gated_choice.label)

        self.client.post(reverse("choice_resolve", kwargs={"choice_id": clear_flag_choice.pk}), HTTP_HX_REQUEST="true")
        self.session.refresh_from_db()
        self.assertNotIn("phase6_secret", self.session.flags)

        self.session.current_scene = current_scene
        self.session.save(update_fields=["current_scene"])
        response = self.client.get(reverse("scene_detail", kwargs={"scene_key": current_scene.key}))
        self.assertNotContains(response, gated_choice.label)

    def test_roll_choice_missing_success_scene_returns_400_and_does_not_move_session(self):
        initial_scene = self.session.current_scene
        initial_scene.requires_roll = True
        initial_scene.roll_stat = "agility"
        initial_scene.roll_difficulty = 10
        initial_scene.save(update_fields=["requires_roll", "roll_stat", "roll_difficulty"])

        choice = Choice.objects.create(scene=initial_scene, label="Risk the jump", success_scene=None, failure_scene=initial_scene, order=5000)
        with patch("game.services.scene.roll_d20", return_value=20):
            response = self.client.post(reverse("choice_resolve", kwargs={"choice_id": choice.pk}), HTTP_HX_REQUEST="true")

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "missing success_scene", status_code=400)
        self.session.refresh_from_db()
        self.assertEqual(self.session.current_scene, initial_scene)

    def test_roll_choice_missing_failure_scene_returns_400_and_does_not_move_session(self):
        initial_scene = self.session.current_scene
        initial_scene.requires_roll = True
        initial_scene.roll_stat = "agility"
        initial_scene.roll_difficulty = 30
        initial_scene.save(update_fields=["requires_roll", "roll_stat", "roll_difficulty"])

        success_scene = Scene.objects.create(key="test__roll_success_dest", title="Success", body="", scene_type="normal")
        choice = Choice.objects.create(scene=initial_scene, label="Try anyway", success_scene=success_scene, failure_scene=None, order=5001)
        with patch("game.services.scene.roll_d20", return_value=1):
            response = self.client.post(reverse("choice_resolve", kwargs={"choice_id": choice.pk}), HTTP_HX_REQUEST="true")

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "missing failure_scene", status_code=400)
        self.session.refresh_from_db()
        self.assertEqual(self.session.current_scene, initial_scene)

    def test_event_log_classification_marks_only_player_attack_as_player(self):
        self.session.log.create(text="You move on him - roll 12 (+2) = 14 vs 10 - Hit! 4 damage.")
        self.session.log.create(text="You gained 50 XP, +$4 cash, +1 heat, +2 rep.")
        self.session.log.create(text="Corner Thug comes at you - roll 9 (+0) = 9 vs 11 - Missed.")

        response = self.client.get(reverse("scene_detail", kwargs={"scene_key": self.session.current_scene.key}))
        content = response.content.decode()

        self.assertIn("You move on him", content)
        self.assertIn("log-entry--player", content)
        self.assertIn("You gained 50 XP", content)
        self.assertIn("log-entry--system", content)
        self.assertIn("comes at you", content)
        self.assertIn("log-entry--enemy", content)

    def test_non_combat_roll_does_not_render_attack_or_damage_card(self):
        roll_scene = Scene.objects.create(
            key="test__roll_scene_ui",
            title="Roll Scene UI",
            body="",
            scene_type="normal",
            requires_roll=True,
            roll_stat="agility",
            roll_difficulty=10,
        )
        success_scene = Scene.objects.create(key="test__roll_success_ui", title="Roll Success UI", body="", scene_type="normal")
        failure_scene = Scene.objects.create(key="test__roll_fail_ui", title="Roll Fail UI", body="", scene_type="normal")
        choice = Choice.objects.create(scene=roll_scene, label="Take the chance", success_scene=success_scene, failure_scene=failure_scene, order=1)

        self.session.current_scene = roll_scene
        self.session.save(update_fields=["current_scene"])

        with patch("game.services.scene.roll_d20", return_value=1):
            response = self.client.post(reverse("choice_resolve", kwargs={"choice_id": choice.pk}), HTTP_HX_REQUEST="true")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "REFLEXES CHECK")
        self.assertNotContains(response, "roll-result--miss")
        self.assertNotContains(response, "roll-result--damage")
