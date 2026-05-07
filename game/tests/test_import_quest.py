from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from game.models import Contact, Enemy, Gang, Scene
from game.models.combat import CombatEncounter
from game.models.property import Territory
from game.services.importers.domain import import_quest_data


class ImportQuestCommandTests(TestCase):
    fixtures = [
        "game/fixtures/item.json",
    ]

    def _run_import(self, yaml_text: str) -> None:
        with TemporaryDirectory() as tmp_dir:
            yaml_path = Path(tmp_dir) / "quest.yaml"
            yaml_path.write_text(yaml_text, encoding="utf-8")
            call_command("import_quest", str(yaml_path))

    def _base_reimport_payload(self) -> dict:
        return {
            "quest": {
                "key": "reimport-scene-links",
                "title": "Reimport Scene Links",
                "description": "Reimport behavior",
                "arc": None,
                "arc_order": 0,
                "is_repeatable": False,
                "hub_scenes": [],
                "entrance_scene": "reimport-scene-links__start",
                "requirements": [],
            },
            "scenes": [
                {
                    "key": "reimport-scene-links__start",
                    "scene_type": "normal",
                    "title": "Start",
                    "body": "Start",
                    "order": 0,
                    "choices": [],
                }
            ],
        }

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

    def test_import_resolves_territory_arrival_fields(self):
        Territory.objects.create(key="the_docks", name="The Docks")
        Gang.objects.create(key="dockers", name="Dockers")
        self._run_import(
            """
quest:
  key: import-territory-arrival
  title: Import Territory Arrival
  description: Import test
  arc: null
  arc_order: 0
  is_repeatable: false
  hub_scenes: []
  entrance_scene: import-territory-arrival__start
  requirements: []

scenes:
  - key: import-territory-arrival__start
    scene_type: normal
    title: Start
    order: 10
    body: |
      Start scene.
    arrival:
      cash_change: 0
      rep_change: 0
      heat_change: 0
      consume_item: null
      receive_property: null
      lose_property: null
      receive_territory: the_docks
      lose_territory: null
      discover_territory: the_docks
      gang_standing_changes:
        - gang: dockers
          standing_change: 2
    choices: []
"""
        )

        start_scene = Scene.objects.get(key="import-territory-arrival__start")
        self.assertIsNotNone(start_scene.receive_territory)
        self.assertEqual(start_scene.receive_territory.key, "the_docks")
        self.assertIsNotNone(start_scene.discover_territory)
        self.assertEqual(start_scene.discover_territory.key, "the_docks")
        self.assertEqual(start_scene.scene_gang_standings.count(), 1)
        standing = start_scene.scene_gang_standings.get()
        self.assertEqual(standing.gang.key, "dockers")
        self.assertEqual(standing.standing_change, 2)

    def test_import_quest_reimport_recreates_scene_items_and_tracks_counts(self):
        first = self._base_reimport_payload()
        first["scenes"][0]["scene_items"] = [{"item": "brass_knuckles", "quantity": 1, "award_once": True}]
        first_result = import_quest_data(first)
        self.assertEqual(first_result.counts["scene_items"].created, 1)
        self.assertEqual(first_result.counts.get("scene_items").deleted, 0)

        second = self._base_reimport_payload()
        second["scenes"][0]["scene_items"] = [{"item": "brass_knuckles", "quantity": 3, "award_once": False}]
        second_result = import_quest_data(second)

        start_scene = Scene.objects.get(key="reimport-scene-links__start")
        self.assertEqual(start_scene.scene_items.count(), 1)
        scene_item = start_scene.scene_items.get()
        self.assertEqual(scene_item.quantity, 3)
        self.assertFalse(scene_item.award_once)
        self.assertEqual(second_result.counts["scene_items"].deleted, 1)
        self.assertEqual(second_result.counts["scene_items"].created, 1)

    def test_import_quest_reimport_recreates_scene_contacts_and_tracks_counts(self):
        Contact.objects.create(key="fixer", name="Fixer", description="Test contact")
        first = self._base_reimport_payload()
        first["scenes"][0]["scene_contacts"] = [{"contact": "fixer", "action": "gain", "award_once": True}]
        first_result = import_quest_data(first)
        self.assertEqual(first_result.counts["scene_contacts"].created, 1)
        self.assertEqual(first_result.counts.get("scene_contacts").deleted, 0)

        second = self._base_reimport_payload()
        second["scenes"][0]["scene_contacts"] = [{"contact": "fixer", "action": "lose", "award_once": False}]
        second_result = import_quest_data(second)

        start_scene = Scene.objects.get(key="reimport-scene-links__start")
        self.assertEqual(start_scene.scene_contacts.count(), 1)
        scene_contact = start_scene.scene_contacts.get()
        self.assertEqual(scene_contact.action, "lose")
        self.assertFalse(scene_contact.award_once)
        self.assertEqual(second_result.counts["scene_contacts"].deleted, 1)
        self.assertEqual(second_result.counts["scene_contacts"].created, 1)

    def test_import_quest_combat_missing_enemy_warns_and_skips_combat_encounter(self):
        data = {
            "quest": {
                "key": "missing-combat-enemy",
                "title": "Missing Combat Enemy",
                "description": "Combat import warning",
                "arc": None,
                "arc_order": 0,
                "is_repeatable": False,
                "hub_scenes": [],
                "entrance_scene": "missing-combat-enemy__fight",
                "requirements": [],
            },
            "scenes": [
                {
                    "key": "missing-combat-enemy__fight",
                    "scene_type": "combat",
                    "title": "Fight",
                    "body": "Fight body",
                    "order": 0,
                    "combat_encounter": {"enemy": "does-not-exist"},
                    "choices": [],
                }
            ],
        }

        result = import_quest_data(data)

        self.assertTrue(any("Enemy 'does-not-exist' not found in DB; FK set to null" in warning for warning in result.warnings))
        self.assertTrue(
            any("Skipping CombatEncounter for 'missing-combat-enemy__fight'; enemy not found" in warning for warning in result.warnings)
        )
        self.assertFalse(Enemy.objects.filter(key="does-not-exist").exists())
        self.assertFalse(
            CombatEncounter.objects.filter(scene__key="missing-combat-enemy__fight").exists()
        )
