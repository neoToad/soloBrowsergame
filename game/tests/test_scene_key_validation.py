from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from game.models import Quest, Scene


class ReportInvalidSceneKeysCommandTests(TestCase):
    def test_report_invalid_scene_keys_outputs_invalid_rows(self):
        quest = Quest.objects.create(key="scene-key-quest", title="Scene Key Quest", description="")
        Scene.objects.create(
            quest=quest,
            key="wrong-prefix__start",
            title="Start Scene",
            body="",
            scene_type="normal",
        )

        out = StringIO()
        call_command("report_invalid_scene_keys", stdout=out)
        output = out.getvalue()
        self.assertIn("wrong-prefix__start", output)
        self.assertIn("Found 1 invalid scene key(s).", output)

    def test_report_invalid_scene_keys_fix_renames_when_no_conflict(self):
        quest = Quest.objects.create(key="scene-key-quest-2", title="Scene Key Quest 2", description="")
        scene = Scene.objects.create(
            quest=quest,
            key="wrong-prefix__legacy",
            title="City Roof",
            body="",
            scene_type="normal",
        )

        call_command("report_invalid_scene_keys", "--fix")
        scene.refresh_from_db()
        self.assertEqual(scene.key, "scene-key-quest-2__city-roof")

    def test_report_invalid_scene_keys_fix_skips_on_conflict(self):
        quest = Quest.objects.create(key="scene-key-quest-3", title="Scene Key Quest 3", description="")
        Scene.objects.create(
            quest=quest,
            key="scene-key-quest-3__city-roof",
            title="City Roof",
            body="",
            scene_type="normal",
        )
        invalid_scene = Scene.objects.create(
            quest=quest,
            key="wrong-prefix__legacy",
            title="City Roof",
            body="",
            scene_type="normal",
        )

        out = StringIO()
        call_command("report_invalid_scene_keys", "--fix", stdout=out)
        invalid_scene.refresh_from_db()
        self.assertEqual(invalid_scene.key, "wrong-prefix__legacy")
        self.assertIn("conflicts 1", out.getvalue())
