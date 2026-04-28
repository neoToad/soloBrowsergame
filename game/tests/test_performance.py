from django.test import Client, TestCase

from game.models import GameSession, Scene


class QueryBudgetTest(TestCase):
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

    def test_get_available_choices_uses_prefetch_budget(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from game.services.scene import get_available_choices

        scene = Scene.objects.get(key="warehouse__loading_dock")
        with CaptureQueriesContext(connection) as ctx:
            choices = get_available_choices(scene, self.session.stats, {}, {})

        self.assertGreaterEqual(len(choices), 1)
        self.assertLessEqual(len(ctx), 4)

    def test_get_notice_board_uses_prefetch_budget(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from game.services.scene import get_notice_board

        scene = Scene.objects.get(key="hub__notice_board")
        with CaptureQueriesContext(connection) as ctx:
            board = get_notice_board(scene, {}, {}, self.session.stats)

        self.assertIn("available", board)
        self.assertIn("locked", board)
        self.assertIn("completed", board)
        self.assertLessEqual(len(ctx), 4)

    def test_build_render_context_non_hub_uses_fewer_queries_than_hub(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from game.services.session import build_render_context, get_completed_map
        from game.services.inventory import get_player_inventory
        from game.utils import get_effective_stats

        inventory = get_player_inventory(self.session)
        completed_map = get_completed_map(self.session)
        effective_stats = get_effective_stats(self.session.stats, inventory)

        hub_scene = Scene.objects.get(key="hub__notice_board")
        non_hub_scene = Scene.objects.get(key="warehouse__loading_dock")

        with CaptureQueriesContext(connection) as hub_ctx:
            hub_render = build_render_context(
                self.session,
                hub_scene,
                self.session.stats,
                effective_stats,
                inventory,
                completed_map,
                combat_state=None,
            )
            _ = hub_render["choices"]
            _ = hub_render["district_job_targets"]
            _ = hub_render["player_contacts"]

        with CaptureQueriesContext(connection) as non_hub_ctx:
            non_hub_render = build_render_context(
                self.session,
                non_hub_scene,
                self.session.stats,
                effective_stats,
                inventory,
                completed_map,
                combat_state=None,
            )
            _ = non_hub_render["choices"]
            _ = non_hub_render["district_job_targets"]
            _ = non_hub_render["player_contacts"]

        self.assertGreaterEqual(len(hub_ctx), len(non_hub_ctx))

    def test_build_render_context_keeps_expected_jobs_and_notice_keys(self):
        from game.services.session import build_render_context, get_completed_map
        from game.services.inventory import get_player_inventory
        from game.utils import get_effective_stats

        inventory = get_player_inventory(self.session)
        completed_map = get_completed_map(self.session)
        effective_stats = get_effective_stats(self.session.stats, inventory)

        hub_scene = Scene.objects.get(key="hub__notice_board")
        non_hub_scene = Scene.objects.get(key="warehouse__loading_dock")

        hub_render = build_render_context(
            self.session,
            hub_scene,
            self.session.stats,
            effective_stats,
            inventory,
            completed_map,
            combat_state=None,
        )
        self.assertIsNotNone(hub_render["notice_board"])
        self.assertIn("district_job_targets", hub_render)
        self.assertIn("contact_job_offers", hub_render)
        self.assertIn("active_job_run", hub_render)

        non_hub_render = build_render_context(
            self.session,
            non_hub_scene,
            self.session.stats,
            effective_stats,
            inventory,
            completed_map,
            combat_state=None,
        )
        self.assertIsNone(non_hub_render["notice_board"])
        self.assertEqual(non_hub_render["district_job_targets"], [])
        self.assertEqual(non_hub_render["contact_job_offers"], [])
        self.assertIsNone(non_hub_render["active_job_run"])
