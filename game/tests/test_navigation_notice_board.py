from django.test import Client, TestCase, override_settings
from django.urls import reverse

from game.models import CompletedQuest, Quest, Requirement, RequirementGroup
from game.tests.factories import ChoiceFactory, HubSceneFactory, QuestFactory, SceneFactory
from game.tests.helpers import start_game_session


class NoticeBoardTest(TestCase):
    def setUp(self):
        self.client = Client()
        HubSceneFactory()
        self.notice_board_scene = SceneFactory(key="hub__notice_board", title="The Board", body="", scene_type="hub")
        self.warehouse_entrance = SceneFactory(
            key="warehouse__loading_dock", title="Loading Dock", body="", scene_type="normal"
        )
        ChoiceFactory(
            scene=self.warehouse_entrance, label="Slip around back.", target_scene=self.notice_board_scene, order=1
        )
        self.warehouse_job = QuestFactory(
            key="the_warehouse_job",
            title="The Warehouse Job",
            description="A warehouse run.",
            entrance_scene=self.warehouse_entrance,
        )
        self.warehouse_job.hub_scenes.add(self.notice_board_scene)
        self.session = start_game_session(self.client)

    def test_notice_board_initial_state(self):
        response = self.client.get(reverse("scene_detail", kwargs={"scene_key": "hub__notice_board"}))
        self.assertContains(response, "[ AVAILABLE EVENTS ]")
        self.assertContains(response, "The Warehouse Job")
        self.assertIn("quest-entry--available", response.content.decode())

    @override_settings(SHOW_LOCKED_COMPLETED_QUESTS=True)
    def test_quest_prerequisite_gating(self):
        second_quest = Quest.objects.create(
            key="second_quest", title="The Second Quest", description="Locked until warehouse is done.", entrance_scene=self.warehouse_entrance
        )
        req = Requirement.objects.create(condition_type="quest_completed", required_quest=self.warehouse_job)
        group = RequirementGroup.objects.create(label="Requires Warehouse", logic="all")
        group.requirements.add(req)
        second_quest.requirements.add(group)
        second_quest.hub_scenes.add(self.notice_board_scene)

        response = self.client.get(reverse("scene_detail", kwargs={"scene_key": "hub__notice_board"}))
        self.assertContains(response, "[ LOCKED EVENTS ]")
        self.assertContains(response, second_quest.title)
        self.assertContains(response, "Requires Warehouse")

        CompletedQuest.objects.create(session=self.session, quest=self.warehouse_job, ending_type="victory")
        response = self.client.get(reverse("scene_detail", kwargs={"scene_key": "hub__notice_board"}))
        self.assertContains(response, second_quest.title)
        self.assertNotContains(response, "Requires Warehouse")

    @override_settings(SHOW_LOCKED_COMPLETED_QUESTS=True)
    def test_stat_gated_quest(self):
        intellect_quest = Quest.objects.create(
            key="intellect_quest", title="Intellect Quest", description="Requires brains.", entrance_scene=self.warehouse_entrance
        )
        req = Requirement.objects.create(condition_type="stat_gte", stat_name="intellect", stat_value=9)
        group = RequirementGroup.objects.create(label="Requires Intellect 9", logic="all")
        group.requirements.add(req)
        intellect_quest.requirements.add(group)
        intellect_quest.hub_scenes.add(self.notice_board_scene)

        self.session.stats.intellect = 6
        self.session.stats.save(update_fields=["intellect"])
        response = self.client.get(reverse("scene_detail", kwargs={"scene_key": "hub__notice_board"}))
        self.assertContains(response, "Requires Intellect 9")

        self.session.stats.intellect = 9
        self.session.stats.save(update_fields=["intellect"])
        response = self.client.get(reverse("scene_detail", kwargs={"scene_key": "hub__notice_board"}))
        self.assertNotContains(response, "Requires Intellect 9")
        self.assertContains(response, intellect_quest.title)

    @override_settings(SHOW_LOCKED_COMPLETED_QUESTS=True)
    def test_completed_quest_rendering(self):
        self.warehouse_job.is_repeatable = True
        self.warehouse_job.save(update_fields=["is_repeatable"])
        CompletedQuest.objects.create(session=self.session, quest=self.warehouse_job, ending_type="victory")

        response = self.client.get(reverse("scene_detail", kwargs={"scene_key": "hub__notice_board"}))
        self.assertContains(response, "[ COMPLETED EVENTS ]")
        self.assertContains(response, "The Warehouse Job")
        self.assertContains(response, "Victory")
        self.assertContains(response, "Play again")

    def test_locked_and_completed_are_hidden_when_debug_toggle_off(self):
        second_quest = Quest.objects.create(
            key="second_quest_hidden",
            title="Hidden Locked Quest",
            description="Locked until warehouse is done.",
            entrance_scene=self.warehouse_entrance,
        )
        req = Requirement.objects.create(condition_type="quest_completed", required_quest=self.warehouse_job)
        group = RequirementGroup.objects.create(label="Requires Warehouse Hidden", logic="all")
        group.requirements.add(req)
        second_quest.requirements.add(group)
        second_quest.hub_scenes.add(self.notice_board_scene)
        CompletedQuest.objects.create(session=self.session, quest=self.warehouse_job, ending_type="victory")

        response = self.client.get(reverse("scene_detail", kwargs={"scene_key": "hub__notice_board"}))
        self.assertNotContains(response, "[ LOCKED EVENTS ]")
        self.assertNotContains(response, "[ COMPLETED EVENTS ]")

    def test_start_quest_view(self):
        locked_quest = Quest.objects.create(
            key="locked_quest", title="Locked Quest", description="Requires brains.", entrance_scene=self.warehouse_entrance
        )
        req = Requirement.objects.create(condition_type="stat_gte", stat_name="intellect", stat_value=99)
        group = RequirementGroup.objects.create(label="Requires Big Brains", logic="all")
        group.requirements.add(req)
        locked_quest.requirements.add(group)

        response = self.client.post(reverse("start_quest", kwargs={"quest_key": "locked_quest"}))
        self.assertEqual(response.status_code, 403)
        self.assertIn("[ REQUEST FAILED ]", response.content.decode())

        response = self.client.post(reverse("start_quest", kwargs={"quest_key": "the_warehouse_job"}))
        self.assertRedirects(response, reverse("scene_detail", kwargs={"scene_key": self.warehouse_entrance.key}))

        self.session.refresh_from_db()
        self.assertEqual(self.session.current_scene, self.warehouse_entrance)
        self.assertTrue(self.session.log.filter(text__icontains="took the job").exists())

    def test_start_quest_htmx(self):
        response = self.client.post(reverse("start_quest", kwargs={"quest_key": "the_warehouse_job"}), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="scene-panel"', response.content.decode())
        self.assertContains(response, self.warehouse_entrance.title)

    def test_start_quest_rejects_get_with_405(self):
        response = self.client.get(reverse("start_quest", kwargs={"quest_key": "the_warehouse_job"}))
        self.assertEqual(response.status_code, 405)

    def test_start_quest_non_htmx_error_renders_full_page_template(self):
        locked_quest = Quest.objects.create(
            key="locked_quest_non_htmx_error",
            title="Locked Quest Non HTMX Error",
            description="Requires brains.",
            entrance_scene=self.warehouse_entrance,
        )
        req = Requirement.objects.create(condition_type="stat_gte", stat_name="intellect", stat_value=99)
        group = RequirementGroup.objects.create(label="Requires Big Brains Non HTMX", logic="all")
        group.requirements.add(req)
        locked_quest.requirements.add(group)

        response = self.client.post(reverse("start_quest", kwargs={"quest_key": locked_quest.key}))
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "game/error.html")
        self.assertContains(response, "[ REQUEST FAILED ]", status_code=403)
        self.assertContains(response, "Status 403", status_code=403)
