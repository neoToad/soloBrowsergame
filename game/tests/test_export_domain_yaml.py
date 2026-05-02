from pathlib import Path
from tempfile import TemporaryDirectory

import yaml
from django.core.management import call_command
from django.test import TestCase

from game.models import Contact, Gang, Item, Scene
from game.models.combat import Enemy
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
        Choice.objects.create(scene=self.hub, label="Go", order=1, target_scene=self.target)
        SceneItem.objects.create(scene=self.hub, item=self.item, quantity=2, award_once=False)
        SceneContact.objects.create(scene=self.hub, contact=self.contact, action="gain", award_once=True)
        SceneGangStanding.objects.create(scene=self.hub, gang=self.gang, standing_change=4)

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
            ]
            for rel_path in expected_files:
                self.assertTrue((Path(tmp_dir) / rel_path).exists(), rel_path)

            hubs_data = yaml.safe_load((Path(tmp_dir) / "hubs/hubs.yaml").read_text(encoding="utf-8"))
            self.assertIn("hubs", hubs_data)
            hub_row = next(row for row in hubs_data["hubs"] if row["key"] == "hub__export")
            self.assertEqual(hub_row["arrival"]["discover_territory"], "export_territory")
            self.assertEqual(hub_row["arrival"]["gang_standing_changes"][0]["gang"], "export_gang")

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
            hub = Scene.objects.get(key="hub__export")
            self.assertEqual(hub.scene_gang_standings.count(), 1)
