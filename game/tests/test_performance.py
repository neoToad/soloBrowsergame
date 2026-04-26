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
