import json
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from game.constants import SESSION_KEY
from game.models import (
    Choice,
    CompletedQuest,
    GameSession,
    PlayerDiscoveredTerritory,
    PlayerStats,
    Quest,
    Requirement,
    RequirementGroup,
    Scene,
    Territory,
)

from game.tests.factories import HubSceneFactory


class GameNavigationTest(TestCase):
    def setUp(self):
        self.client = Client()
        hub = HubSceneFactory()

        notice_board = Scene.objects.create(
            key="hub__notice_board", title="The Board", body="", scene_type="hub"
        )
        Choice.objects.create(
            scene=notice_board, label="Head back outside", target_scene=hub, order=1
        )

        self.warehouse_scene = Scene.objects.create(
            key="warehouse__loading_dock",
            title="Loading Dock",
            body="",
            scene_type="normal",
        )
        Choice.objects.create(
            scene=self.warehouse_scene,
            label="Slip around back.",
            target_scene=hub,
            order=1,
        )

        decoy = Scene.objects.create(
            key="test__nav_decoy", title="Decoy", body="", scene_type="normal"
        )
        Choice.objects.create(scene=decoy, label="Decoy Choice", target_scene=hub, order=1)

    def test_root_redirects_to_game(self):
        response = self.client.get("/")
        self.assertRedirects(response, "/game/", target_status_code=302)

    def test_game_hub_creates_session_and_redirects(self):
        Territory.objects.create(key="the_flats", name="The Flats")
        response = self.client.get("/game/")
        self.assertRedirects(
            response, reverse("scene_detail", kwargs={"scene_key": "hub__apartment"})
        )

        self.assertEqual(GameSession.objects.count(), 1)
        self.assertEqual(PlayerStats.objects.count(), 1)
        self.assertIn(SESSION_KEY, self.client.session)
        session = GameSession.objects.get(pk=self.client.session[SESSION_KEY])
        self.assertTrue(
            PlayerDiscoveredTerritory.objects.filter(
                session=session, territory__key="the_flats"
            ).exists()
        )

    def test_scene_navigation(self):
        self.client.get("/game/")
        session = GameSession.objects.first()
        initial_scene = session.current_scene

        response = self.client.get(
            reverse("scene_detail", kwargs={"scene_key": "hub__notice_board"})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The Board")
        self.assertContains(response, "Head back outside")
        session.refresh_from_db()
        self.assertEqual(session.current_scene, initial_scene)

    def test_stat_gated_choice(self):
        self.client.get("/game/")
        game_session = GameSession.objects.first()
        stats = game_session.stats
        scene = Scene.objects.get(key="warehouse__loading_dock")

        choice_sneak = Choice.objects.get(
            scene=scene,
            label__icontains="Slip around back",
        )

        req = Requirement.objects.create(
            condition_type="stat_gte", stat_name="agility", stat_value=7
        )
        group = RequirementGroup.objects.create(label="Agility 7 gate", logic="all")
        group.requirements.add(req)
        choice_sneak.requirements.add(group)

        response = self.client.get(
            reverse("scene_detail", kwargs={"scene_key": "warehouse__loading_dock"})
        )
        self.assertNotContains(response, "Slip around back.")

        stats.agility = 7
        stats.save()

        response = self.client.get(
            reverse("scene_detail", kwargs={"scene_key": "warehouse__loading_dock"})
        )
        self.assertContains(response, "Slip around back.")

    def test_persistent_session(self):
        self.client.get("/game/")
        session_id_1 = self.client.session[SESSION_KEY]

        self.client.get("/game/")
        session_id_2 = self.client.session[SESSION_KEY]

        self.assertEqual(session_id_1, session_id_2)
        self.assertEqual(GameSession.objects.count(), 1)

    def test_choice_resolve_advances_scene_and_returns_htmx_fragment(self):
        self.client.get("/game/")
        session = GameSession.objects.first()
        initial_scene = session.current_scene

        dest = Scene.objects.create(
            key="test__nav_dest", title="Destination", body="", scene_type="normal"
        )
        choice = Choice.objects.create(
            scene=initial_scene, label="Go there", target_scene=dest, order=1
        )

        response = self.client.post(
            reverse("choice_resolve", kwargs={"choice_id": choice.pk}),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="scene-panel"', response.content.decode())
        session.refresh_from_db()
        self.assertEqual(session.current_scene, dest)

    def test_choice_flag_effects_update_gated_choice_visibility(self):
        self.client.get("/game/")
        session = GameSession.objects.first()
        current_scene = session.current_scene

        next_scene = Scene.objects.create(
            key="phase6__flag_next", title="Flag Next", body="next", scene_type="normal"
        )
        final_scene = Scene.objects.create(
            key="phase6__flag_final",
            title="Flag Final",
            body="final",
            scene_type="normal",
        )
        set_flag_choice = Choice.objects.create(
            scene=current_scene,
            label="Set Secret Flag",
            target_scene=next_scene,
            set_flag_name="phase6_secret",
            order=9000,
        )
        clear_flag_choice = Choice.objects.create(
            scene=current_scene,
            label="Clear Secret Flag",
            target_scene=next_scene,
            clear_flag_name="phase6_secret",
            order=9001,
        )
        gated_choice = Choice.objects.create(
            scene=current_scene, label="Secret Route", target_scene=final_scene, order=9002
        )

        gate_req = Requirement.objects.create(
            condition_type="has_flag", flag_name="phase6_secret"
        )
        gate_group = RequirementGroup.objects.create(
            label="Requires phase6_secret", logic="all"
        )
        gate_group.requirements.add(gate_req)
        gated_choice.requirements.add(gate_group)

        response = self.client.get(reverse("scene_detail", kwargs={"scene_key": current_scene.key}))
        self.assertNotContains(response, gated_choice.label)

        self.client.post(
            reverse("choice_resolve", kwargs={"choice_id": set_flag_choice.pk}),
            HTTP_HX_REQUEST="true",
        )
        session.refresh_from_db()
        self.assertTrue(session.flags.get("phase6_secret"))

        session.current_scene = current_scene
        session.save(update_fields=["current_scene"])
        response = self.client.get(reverse("scene_detail", kwargs={"scene_key": current_scene.key}))
        self.assertContains(response, gated_choice.label)

        self.client.post(
            reverse("choice_resolve", kwargs={"choice_id": clear_flag_choice.pk}),
            HTTP_HX_REQUEST="true",
        )
        session.refresh_from_db()
        self.assertNotIn("phase6_secret", session.flags)

        session.current_scene = current_scene
        session.save(update_fields=["current_scene"])
        response = self.client.get(reverse("scene_detail", kwargs={"scene_key": current_scene.key}))
        self.assertNotContains(response, gated_choice.label)

    def test_choice_resolve_rejects_choice_from_different_scene(self):
        self.client.get("/game/")
        session = GameSession.objects.first()
        initial_scene = session.current_scene

        off_scene_choice = Choice.objects.exclude(scene=initial_scene).first()
        self.assertIsNotNone(off_scene_choice, "Expected at least one choice from another scene")

        response = self.client.post(
            reverse("choice_resolve", kwargs={"choice_id": off_scene_choice.pk}),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn('id="scene-panel"', response.content.decode())
        triggers = json.loads(response.headers.get("HX-Trigger", "{}"))
        self.assertIn("app.error", triggers)
        session.refresh_from_db()
        self.assertEqual(session.current_scene, initial_scene)

    def test_roll_choice_missing_success_scene_returns_400_and_does_not_move_session(self):
        self.client.get("/game/")
        session = GameSession.objects.first()
        initial_scene = session.current_scene
        session.current_scene.requires_roll = True
        session.current_scene.roll_stat = "agility"
        session.current_scene.roll_difficulty = 10
        session.current_scene.save(update_fields=["requires_roll", "roll_stat", "roll_difficulty"])

        choice = Choice.objects.create(
            scene=initial_scene,
            label="Risk the jump",
            success_scene=None,
            failure_scene=initial_scene,
            order=5000,
        )

        with patch("game.services.scene.roll_d20", return_value=20):
            response = self.client.post(
                reverse("choice_resolve", kwargs={"choice_id": choice.pk}),
                HTTP_HX_REQUEST="true",
            )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "missing success_scene", status_code=400)
        session.refresh_from_db()
        self.assertEqual(session.current_scene, initial_scene)

    def test_roll_choice_missing_failure_scene_returns_400_and_does_not_move_session(self):
        self.client.get("/game/")
        session = GameSession.objects.first()
        initial_scene = session.current_scene
        session.current_scene.requires_roll = True
        session.current_scene.roll_stat = "agility"
        session.current_scene.roll_difficulty = 30
        session.current_scene.save(update_fields=["requires_roll", "roll_stat", "roll_difficulty"])

        success_scene = Scene.objects.create(
            key="test__roll_success_dest", title="Success", body="", scene_type="normal"
        )
        choice = Choice.objects.create(
            scene=initial_scene,
            label="Try anyway",
            success_scene=success_scene,
            failure_scene=None,
            order=5001,
        )

        with patch("game.services.scene.roll_d20", return_value=1):
            response = self.client.post(
                reverse("choice_resolve", kwargs={"choice_id": choice.pk}),
                HTTP_HX_REQUEST="true",
            )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "missing failure_scene", status_code=400)
        session.refresh_from_db()
        self.assertEqual(session.current_scene, initial_scene)


class NoticeBoardTest(TestCase):
    fixtures = [
        "game/fixtures/arc.json",
        "game/fixtures/property.json",
        "game/fixtures/requirement.json",
        "game/fixtures/requirementgroup.json",
        "game/fixtures/scene.json",
        "game/fixtures/choice.json",
        "game/fixtures/quest.json",
    ]

    def setUp(self):
        self.client = Client()
        self.client.get("/game/")
        self.session = GameSession.objects.first()
        self.warehouse_job = Quest.objects.get(key="the_warehouse_job")
        self.warehouse_entrance = Scene.objects.get(key="warehouse__loading_dock")
        self.notice_board_scene = Scene.objects.get(key="hub__notice_board")
        self.warehouse_job.hub_scenes.add(self.notice_board_scene)

    def test_notice_board_initial_state(self):
        response = self.client.get(reverse("scene_detail", kwargs={"scene_key": "hub__notice_board"}))
        self.assertContains(response, "[ AVAILABLE JOBS ]")
        self.assertContains(response, "The Warehouse Job")
        self.assertIn("quest-entry--available", response.content.decode())

    def test_quest_prerequisite_gating(self):
        second_quest = Quest.objects.create(
            key="second_quest",
            title="The Second Quest",
            description="Locked until warehouse is done.",
            entrance_scene=self.warehouse_entrance,
        )
        req = Requirement.objects.create(
            condition_type="quest_completed", required_quest=self.warehouse_job
        )
        group = RequirementGroup.objects.create(label="Requires Warehouse", logic="all")
        group.requirements.add(req)
        second_quest.requirements.add(group)
        second_quest.hub_scenes.add(self.notice_board_scene)

        response = self.client.get(reverse("scene_detail", kwargs={"scene_key": "hub__notice_board"}))
        self.assertContains(response, "[ LOCKED JOBS ]")
        self.assertContains(response, second_quest.title)
        self.assertContains(response, "Requires Warehouse")

        CompletedQuest.objects.create(
            session=self.session, quest=self.warehouse_job, ending_type="victory"
        )

        response = self.client.get(reverse("scene_detail", kwargs={"scene_key": "hub__notice_board"}))
        self.assertContains(response, second_quest.title)
        self.assertNotContains(response, "Requires Warehouse")

    def test_stat_gated_quest(self):
        intellect_quest = Quest.objects.create(
            key="intellect_quest",
            title="Intellect Quest",
            description="Requires brains.",
            entrance_scene=self.warehouse_entrance,
        )
        req = Requirement.objects.create(
            condition_type="stat_gte", stat_name="intellect", stat_value=9
        )
        group = RequirementGroup.objects.create(label="Requires Intellect 9", logic="all")
        group.requirements.add(req)
        intellect_quest.requirements.add(group)
        intellect_quest.hub_scenes.add(self.notice_board_scene)

        self.session.stats.intellect = 6
        self.session.stats.save()

        response = self.client.get(reverse("scene_detail", kwargs={"scene_key": "hub__notice_board"}))
        self.assertContains(response, "Requires Intellect 9")

        self.session.stats.intellect = 9
        self.session.stats.save()

        response = self.client.get(reverse("scene_detail", kwargs={"scene_key": "hub__notice_board"}))
        self.assertNotContains(response, "Requires Intellect 9")
        self.assertContains(response, intellect_quest.title)

    def test_completed_quest_rendering(self):
        self.warehouse_job.is_repeatable = True
        self.warehouse_job.save()

        CompletedQuest.objects.create(
            session=self.session, quest=self.warehouse_job, ending_type="victory"
        )

        response = self.client.get(reverse("scene_detail", kwargs={"scene_key": "hub__notice_board"}))
        self.assertContains(response, "[ COMPLETED JOBS ]")
        self.assertContains(response, "The Warehouse Job")
        self.assertContains(response, "Victory")
        self.assertContains(response, "Play again")

    def test_start_quest_view(self):
        locked_quest = Quest.objects.create(
            key="locked_quest",
            title="Locked Quest",
            description="Requires brains.",
            entrance_scene=self.warehouse_entrance,
        )
        req = Requirement.objects.create(
            condition_type="stat_gte", stat_name="intellect", stat_value=99
        )
        group = RequirementGroup.objects.create(label="Requires Big Brains", logic="all")
        group.requirements.add(req)
        locked_quest.requirements.add(group)

        response = self.client.post(reverse("start_quest", kwargs={"quest_key": "locked_quest"}))
        self.assertEqual(response.status_code, 403)
        self.assertIn("[ REQUEST FAILED ]", response.content.decode())

        response = self.client.post(reverse("start_quest", kwargs={"quest_key": "the_warehouse_job"}))
        self.assertRedirects(
            response, reverse("scene_detail", kwargs={"scene_key": self.warehouse_entrance.key})
        )

        self.session.refresh_from_db()
        self.assertEqual(self.session.current_scene, self.warehouse_entrance)
        self.assertTrue(self.session.log.filter(text__icontains="took the job").exists())

    def test_start_quest_htmx(self):
        response = self.client.post(
            reverse("start_quest", kwargs={"quest_key": "the_warehouse_job"}),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="scene-panel"', response.content.decode())
        self.assertContains(response, self.warehouse_entrance.title)

