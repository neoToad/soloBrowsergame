from django.test import Client, TestCase
from django.urls import reverse

from game.models import CompletedQuest, Quest, Scene

from .test_factories import make_game_session


class LevelUpTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.session = make_game_session(self.client)
        self.stats = self.session.stats

    def test_level_up_success(self):
        self.stats.stat_points = 1
        self.stats.strength = 10
        self.stats.save()

        response = self.client.post(reverse("level_up"), {"stat": "strength"}, HTTP_HX_REQUEST="true")

        self.assertEqual(response.status_code, 200)
        self.stats.refresh_from_db()
        self.assertEqual(self.stats.strength, 11)
        self.assertEqual(self.stats.stat_points, 0)
        self.assertIn('id="stats-bar"', response.content.decode())

    def test_level_up_no_points(self):
        self.stats.stat_points = 0
        self.stats.save()

        response = self.client.post(reverse("level_up"), {"stat": "strength"}, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 400)

    def test_scene_renders_level_up_panel_after_level_gain(self):
        self.stats.level = 2
        self.stats.stat_points = 1
        self.stats.save()

        response = self.client.get(
            reverse("scene_detail", kwargs={"scene_key": self.session.current_scene.key})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MOVING UP")
        self.assertContains(response, "Word travels fast.")

    def test_scene_hides_level_up_panel_when_none_available(self):
        self.stats.stat_points = 0
        self.stats.save()

        response = self.client.get(
            reverse("scene_detail", kwargs={"scene_key": self.session.current_scene.key})
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "MOVING UP")


class ProgressionTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.session = make_game_session(self.client)
        self.stats = self.session.stats

    def test_award_xp_crosses_multiple_levels(self):
        from game.services.progression import award_xp

        self.stats.level = 1
        self.stats.experience = 150
        self.stats.stat_points = 0
        self.stats.stat_points_awarded = 0
        self.stats.save()

        levels = award_xp(self.session, self.stats, 500)
        self.stats.refresh_from_db()

        self.assertEqual(levels, [2, 3])
        self.assertEqual(self.stats.level, 3)
        self.assertEqual(self.stats.experience, 650)
        self.assertEqual(self.stats.stat_points, 6)
        self.assertEqual(self.stats.stat_points_awarded, 6)

    def test_award_xp_irregular_increments_do_not_over_or_under_grant_points(self):
        from game.services.progression import award_xp

        self.stats.experience = 0
        self.stats.stat_points = 0
        self.stats.stat_points_awarded = 0
        self.stats.save()

        award_xp(self.session, self.stats, 7)
        award_xp(self.session, self.stats, 133)
        award_xp(self.session, self.stats, 250)
        self.stats.refresh_from_db()

        self.assertEqual(self.stats.experience, 390)
        self.assertEqual(self.stats.stat_points, 3)
        self.assertEqual(self.stats.stat_points_awarded, 3)

    def test_award_xp_catches_up_legacy_rows_on_first_post_migration_xp_gain(self):
        from game.services.progression import award_xp

        self.stats.experience = 550
        self.stats.stat_points = 0
        self.stats.stat_points_awarded = 0
        self.stats.save()

        award_xp(self.session, self.stats, 1)
        self.stats.refresh_from_db()

        self.assertEqual(self.stats.experience, 551)
        self.assertEqual(self.stats.stat_points, 5)
        self.assertEqual(self.stats.stat_points_awarded, 5)


class MaxHpTest(TestCase):
    def test_create_session_sets_hp_and_max_hp_from_formula(self):
        from game.utils import compute_max_hp

        client = Client()
        session = make_game_session(client)
        stats = session.stats
        expected = compute_max_hp(5)
        self.assertEqual(stats.max_hp, expected)
        self.assertEqual(stats.hp, expected)

    def test_effective_stats_max_hp_reflects_strength_item_bonus(self):
        from game.models import PlayerInventory
        from game.models.items import Item
        from game.services.inventory import get_player_inventory
        from game.utils import compute_max_hp, get_effective_stats

        client = Client()
        session = make_game_session(client)
        stats = session.stats
        stats.strength = 10
        stats.max_hp = compute_max_hp(10)
        stats.save()

        str_item = Item.objects.create(
            key="maxhp__str_charm",
            name="STR Charm",
            description="",
            passive_stat="strength",
            passive_value=2,
        )
        PlayerInventory.objects.create(session=session, item=str_item, quantity=1)

        inventory = get_player_inventory(session)
        effective = get_effective_stats(stats, inventory)

        self.assertEqual(effective.strength, 12)
        self.assertEqual(effective.max_hp, compute_max_hp(12))
        self.assertEqual(stats.max_hp, compute_max_hp(10))

    def test_spend_strength_updates_max_hp_and_caps_hp(self):
        from game.constants import STAT_FIELDS
        from game.services.progression import spend_stat_point
        from game.utils import compute_max_hp

        client = Client()
        session = make_game_session(client)
        stats = session.stats
        stats.strength = 10
        stats.max_hp = compute_max_hp(10)
        stats.hp = compute_max_hp(10)
        stats.stat_points = 1
        stats.save()

        spend_stat_point(stats, "strength", STAT_FIELDS)
        stats.refresh_from_db()

        self.assertEqual(stats.strength, 11)
        self.assertEqual(stats.max_hp, compute_max_hp(11))
        self.assertLessEqual(stats.hp, stats.max_hp)


class ProgressionServiceTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.session = make_game_session(self.client)
        self.stats = self.session.stats

    def test_maybe_complete_quest_non_ending_scene_returns_empty(self):
        from game.services.progression import maybe_complete_quest

        normal_scene = Scene.objects.create(key="prog__normal", title="Normal", body="", scene_type="normal")

        result = maybe_complete_quest(self.session, self.stats, normal_scene, {})

        self.assertEqual(result, [])
        self.assertFalse(CompletedQuest.objects.filter(session=self.session).exists())

    def test_maybe_complete_quest_already_completed_does_not_duplicate(self):
        from game.services.progression import maybe_complete_quest

        quest = Quest.objects.create(key="prog__quest", title="Prog Quest", description="")
        ending_scene = Scene.objects.create(
            quest=quest,
            key="prog__ending",
            title="Ending",
            body="",
            scene_type="ending",
            ending_type="victory",
        )
        CompletedQuest.objects.create(session=self.session, quest=quest, ending_type="victory")
        completed_map = {quest.id: "victory"}

        result = maybe_complete_quest(self.session, self.stats, ending_scene, completed_map)

        self.assertEqual(result, [])
        self.assertEqual(CompletedQuest.objects.filter(session=self.session, quest=quest).count(), 1)
