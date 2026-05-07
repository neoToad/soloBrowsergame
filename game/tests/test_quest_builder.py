import json

from django.test import Client, TestCase
from django.urls import reverse

from game.models import Choice, CombatEncounter, Contact, Enemy, Gang, Item, Quest, Scene, SceneContact, SceneItem, Territory
from game.services.quest_builder.parsing import parse_scene_contacts_rows, parse_scene_items_rows


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

    def test_scene_create_persists_territory_arrival_fields(self):
        gain_territory = Territory.objects.create(key="qb-gain", name="QB Gain")
        lose_territory = Territory.objects.create(key="qb-lose", name="QB Lose")
        discover_territory = Territory.objects.create(key="qb-discover", name="QB Discover")

        response = self.client.post(
            self._create_url(),
            {
                "title": "Territory Scene",
                "key": "test_quest__territory-scene",
                "scene_type": "normal",
                "description": "Territory effects.",
                "receive_territory_id": str(gain_territory.id),
                "lose_territory_id": str(lose_territory.id),
                "discover_territory_id": str(discover_territory.id),
            },
        )

        self.assertEqual(response.status_code, 200)
        scene = self.quest.scenes.get(key="test_quest__territory-scene")
        self.assertEqual(scene.receive_territory_id, gain_territory.id)
        self.assertEqual(scene.lose_territory_id, lose_territory.id)
        self.assertEqual(scene.discover_territory_id, discover_territory.id)

    def test_scene_save_updates_territory_arrival_fields(self):
        gain_territory = Territory.objects.create(key="qb-gain-save", name="QB Gain Save")
        lose_territory = Territory.objects.create(key="qb-lose-save", name="QB Lose Save")
        discover_territory = Territory.objects.create(key="qb-discover-save", name="QB Discover Save")
        scene = Scene.objects.create(
            quest=self.quest, key="test_quest__territory-edit", title="Territory Edit", body="", scene_type="normal"
        )

        response = self.client.post(
            self._save_url(scene.pk),
            {
                "title": "Territory Edit",
                "key": "test_quest__territory-edit",
                "scene_type": "normal",
                "description": "",
                "receive_territory_id": str(gain_territory.id),
                "lose_territory_id": str(lose_territory.id),
                "discover_territory_id": str(discover_territory.id),
            },
        )

        self.assertEqual(response.status_code, 200)
        scene.refresh_from_db()
        self.assertEqual(scene.receive_territory_id, gain_territory.id)
        self.assertEqual(scene.lose_territory_id, lose_territory.id)
        self.assertEqual(scene.discover_territory_id, discover_territory.id)

    def test_scene_gang_standings_save_persists_rows(self):
        scene = Scene.objects.create(
            quest=self.quest, key="test_quest__standing", title="Standing", body="", scene_type="normal"
        )
        gang_a = Gang.objects.create(key="qb-gang-a", name="QB Gang A")
        gang_b = Gang.objects.create(key="qb-gang-b", name="QB Gang B")
        url = reverse("admin:quest_builder_scene_gang_standings_save", args=[self.quest.pk, scene.pk])

        response = self.client.post(
            url,
            {
                "gang_id_0": str(gang_a.id),
                "standing_change_0": "3",
                "gang_id_1": str(gang_b.id),
                "standing_change_1": "-2",
            },
        )

        self.assertEqual(response.status_code, 200)
        scene.refresh_from_db()
        rows = list(scene.scene_gang_standings.order_by("gang__key"))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].standing_change, 3)
        self.assertEqual(rows[1].standing_change, -2)

    def test_scene_items_save_invalid_quantity_returns_400_and_error_trigger(self):
        scene = Scene.objects.create(
            quest=self.quest, key="test_quest__items", title="Items", body="", scene_type="normal"
        )
        item = Item.objects.create(key="qb-item", name="QB Item", description="")
        url = reverse("admin:quest_builder_scene_items_save", args=[self.quest.pk, scene.pk])

        response = self.client.post(
            url,
            {"item_id_0": str(item.id), "quantity_0": "nope"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "quantity_0 must be a valid integer", status_code=400)
        triggers = json.loads(response.headers.get("HX-Trigger", "{}"))
        self.assertEqual(
            triggers.get("quest_builder.error"),
            {"message": "quantity_0 must be a valid integer", "status": 400},
        )
        self.assertEqual(SceneItem.objects.filter(scene=scene).count(), 0)

    def test_scene_contacts_save_invalid_contact_id_returns_400_and_error_trigger(self):
        scene = Scene.objects.create(
            quest=self.quest, key="test_quest__contacts", title="Contacts", body="", scene_type="normal"
        )
        url = reverse("admin:quest_builder_scene_contacts_save", args=[self.quest.pk, scene.pk])

        response = self.client.post(
            url,
            {"contact_id_0": "bad", "action_0": "gain"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "contact_id_0 must be a valid integer", status_code=400)
        triggers = json.loads(response.headers.get("HX-Trigger", "{}"))
        self.assertEqual(
            triggers.get("quest_builder.error"),
            {"message": "contact_id_0 must be a valid integer", "status": 400},
        )
        self.assertEqual(SceneContact.objects.filter(scene=scene).count(), 0)

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

    def test_scene_move_invalid_coordinates_returns_same_htmx_error_trigger(self):
        scene = Scene.objects.create(
            quest=self.quest, key="test_quest__move", title="Move", body="", scene_type="normal"
        )
        url = reverse("admin:quest_builder_scene_move", args=[self.quest.pk, scene.pk])

        response = self.client.post(url, {"x": "abc", "y": "200"}, HTTP_HX_REQUEST="true")

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "x and y must be integers", status_code=400)
        triggers = json.loads(response.headers.get("HX-Trigger", "{}"))
        self.assertEqual(
            triggers.get("quest_builder.error"),
            {"message": "x and y must be integers", "status": 400},
        )

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


class QuestBuilderParsingTest(TestCase):
    def test_parse_scene_items_rows_handles_sparse_indices(self):
        parsed = parse_scene_items_rows({"item_id_1": "7", "quantity_1": "3"})
        self.assertEqual(parsed, [{"item_id": 7, "quantity": 3}])

    def test_parse_scene_contacts_rows_defaults_action_and_bool(self):
        parsed = parse_scene_contacts_rows({"contact_id_2": "5", "action_2": "invalid", "award_once_2": "yes"})
        self.assertEqual(parsed, [{"contact_id": 5, "action": "gain", "award_once": True}])


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
        triggers = json.loads(response.headers.get("HX-Trigger", "{}"))
        self.assertEqual(
            triggers.get("quest_builder.error"),
            {"message": "Source scene does not belong to this quest.", "status": 403},
        )

    def test_choice_create_missing_source_non_htmx_returns_inline_error_without_trigger(self):
        response = self.client.post(
            self._create_url(),
            {
                "label": "Missing source",
                "routing_type": "direct",
                "target_scene": str(self.target_scene.pk),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "source_scene_id required", status_code=400)
        self.assertFalse(response.has_header("HX-Trigger"))

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


class QuestDeleteCascadeTest(TestCase):
    def test_deleting_quest_deletes_its_scenes_and_scene_children(self):
        quest = Quest.objects.create(key="cascade_q", title="Cascade Quest", description="")
        scene = Scene.objects.create(
            quest=quest,
            key="cascade_q__scene",
            title="Scene",
            body="",
            scene_type="combat",
        )
        next_scene = Scene.objects.create(
            quest=quest,
            key="cascade_q__next",
            title="Next",
            body="",
            scene_type="normal",
        )
        item = Item.objects.create(key="cascade_item", name="Cascade Item", description="")
        contact = Contact.objects.create(key="cascade_contact", name="Cascade Contact", description="")
        enemy = Enemy.objects.create(
            key="cascade_enemy",
            name="Cascade Enemy",
            max_hp=10,
            defense=0,
            attack_modifier=0,
            damage_min=1,
            damage_max=2,
        )

        choice = Choice.objects.create(scene=scene, label="Go", target_scene=next_scene)
        scene_item = SceneItem.objects.create(scene=scene, item=item, quantity=1, award_once=True)
        scene_contact = SceneContact.objects.create(scene=scene, contact=contact, action="gain", award_once=True)
        encounter = CombatEncounter.objects.create(scene=scene, enemy=enemy)

        quest.delete()

        self.assertFalse(Scene.objects.filter(pk=scene.pk).exists())
        self.assertFalse(Scene.objects.filter(pk=next_scene.pk).exists())
        self.assertFalse(Choice.objects.filter(pk=choice.pk).exists())
        self.assertFalse(SceneItem.objects.filter(pk=scene_item.pk).exists())
        self.assertFalse(SceneContact.objects.filter(pk=scene_contact.pk).exists())
        self.assertFalse(CombatEncounter.objects.filter(pk=encounter.pk).exists())

    def test_deleting_quest_nulls_cross_quest_choice_target(self):
        doomed_quest = Quest.objects.create(key="doomed_q", title="Doomed Quest", description="")
        survivor_quest = Quest.objects.create(key="survivor_q", title="Survivor Quest", description="")

        doomed_scene = Scene.objects.create(
            quest=doomed_quest,
            key="doomed_q__end",
            title="Doomed End",
            body="",
            scene_type="ending",
        )
        survivor_scene = Scene.objects.create(
            quest=survivor_quest,
            key="survivor_q__start",
            title="Survivor Start",
            body="",
            scene_type="normal",
        )
        bridge_choice = Choice.objects.create(scene=survivor_scene, label="Bridge", target_scene=doomed_scene)

        doomed_quest.delete()
        bridge_choice.refresh_from_db()

        self.assertIsNone(bridge_choice.target_scene)
