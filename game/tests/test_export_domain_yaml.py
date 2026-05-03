from pathlib import Path
from tempfile import TemporaryDirectory

import yaml
from django.core.management import call_command
from django.test import TestCase

from game.models import Contact, Gang, Item, Quest, Scene
from game.models.combat import Enemy
from game.models.requirements import Requirement, RequirementGroup
from game.models.property import Property, Territory
from game.models.world import Choice, SceneContact, SceneGangStanding, SceneItem


class ExportDomainYamlTests(TestCase):
    def setUp(self):
        self.item = Item.objects.create(
            key="export_item",
            name="Export Item",
            description="Export item description",
            is_consumable=False,
        )
        self.enemy = Enemy.objects.create(
            key="export_enemy",
            name="Export Enemy",
            description="Export enemy description",
            max_hp=14,
            attack_modifier=2,
            defense=9,
            damage_min=2,
            damage_max=5,
        )
        self.contact = Contact.objects.create(
            key="export_contact",
            name="Export Contact",
            description="Export contact description",
        )
        self.gang = Gang.objects.create(
            key="export_gang",
            name="Export Gang",
            description="Export gang description",
        )
        self.hub = Scene.objects.create(
            key="hub__export",
            scene_type="hub",
            title="Export Hub",
            body="Hub body",
            order=5,
            cash_change=1,
            rep_change=2,
            heat_change=3,
            consume_item=self.item,
        )
        self.target = Scene.objects.create(
            key="hub__export_target",
            scene_type="hub",
            title="Export Hub Target",
            body="Hub target body",
            order=6,
        )
        self.property = Property.objects.create(
            key="export_property",
            name="Export Property",
            description="Export property",
            property_type="business",
            cash_per_turn=10,
            heat_per_turn=1,
            rep_per_turn=2,
            is_contestable=True,
            resolution_scene=self.hub,
        )
        self.territory = Territory.objects.create(
            key="export_territory",
            name="Export Territory",
            description="Export territory",
            cash_per_turn=11,
            heat_per_turn=2,
            rep_per_turn=3,
            is_contestable=True,
            resolution_scene=self.hub,
        )
        self.hub.receive_property = self.property
        self.hub.receive_territory = self.territory
        self.hub.discover_territory = self.territory
        self.hub.save(update_fields=["receive_property", "receive_territory", "discover_territory"])
        hub_choice = Choice.objects.create(scene=self.hub, label="Go", order=1, target_scene=self.target)
        req = Requirement.objects.create(condition_type="has_flag", flag_name="hub_gate_flag")
        req_group = RequirementGroup.objects.create(
            label="Hub gate",
            logic="all",
            group_key="hub__export:1:Go",
        )
        req_group.requirements.add(req)
        hub_choice.requirements.add(req_group)
        SceneItem.objects.create(scene=self.hub, item=self.item, quantity=2, award_once=False)
        SceneContact.objects.create(scene=self.hub, contact=self.contact, action="gain", award_once=True)
        SceneGangStanding.objects.create(scene=self.hub, gang=self.gang, standing_change=4)
        self.quest = Quest.objects.create(
            key="export-domain-quest",
            title="Export Domain Quest",
            description="Quest exported from export_all_yaml.",
            arc=None,
            arc_order=0,
            is_repeatable=False,
        )
        self.quest_start = Scene.objects.create(
            key="export-domain-quest__start",
            scene_type="normal",
            title="Start",
            body="Start body",
            order=1,
            quest=self.quest,
        )
        self.quest_end = Scene.objects.create(
            key="export-domain-quest__end",
            scene_type="ending",
            ending_type="victory",
            title="End",
            body="End body",
            order=2,
            quest=self.quest,
        )
        Choice.objects.create(scene=self.quest_start, label="Finish", order=1, target_scene=self.quest_end)
        self.quest.entrance_scene = self.quest_start
        self.quest.save(update_fields=["entrance_scene"])

    def test_export_all_yaml_writes_split_files_with_expected_roots(self):
        with TemporaryDirectory() as tmp_dir:
            call_command("export_all_yaml", "--out-dir", tmp_dir)
            expected_files = [
                "items.yaml",
                "enemies.yaml",
                "contacts.yaml",
                "hubs/hubs.yaml",
                "gangs.yaml",
                "properties.yaml",
                "territories.yaml",
                "quests/misc/export-domain-quest.yaml",
            ]
            for rel_path in expected_files:
                self.assertTrue((Path(tmp_dir) / rel_path).exists(), rel_path)

            hubs_data = yaml.safe_load((Path(tmp_dir) / "hubs/hubs.yaml").read_text(encoding="utf-8"))
            self.assertIn("hubs", hubs_data)
            hub_row = next(row for row in hubs_data["hubs"] if row["key"] == "hub__export")
            self.assertEqual(hub_row["arrival"]["discover_territory"], "export_territory")
            self.assertEqual(hub_row["arrival"]["gang_standing_changes"][0]["gang"], "export_gang")
            choice_row = next(row for row in hub_row["choices"] if row["label"] == "Go")
            self.assertEqual(len(choice_row["requirements"]), 1)
            self.assertEqual(choice_row["requirements"][0]["label"], "Hub gate")
            self.assertEqual(choice_row["requirements"][0]["conditions"][0]["condition_type"], "has_flag")
            self.assertEqual(choice_row["requirements"][0]["conditions"][0]["flag_name"], "hub_gate_flag")

            properties_data = yaml.safe_load((Path(tmp_dir) / "properties.yaml").read_text(encoding="utf-8"))
            self.assertIn("properties", properties_data)
            property_row = next(row for row in properties_data["properties"] if row["key"] == "export_property")
            self.assertEqual(property_row["description"], "Export property")

    def test_export_all_yaml_combined_round_trip_imports_cleanly(self):
        with TemporaryDirectory() as tmp_dir:
            call_command(
                "export_all_yaml",
                "--out-dir",
                tmp_dir,
                "--combined-world",
                "--combined-enemies-contacts",
            )
            call_command("import_all", tmp_dir)

            self.assertTrue(Item.objects.filter(key="export_item").exists())
            self.assertTrue(Enemy.objects.filter(key="export_enemy").exists())
            self.assertTrue(Contact.objects.filter(key="export_contact").exists())
            self.assertTrue(Gang.objects.filter(key="export_gang").exists())
            self.assertTrue(Property.objects.filter(key="export_property").exists())
            self.assertTrue(Territory.objects.filter(key="export_territory").exists())
            self.assertTrue(Quest.objects.filter(key="export-domain-quest").exists())
            self.assertEqual(Property.objects.get(key="export_property").description, "Export property")
            hub = Scene.objects.get(key="hub__export")
            self.assertEqual(hub.scene_gang_standings.count(), 1)
