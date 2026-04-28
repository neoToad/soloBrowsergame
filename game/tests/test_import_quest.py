from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from game.models import Scene


class ImportQuestCommandTests(TestCase):
    fixtures = [
        "game/fixtures/item.json",
    ]

    def _run_import(self, yaml_text: str) -> None:
        with TemporaryDirectory() as tmp_dir:
            yaml_path = Path(tmp_dir) / "quest.yaml"
            yaml_path.write_text(yaml_text, encoding="utf-8")
            call_command("import_quest", str(yaml_path))

    def test_import_reads_nested_ending_and_arrival_blocks(self):
        self._run_import(
            """
quest:
  key: import-test
  title: Import Test Quest
  description: Import test
  arc: null
  arc_order: 0
  is_repeatable: false
  hub_scenes: []
  entrance_scene: import-test__start
  requirements: []

scenes:
  - key: import-test__start
    scene_type: normal
    title: Start
    order: 10
    body: |
      Start scene.
    roll:
      requires_roll: false
      roll_stat: null
      roll_difficulty: null
    ending:
      ending_type: null
    arrival:
      cash_change: 1
      rep_change: 2
      heat_change: 3
      consume_item: brass_knuckles
      receive_property: null
      lose_property: null
    scene_items: []
    scene_contacts: []
    choices:
      - label: Finish
        order: 1
        target_scene: import-test__end
        success_scene: null
        failure_scene: null
        arrival_flavor: null
        failure_arrival_flavor: null
        set_flag_name: null
        clear_flag_name: null
        requirements: []

  - key: import-test__end
    scene_type: ending
    title: End
    order: 20
    body: |
      Ending scene.
    roll:
      requires_roll: false
      roll_stat: null
      roll_difficulty: null
    ending:
      ending_type: victory
    arrival:
      cash_change: 11
      rep_change: -2
      heat_change: 4
      consume_item: null
      receive_property: null
      lose_property: null
    scene_items: []
    scene_contacts: []
    choices: []
"""
        )

        start_scene = Scene.objects.get(key="import-test__start")
        end_scene = Scene.objects.get(key="import-test__end")

        self.assertEqual(start_scene.cash_change, 1)
        self.assertEqual(start_scene.rep_change, 2)
        self.assertEqual(start_scene.heat_change, 3)
        self.assertEqual(start_scene.consume_item.key, "brass_knuckles")
        self.assertEqual(end_scene.ending_type, "victory")
        self.assertEqual(end_scene.cash_change, 11)
        self.assertEqual(end_scene.rep_change, -2)
        self.assertEqual(end_scene.heat_change, 4)

    def test_import_errors_when_ending_scene_missing_ending_type(self):
        with self.assertRaises(CommandError):
            self._run_import(
                """
quest:
  key: import-test-quest-error
  title: Import Test Quest Error
  description: Import test
  arc: null
  arc_order: 0
  is_repeatable: false
  hub_scenes: []
  entrance_scene: import-test-error__end
  requirements: []

scenes:
  - key: import-test-error__end
    scene_type: ending
    title: End
    order: 10
    body: |
      Ending scene.
    roll:
      requires_roll: false
      roll_stat: null
      roll_difficulty: null
    ending:
      ending_type: null
    arrival:
      cash_change: 0
      rep_change: 0
      heat_change: 0
      consume_item: null
      receive_property: null
      lose_property: null
    scene_items: []
    scene_contacts: []
    choices: []
"""
            )

    def test_import_errors_when_choice_flag_name_is_invalid(self):
        with self.assertRaises(CommandError):
            self._run_import(
                """
quest:
  key: import-test-invalid-flag
  title: Import Test Invalid Flag
  description: Import test
  arc: null
  arc_order: 0
  is_repeatable: false
  hub_scenes: []
  entrance_scene: import-test-invalid-flag__start
  requirements: []

scenes:
  - key: import-test-invalid-flag__start
    scene_type: normal
    title: Start
    order: 10
    body: |
      Start scene.
    choices:
      - label: Finish
        order: 1
        target_scene: import-test-invalid-flag__end
        set_flag_name: bad flag name

  - key: import-test-invalid-flag__end
    scene_type: ending
    title: End
    order: 20
    body: |
      Ending scene.
    ending:
      ending_type: victory
    choices: []
"""
            )

    def test_import_errors_when_scene_key_prefix_does_not_match_quest_key(self):
        with self.assertRaises(CommandError):
            self._run_import(
                """
quest:
  key: import-prefix-quest
  title: Import Prefix Quest
  description: Import test
  arc: null
  arc_order: 0
  is_repeatable: false
  hub_scenes: []
  entrance_scene: wrong-prefix__start
  requirements: []

scenes:
  - key: wrong-prefix__start
    scene_type: normal
    title: Start
    order: 10
    body: |
      Start scene.
    choices: []
"""
            )
