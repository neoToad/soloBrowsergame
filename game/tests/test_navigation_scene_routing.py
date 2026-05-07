import json

from django.test import Client, TestCase
from django.urls import reverse

from game.models import Choice, GameSession, PlayerDiscoveredTerritory, PlayerStats, Scene, Territory
from game.tests.factories import ChoiceFactory, HubSceneFactory
from game.tests.helpers import start_game_session


class NavigationSceneRoutingTest(TestCase):
    def setUp(self):
        self.client = Client()
        hub = HubSceneFactory()
        notice_board = Scene.objects.create(key="hub__notice_board", title="The Board", body="", scene_type="hub")
        Choice.objects.create(scene=notice_board, label="Head back outside", target_scene=hub, order=1)
        self.warehouse_scene = Scene.objects.create(
            key="warehouse__loading_dock", title="Loading Dock", body="", scene_type="normal"
        )
        Choice.objects.create(scene=self.warehouse_scene, label="Slip around back.", target_scene=hub, order=1)
        decoy = Scene.objects.create(key="test__nav_decoy", title="Decoy", body="", scene_type="normal")
        Choice.objects.create(scene=decoy, label="Decoy Choice", target_scene=hub, order=1)

    def test_root_redirects_to_game(self):
        response = self.client.get("/")
        self.assertRedirects(response, "/game/", target_status_code=302)

    def test_game_hub_creates_session_and_redirects(self):
        Territory.objects.create(key="the_flats", name="The Flats")
        response = self.client.get("/game/")
        self.assertRedirects(response, reverse("scene_detail", kwargs={"scene_key": "hub__apartment"}))

        self.assertEqual(GameSession.objects.count(), 1)
        self.assertEqual(PlayerStats.objects.count(), 1)
        session = GameSession.objects.first()
        self.assertTrue(
            PlayerDiscoveredTerritory.objects.filter(session=session, territory__key="the_flats").exists()
        )

    def test_scene_navigation(self):
        session = start_game_session(self.client)
        initial_scene = session.current_scene
        response = self.client.get(reverse("scene_detail", kwargs={"scene_key": "hub__notice_board"}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The Board")
        self.assertContains(response, "Head back outside")
        session.refresh_from_db()
        self.assertEqual(session.current_scene, initial_scene)

    def test_stat_gated_choice(self):
        game_session = start_game_session(self.client)
        stats = game_session.stats
        scene = Scene.objects.get(key="warehouse__loading_dock")
        choice_sneak = Choice.objects.get(scene=scene, label__icontains="Slip around back")

        from game.models import Requirement, RequirementGroup

        req = Requirement.objects.create(condition_type="stat_gte", stat_name="agility", stat_value=7)
        group = RequirementGroup.objects.create(label="Agility 7 gate", logic="all")
        group.requirements.add(req)
        choice_sneak.requirements.add(group)

        response = self.client.get(reverse("scene_detail", kwargs={"scene_key": "warehouse__loading_dock"}))
        self.assertNotContains(response, "Slip around back.")

        stats.agility = 7
        stats.save(update_fields=["agility"])

        response = self.client.get(reverse("scene_detail", kwargs={"scene_key": "warehouse__loading_dock"}))
        self.assertContains(response, "Slip around back.")

    def test_persistent_session(self):
        first = start_game_session(self.client).pk
        second = start_game_session(self.client).pk
        self.assertEqual(first, second)
        self.assertEqual(GameSession.objects.count(), 1)

    def test_choice_resolve_advances_scene_and_returns_htmx_fragment(self):
        session = start_game_session(self.client)
        dest = Scene.objects.create(key="test__nav_dest", title="Destination", body="", scene_type="normal")
        choice = Choice.objects.create(scene=session.current_scene, label="Go there", target_scene=dest, order=1)

        response = self.client.post(reverse("choice_resolve", kwargs={"choice_id": choice.pk}), HTTP_HX_REQUEST="true")

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="scene-panel"', response.content.decode())
        session.refresh_from_db()
        self.assertEqual(session.current_scene, dest)

    def test_choice_resolve_rejects_get_with_405(self):
        session = start_game_session(self.client)
        dest = Scene.objects.create(key="test__nav_method_guard_dest", title="Method Guard Destination", body="", scene_type="normal")
        choice = Choice.objects.create(scene=session.current_scene, label="Guard Choice", target_scene=dest, order=9997)
        response = self.client.get(reverse("choice_resolve", kwargs={"choice_id": choice.pk}))
        self.assertEqual(response.status_code, 405)

    def test_choice_resolve_non_htmx_redirects_to_scene_detail(self):
        session = start_game_session(self.client)
        dest = Scene.objects.create(key="test__nav_non_htmx_dest", title="Destination", body="", scene_type="normal")
        choice = Choice.objects.create(scene=session.current_scene, label="Go non htmx", target_scene=dest, order=9998)
        response = self.client.post(reverse("choice_resolve", kwargs={"choice_id": choice.pk}))
        self.assertRedirects(response, reverse("scene_detail", kwargs={"scene_key": dest.key}))
        session.refresh_from_db()
        self.assertEqual(session.current_scene, dest)

    def test_choice_resolve_non_htmx_error_renders_full_page_template(self):
        session = start_game_session(self.client)
        off_scene_choice = Choice.objects.exclude(scene=session.current_scene).first()
        self.assertIsNotNone(off_scene_choice)

        response = self.client.post(reverse("choice_resolve", kwargs={"choice_id": off_scene_choice.pk}))

        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "game/error.html")
        self.assertContains(response, "[ REQUEST FAILED ]", status_code=403)
        self.assertContains(response, "Status 403", status_code=403)

    def test_choice_resolve_rejects_choice_from_different_scene(self):
        session = start_game_session(self.client)
        initial_scene = session.current_scene
        off_scene_choice = Choice.objects.exclude(scene=initial_scene).first()
        self.assertIsNotNone(off_scene_choice)

        response = self.client.post(reverse("choice_resolve", kwargs={"choice_id": off_scene_choice.pk}), HTTP_HX_REQUEST="true")

        self.assertEqual(response.status_code, 403)
        self.assertIn('id="scene-panel"', response.content.decode())
        triggers = json.loads(response.headers.get("HX-Trigger", "{}"))
        self.assertIn("app.error", triggers)
        session.refresh_from_db()
        self.assertEqual(session.current_scene, initial_scene)
