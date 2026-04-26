from django.test import TestCase

from .test_factories import make_item


class ExportGameStateTest(TestCase):
    def test_build_game_state_payload_returns_expected_structure(self):
        from game.services.export_game_state import build_game_state_payload

        payload = build_game_state_payload()

        self.assertIsInstance(payload, dict)
        for key in ("meta", "counts", "items", "enemies", "contacts", "scenes", "quests", "jobs"):
            self.assertIn(key, payload)
        self.assertEqual(payload["meta"]["version"], 1)
        self.assertIn("exported_at", payload["meta"])

    def test_build_game_state_payload_counts_match_list_lengths(self):
        from game.services.export_game_state import build_game_state_payload

        make_item(key="exp__item", name="Export Item")
        payload = build_game_state_payload()

        self.assertEqual(payload["counts"]["items"], len(payload["items"]))
        self.assertEqual(payload["counts"]["scenes"], len(payload["scenes"]))
        self.assertEqual(payload["counts"]["enemies"], len(payload["enemies"]))
