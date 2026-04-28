import json

from django.test import Client, TestCase
from django.urls import reverse

from game.models import Choice, Quest, Scene


class QuestBuilderSceneTest(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User

        self.admin = User.objects.create_superuser(
            username="testadmin", password="testpass", email="a@a.com"
        )
        self.client = Client()
        self.client.force_login(self.admin)
        self.quest = Quest.objects.create(
            key="test_quest", title="Test Quest", description="A quest for testing."
        )

    def _create_url(self):
        return reverse("admin:quest_builder_scene_create", args=[self.quest.pk])

    def _save_url(self, scene_id):
        return reverse("admin:quest_builder_scene_save", args=[self.quest.pk, scene_id])

    def _delete_url(self, scene_id):
        return reverse("admin:quest_builder_scene_delete", args=[self.quest.pk, scene_id])

    def test_scene_create_saves_to_db(self):
        self.assertEqual(self.quest.scenes.count(), 0)

        response = self.client.post(
            self._create_url(),
            {
                "title": "Rooftop",
                "key": "test_quest__rooftop",
                "scene_type": "normal",
                "description": "High up.",
                "canvas_x": "100",
                "canvas_y": "200",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
            f"Expected 200, got {response.status_code}. Body: {response.content[:400]}",
        )
        self.assertEqual(self.quest.scenes.count(), 1)
        scene = self.quest.scenes.get()
        self.assertEqual(scene.title, "Rooftop")
        self.assertEqual(scene.key, "test_quest__rooftop")
        self.assertEqual(scene.canvas_x, 100)
        self.assertEqual(scene.canvas_y, 200)

    def test_scene_create_auto_generates_key(self):
        self.client.post(
            self._create_url(),
            {"title": "Dark Alley", "key": "", "scene_type": "normal", "description": ""},
        )
        scene = self.quest.scenes.get()
        self.assertIn("test_quest", scene.key)
        self.assertIn("dark", scene.key)
    
    def test_scene_create_rejects_key_with_wrong_quest_prefix(self):
        response = self.client.post(
            self._create_url(),
            {"title": "Rooftop", "key": "wrong_quest__rooftop", "scene_type": "normal", "description": ""},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Scene key must start with", response.content.decode())

    def test_scene_create_returns_oob_html(self):
        response = self.client.post(
            self._create_url(), {"title": "Docks", "scene_type": "normal", "description": ""}
        )
        body = response.content.decode()
        self.assertIn("hx-swap-oob", body)
        self.assertIn("canvas-stage", body)
        self.assertIn("qb-toast-container", body)
        self.assertIn("Docks", body)
        triggers = json.loads(response.headers.get("HX-Trigger", "{}"))
        self.assertIn("sceneUpdated", triggers)
        self.assertIn("scene.updated", triggers)

    def test_scene_create_get_not_allowed(self):
        response = self.client.get(self._create_url())
        self.assertEqual(response.status_code, 405)

    def test_scene_create_requires_login(self):
        self.client.logout()
        response = self.client.post(self._create_url(), {"title": "X", "scene_type": "normal"})
        self.assertIn(response.status_code, [302, 403])

    def test_scene_save_updates_db(self):
        scene = Scene.objects.create(
            quest=self.quest, key="test_quest__old", title="Old Title", body="old body", scene_type="normal"
        )
        response = self.client.post(
            self._save_url(scene.pk),
            {"title": "New Title", "key": "test_quest__new", "scene_type": "hub", "description": "new body"},
        )
        self.assertEqual(
            response.status_code,
            200,
            f"Expected 200, got {response.status_code}. Body: {response.content[:400]}",
        )
        scene.refresh_from_db()
        self.assertEqual(scene.title, "New Title")
        self.assertEqual(scene.scene_type, "hub")
        self.assertEqual(scene.body, "new body")

    def test_scene_save_returns_oob_html(self):
        scene = Scene.objects.create(
            quest=self.quest, key="test_quest__s", title="Spot", body="", scene_type="normal"
        )
        response = self.client.post(
            self._save_url(scene.pk),
            {"title": "Spot", "key": "test_quest__s", "scene_type": "normal", "description": ""},
        )
        body = response.content.decode()
        self.assertIn("hx-swap-oob", body)
        self.assertIn(f"scene-card-{scene.pk}", body)
        self.assertIn("qb-toast-container", body)
        triggers = json.loads(response.headers.get("HX-Trigger", "{}"))
        self.assertIn("sceneUpdated", triggers)
        self.assertIn("scene.updated", triggers)
    
    def test_scene_save_rejects_key_with_invalid_slug_segment(self):
        scene = Scene.objects.create(
            quest=self.quest, key="test_quest__old", title="Spot", body="", scene_type="normal"
        )
        response = self.client.post(
            self._save_url(scene.pk),
            {"title": "Spot", "key": "test_quest__Bad_Slug", "scene_type": "normal", "description": ""},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Scene key must match", response.content.decode())

    def test_scene_delete_removes_from_db(self):
        scene = Scene.objects.create(
            quest=self.quest, key="test_quest__del", title="Gone", body="", scene_type="normal"
        )
        self.client.post(self._delete_url(scene.pk))
        response = self.client.post(self._delete_url(scene.pk), {"confirmed": "1"})
        self.assertEqual(response.status_code, 200, f"Expected 200, got {response.content[:400]}")
        triggers = json.loads(response.headers.get("HX-Trigger", "{}"))
        self.assertIn("sceneUpdated", triggers)
        self.assertIn("scene.updated", triggers)
        self.assertFalse(Scene.objects.filter(pk=scene.pk).exists())


class QuestBuilderValidationTest(TestCase):
    def _make_quest(self, key="qbv__quest", **kwargs):
        return Quest.objects.create(key=key, title="QB Quest", description="", **kwargs)

    def _make_scene(self, quest, key, scene_type="normal", **kwargs):
        return Scene.objects.create(quest=quest, key=key, title=key, body="", scene_type=scene_type, **kwargs)

    def _make_choice(self, scene, label="Go", **kwargs):
        return Choice.objects.create(scene=scene, label=label, order=1, **kwargs)

    def _warning_types(self, quest):
        from game.services.quest_builder import validate_quest

        return [w["type"] for w in validate_quest(quest.pk)]

    def test_orphan_scene_detected(self):
        quest = self._make_quest()
        entry = self._make_scene(quest, "qbv__entry")
        quest.entrance_scene = entry
        quest.save()
        self._make_scene(quest, "qbv__orphan")
        self.assertIn("orphan_scene", self._warning_types(quest))

    def test_no_orphan_when_pointed_to(self):
        quest = self._make_quest()
        entry = self._make_scene(quest, "qbv__e")
        dest = self._make_scene(quest, "qbv__d", scene_type="ending")
        quest.entrance_scene = entry
        quest.save()
        self._make_choice(entry, target_scene=dest)

        types = self._warning_types(quest)
        self.assertNotIn("orphan_scene", types)

    def test_missing_routing_detected(self):
        quest = self._make_quest()
        entry = self._make_scene(quest, "qbv__e2")
        quest.entrance_scene = entry
        quest.save()
        self._make_choice(entry, label="Nowhere")
        self.assertIn("missing_routing", self._warning_types(quest))

    def test_no_missing_routing_when_target_set(self):
        quest = self._make_quest()
        entry = self._make_scene(quest, "qbv__e3")
        dest = self._make_scene(quest, "qbv__d3", scene_type="ending")
        quest.entrance_scene = entry
        quest.save()
        self._make_choice(entry, target_scene=dest)
        self.assertNotIn("missing_routing", self._warning_types(quest))

    def test_missing_roll_target_detected(self):
        quest = self._make_quest()
        entry = self._make_scene(quest, "qbv__e4", requires_roll=True)
        quest.entrance_scene = entry
        quest.save()
        dest = self._make_scene(quest, "qbv__d4", scene_type="ending")
        self._make_choice(entry, success_scene=dest)
        self.assertIn("missing_roll_target", self._warning_types(quest))

    def test_no_missing_roll_target_when_both_set(self):
        quest = self._make_quest()
        entry = self._make_scene(quest, "qbv__e5", requires_roll=True)
        win = self._make_scene(quest, "qbv__w5", scene_type="ending")
        lose = self._make_scene(quest, "qbv__l5", scene_type="ending")
        quest.entrance_scene = entry
        quest.save()
        self._make_choice(entry, success_scene=win, failure_scene=lose)
        self.assertNotIn("missing_roll_target", self._warning_types(quest))

    def test_roll_direct_choice_detected(self):
        quest = self._make_quest()
        entry = self._make_scene(quest, "qbv__e6", requires_roll=True)
        win = self._make_scene(quest, "qbv__w6", scene_type="ending")
        lose = self._make_scene(quest, "qbv__l6", scene_type="ending")
        quest.entrance_scene = entry
        quest.save()
        self._make_choice(entry, success_scene=win, failure_scene=lose)
        direct = self._make_scene(quest, "qbv__direct6", scene_type="ending")
        self._make_choice(entry, label="Direct", target_scene=direct)
        self.assertIn("roll_direct_choice", self._warning_types(quest))

    def test_empty_scene_detected(self):
        quest = self._make_quest()
        entry = self._make_scene(quest, "qbv__e7")
        empty = self._make_scene(quest, "qbv__empty7")
        quest.entrance_scene = entry
        quest.save()
        self._make_choice(entry, target_scene=empty)
        self.assertIn("empty_scene", self._warning_types(quest))

    def test_ending_scene_no_empty_warning(self):
        quest = self._make_quest()
        entry = self._make_scene(quest, "qbv__e8")
        end = self._make_scene(quest, "qbv__end8", scene_type="ending")
        quest.entrance_scene = entry
        quest.save()
        self._make_choice(entry, target_scene=end)
        self.assertNotIn("empty_scene", self._warning_types(quest))

    def test_combat_missing_encounter_detected(self):
        quest = self._make_quest()
        entry = self._make_scene(quest, "qbv__e9")
        combat = self._make_scene(quest, "qbv__combat9", scene_type="combat")
        quest.entrance_scene = entry
        quest.save()
        self._make_choice(entry, target_scene=combat)
        self.assertIn("combat_missing_encounter", self._warning_types(quest))

    def test_ending_no_hub_return_detected(self):
        quest = self._make_quest()
        entry = self._make_scene(quest, "qbv__e10")
        end = self._make_scene(quest, "qbv__end10", scene_type="ending")
        quest.entrance_scene = entry
        quest.save()
        self._make_choice(entry, target_scene=end)
        self.assertIn("ending_no_hub_return", self._warning_types(quest))

    def test_ending_with_hub_return_no_warning(self):
        hub = Scene.objects.create(key="qbv__hub", title="Hub", body="", scene_type="hub")
        quest = self._make_quest(key="qbv__quest2")
        entry = self._make_scene(quest, "qbv__e11")
        end = self._make_scene(quest, "qbv__end11", scene_type="ending")
        quest.entrance_scene = entry
        quest.save()
        self._make_choice(entry, target_scene=end)
        self._make_choice(end, label="Return", target_scene=hub)
        self.assertNotIn("ending_no_hub_return", self._warning_types(quest))


class QuestBuilderChoiceCreateOwnershipTest(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User

        self.admin = User.objects.create_superuser(
            username="choiceadmin", password="testpass", email="choice@a.com"
        )
        self.client = Client()
        self.client.force_login(self.admin)

        self.quest = Quest.objects.create(
            key="qb_choice_owner", title="Choice Owner Quest", description=""
        )
        self.other_quest = Quest.objects.create(
            key="qb_choice_other", title="Other Quest", description=""
        )

        self.source_scene = Scene.objects.create(
            quest=self.quest,
            key="qb_choice_owner__source",
            title="Owner Source",
            body="",
            scene_type="normal",
        )
        self.target_scene = Scene.objects.create(
            quest=self.quest,
            key="qb_choice_owner__target",
            title="Owner Target",
            body="",
            scene_type="normal",
        )
        self.other_source_scene = Scene.objects.create(
            quest=self.other_quest,
            key="qb_choice_other__source",
            title="Other Source",
            body="",
            scene_type="normal",
        )

    def _create_url(self):
        return reverse("admin:quest_builder_choice_create", args=[self.quest.pk])

    def test_choice_create_rejects_source_scene_from_other_quest(self):
        response = self.client.post(
            self._create_url(),
            {
                "source_scene_id": str(self.other_source_scene.pk),
                "label": "Invalid cross quest choice",
                "routing_type": "direct",
                "target_scene": str(self.target_scene.pk),
            },
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Source scene does not belong to this quest.", status_code=403)
        self.assertFalse(
            Choice.objects.filter(scene=self.other_source_scene, label="Invalid cross quest choice").exists()
        )

    def test_choice_create_allows_source_scene_in_same_quest(self):
        response = self.client.post(
            self._create_url(),
            {
                "source_scene_id": str(self.source_scene.pk),
                "label": "Valid in quest choice",
                "routing_type": "direct",
                "target_scene": str(self.target_scene.pk),
            },
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        choice = Choice.objects.get(scene=self.source_scene, label="Valid in quest choice")
        self.assertEqual(choice.target_scene, self.target_scene)
