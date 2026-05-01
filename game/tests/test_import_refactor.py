from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import TestCase

from game.models import Contact, Enemy, Property, Quest, RequirementGroup, Scene, Territory


class ImportRefactorTests(TestCase):
    def _write_and_run(self, command: str, filename: str, yaml_text: str) -> None:
        with TemporaryDirectory() as tmp_dir:
            yaml_path = Path(tmp_dir) / filename
            yaml_path.write_text(yaml_text, encoding="utf-8")
            call_command(command, str(yaml_path))

    def test_requirement_group_scope_prevents_cross_quest_mutation(self):
        self._write_and_run(
            "import_quest",
            "quest_a.yaml",
            """
quest:
  key: scoped-quest-a
  title: Scoped Quest A
  description: Test
  arc: null
  arc_order: 0
  is_repeatable: false
  hub_scenes: []
  entrance_scene: scoped-quest-a__start
  requirements:
    - label: Shared Label
      logic: all
      conditions:
        - condition_type: has_flag
          flag_name: flag_a

scenes:
  - key: scoped-quest-a__start
    scene_type: normal
    title: Start
    order: 0
    body: Start
    choices: []
""",
        )
        self._write_and_run(
            "import_quest",
            "quest_b.yaml",
            """
quest:
  key: scoped-quest-b
  title: Scoped Quest B
  description: Test
  arc: null
  arc_order: 0
  is_repeatable: false
  hub_scenes: []
  entrance_scene: scoped-quest-b__start
  requirements:
    - label: Shared Label
      logic: all
      conditions:
        - condition_type: has_flag
          flag_name: flag_b

scenes:
  - key: scoped-quest-b__start
    scene_type: normal
    title: Start
    order: 0
    body: Start
    choices: []
""",
        )

        quest_a = Quest.objects.get(key="scoped-quest-a")
        quest_b = Quest.objects.get(key="scoped-quest-b")
        group_a = quest_a.requirements.get()
        group_b = quest_b.requirements.get()

        req_a = group_a.requirements.get()
        req_b = group_b.requirements.get()

        self.assertEqual(req_a.flag_name, "flag_a")
        self.assertEqual(req_b.flag_name, "flag_b")
        self.assertNotEqual(group_a.pk, group_b.pk)
        self.assertEqual(group_a.scope_type, "quest")
        self.assertEqual(group_a.scope_key, "scoped-quest-a")
        self.assertEqual(group_b.scope_type, "quest")
        self.assertEqual(group_b.scope_key, "scoped-quest-b")

    def test_reimport_updates_same_scoped_requirement_group(self):
        base_yaml = """
quest:
  key: scoped-reimport
  title: Scoped Reimport
  description: Test
  arc: null
  arc_order: 0
  is_repeatable: false
  hub_scenes: []
  entrance_scene: scoped-reimport__start
  requirements:
    - label: Strength Gate
      logic: all
      conditions:
        - condition_type: stat_gte
          stat_name: strength
          stat_value: {stat_value}

scenes:
  - key: scoped-reimport__start
    scene_type: normal
    title: Start
    order: 0
    body: Start
    choices: []
"""
        self._write_and_run("import_quest", "reimport.yaml", base_yaml.format(stat_value=5))
        group_pk = Quest.objects.get(key="scoped-reimport").requirements.get().pk
        self._write_and_run("import_quest", "reimport.yaml", base_yaml.format(stat_value=9))

        quest = Quest.objects.get(key="scoped-reimport")
        self.assertEqual(quest.requirements.count(), 1)
        self.assertEqual(RequirementGroup.objects.filter(scope_type="quest", scope_key="scoped-reimport").count(), 1)
        group = quest.requirements.get()
        self.assertEqual(group.pk, group_pk)
        self.assertEqual(group.requirements.get().stat_value, 9)

    def test_import_all_discovers_and_imports_yaml_directory(self):
        with TemporaryDirectory() as tmp_dir:
            quest_yaml = Path(tmp_dir) / "quest.yaml"
            quest_yaml.write_text(
                """
quest:
  key: all-import-quest
  title: All Import Quest
  description: Test
  arc: null
  arc_order: 0
  is_repeatable: false
  hub_scenes: []
  entrance_scene: all-import-quest__start
  requirements: []

scenes:
  - key: all-import-quest__start
    scene_type: normal
    title: Start
    order: 0
    body: Start
    choices: []
""",
                encoding="utf-8",
            )
            hubs_yaml = Path(tmp_dir) / "hubs.yaml"
            hubs_yaml.write_text(
                """
hubs:
  - key: all-import-hub
    scene_type: hub
    title: Hub
    order: 0
    body: Hub
    choices: []
""",
                encoding="utf-8",
            )
            call_command("import_all", tmp_dir)

        self.assertTrue(Quest.objects.filter(key="all-import-quest").exists())
        self.assertTrue(Scene.objects.filter(key="all-import-hub").exists())

    def test_import_all_resolves_scene_property_and_territory_fks_from_world_keys(self):
        with TemporaryDirectory() as tmp_dir:
            world_yaml = Path(tmp_dir) / "world.yaml"
            world_yaml.write_text(
                """
properties:
  - key: storage_unit
    name: Dockside Warehouse Unit
    property_type: business
    cash_per_turn: 200
    heat_per_turn: 3
    rep_per_turn: 0
    is_contestable: true
    resolution_scene: null
territories:
  - key: the_docks
    name: The Docks
    cash_per_turn: 225
    heat_per_turn: 3
    rep_per_turn: 1
    is_contestable: true
    resolution_scene: null
""",
                encoding="utf-8",
            )
            quest_yaml = Path(tmp_dir) / "quest.yaml"
            quest_yaml.write_text(
                """
quest:
  key: property-fk-quest
  title: Property FK Quest
  description: Test
  arc: null
  arc_order: 0
  is_repeatable: false
  hub_scenes: []
  entrance_scene: property-fk-quest__start
  requirements: []

scenes:
  - key: property-fk-quest__start
    scene_type: normal
    title: Start
    order: 0
    body: Start
    arrival:
      cash_change: 0
      rep_change: 0
      heat_change: 0
      consume_item: null
      receive_property: storage_unit
      lose_property: null
      receive_territory: null
      lose_territory: null
    choices: []

  - key: property-fk-quest__territory
    scene_type: normal
    title: Territory
    order: 1
    body: Territory
    arrival:
      cash_change: 0
      rep_change: 0
      heat_change: 0
      consume_item: null
      receive_property: null
      lose_property: null
      receive_territory: the_docks
      lose_territory: null
    choices: []
""",
                encoding="utf-8",
            )
            call_command("import_all", tmp_dir)

        scene = Scene.objects.get(key="property-fk-quest__start")
        territory_scene = Scene.objects.get(key="property-fk-quest__territory")
        self.assertIsNotNone(scene.receive_property)
        self.assertEqual(scene.receive_property.key, "storage_unit")
        self.assertIsNotNone(territory_scene.receive_territory)
        self.assertEqual(territory_scene.receive_territory.key, "the_docks")
        self.assertTrue(Property.objects.filter(key="storage_unit").exists())
        self.assertTrue(Territory.objects.filter(key="the_docks").exists())

    def test_import_all_merges_split_enemies_and_contacts_files(self):
        with TemporaryDirectory() as tmp_dir:
            enemies_yaml = Path(tmp_dir) / "enemies.yaml"
            enemies_yaml.write_text(
                """
enemies:
  - key: split_test_enemy
    name: Split Test Enemy
    description: Enemy from split file.
    max_hp: 21
    attack_modifier: 2
    defense: 10
    damage_min: 2
    damage_max: 6
""",
                encoding="utf-8",
            )
            contacts_yaml = Path(tmp_dir) / "contacts.yaml"
            contacts_yaml.write_text(
                """
contacts:
  - key: split_test_contact
    name: Split Test Contact
    description: Contact from split file.
""",
                encoding="utf-8",
            )
            call_command("import_all", tmp_dir)

        self.assertTrue(Enemy.objects.filter(key="split_test_enemy").exists())
        self.assertTrue(Contact.objects.filter(key="split_test_contact").exists())
