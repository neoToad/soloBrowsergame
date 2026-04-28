import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from game.models import Arc, Choice, Quest, Scene
from game.models.items import Item


class ExportAllFixturesTests(TestCase):
    def test_export_serializes_foreign_keys_as_primary_keys(self):
        item = Item.objects.create(key="fixture-item", name="Fixture Item", description="")
        arc = Arc.objects.create(key="fixture-arc", title="Fixture Arc", order=1)
        quest = Quest.objects.create(
            key="fixture-quest",
            title="Fixture Quest",
            description="",
            arc=arc,
            arc_order=1,
        )
        scene = Scene.objects.create(
            key="fixture-quest__start",
            title="Start",
            body="",
            quest=quest,
            consume_item=item,
        )
        Choice.objects.create(scene=scene, label="Continue", target_scene=scene, order=1)

        with TemporaryDirectory() as tmp_dir:
            with patch("game.management.commands.export_all_fixtures.FIXTURES_DIR", tmp_dir):
                call_command("export_all_fixtures")

            scene_rows = json.loads(Path(tmp_dir, "scene.json").read_text(encoding="utf-8"))
            choice_rows = json.loads(Path(tmp_dir, "choice.json").read_text(encoding="utf-8"))

            exported_scene_fields = scene_rows[0]["fields"]
            exported_choice_fields = choice_rows[0]["fields"]
            self.assertEqual(exported_scene_fields["quest"], quest.pk)
            self.assertEqual(exported_scene_fields["consume_item"], item.pk)
            self.assertEqual(exported_choice_fields["scene"], scene.pk)
            self.assertEqual(exported_choice_fields["target_scene"], scene.pk)

    def test_exported_fixtures_can_round_trip_via_loaddata(self):
        item = Item.objects.create(key="roundtrip-item", name="Roundtrip Item", description="")
        arc = Arc.objects.create(key="roundtrip-arc", title="Roundtrip Arc", order=1)
        quest = Quest.objects.create(
            key="roundtrip-quest",
            title="Roundtrip Quest",
            description="",
            arc=arc,
            arc_order=1,
        )
        scene = Scene.objects.create(
            key="roundtrip-quest__start",
            title="Start",
            body="",
            quest=quest,
            consume_item=item,
        )
        Choice.objects.create(scene=scene, label="Continue", target_scene=scene, order=1)

        with TemporaryDirectory() as tmp_dir:
            with patch("game.management.commands.export_all_fixtures.FIXTURES_DIR", tmp_dir):
                call_command("export_all_fixtures")

            Choice.objects.all().delete()
            Scene.objects.all().delete()
            Quest.objects.all().delete()
            Arc.objects.all().delete()
            Item.objects.all().delete()

            for fixture_name in ("item", "arc", "quest", "scene", "choice"):
                call_command("loaddata", str(Path(tmp_dir, f"{fixture_name}.json")), verbosity=0)

        restored_scene = Scene.objects.get(key="roundtrip-quest__start")
        restored_choice = Choice.objects.get(scene=restored_scene)
        self.assertEqual(restored_scene.quest.key, "roundtrip-quest")
        self.assertEqual(restored_scene.consume_item.key, "roundtrip-item")
        self.assertEqual(restored_choice.target_scene_id, restored_scene.id)
