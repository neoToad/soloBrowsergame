from pathlib import Path
from tempfile import TemporaryDirectory

import yaml
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from game.models import (
    Arc,
    Choice,
    Contact,
    Enemy,
    Gang,
    Quest,
    Requirement,
    RequirementGroup,
    Scene,
    SceneContact,
    SceneGangStanding,
    SceneItem,
    Territory,
)
from game.models.items import Item
from game.services.quest_export import build_quest_export_payload, default_quest_export_path


class ExportQuestTests(TestCase):
    def setUp(self):
        self.arc = Arc.objects.create(key="intro", title="Intro", order=1)
        self.item = Item.objects.create(key="brass_knuckles", name="Brass Knuckles", description="")
        self.contact = Contact.objects.create(key="sister", name="Sister", description="")
        self.gang = Gang.objects.create(key="dockers", name="Dockers", description="")
        self.territory = Territory.objects.create(key="the_docks", name="The Docks")
        self.enemy = Enemy.objects.create(
            key="terrell",
            name="Terrell",
            description="",
            max_hp=10,
            attack_modifier=0,
            defense=8,
            damage_min=1,
            damage_max=2,
        )
        self.quest = Quest.objects.create(
            key="export-one",
            title="Export One",
            description="Quest for export.",
            arc=self.arc,
            arc_order=3,
            is_repeatable=False,
        )
        self.start = Scene.objects.create(
            key="export-one__start",
            scene_type="normal",
            title="Start",
            body="Start scene.",
            order=10,
            quest=self.quest,
        )
        self.fight = Scene.objects.create(
            key="export-one__fight",
            scene_type="combat",
            title="Fight",
            body="Fight scene.",
            order=20,
            quest=self.quest,
            discover_territory=self.territory,
        )
        self.end = Scene.objects.create(
            key="export-one__end",
            scene_type="ending",
            ending_type="victory",
            title="End",
            body="End scene.",
            order=30,
            quest=self.quest,
        )
        self.quest.entrance_scene = self.start
        self.quest.save(update_fields=["entrance_scene"])
        self.quest.hub_scenes.add(self.start)

        group = RequirementGroup.objects.create(
            label="Need flag",
            logic="all",
            scope_type="quest",
            scope_key=self.quest.key,
            group_key="need-flag",
        )
        req = Requirement.objects.create(condition_type="has_flag", flag_name="intro_seen")
        group.requirements.add(req)
        self.quest.requirements.add(group)

        choice = Choice.objects.create(
            scene=self.start,
            label="Go fight",
            order=1,
            target_scene=self.fight,
            arrival_flavor="You move.",
            set_flag_name="intro_seen",
        )
        cgroup = RequirementGroup.objects.create(
            label="Choice gate",
            logic="all",
            scope_type="choice",
            scope_key=f"{self.start.key}:{choice.order}:{choice.label}",
            group_key="choice-gate",
        )
        creq = Requirement.objects.create(condition_type="has_item", required_item=self.item)
        cgroup.requirements.add(creq)
        choice.requirements.add(cgroup)

        SceneItem.objects.create(scene=self.fight, item=self.item, quantity=1, award_once=True)
        SceneContact.objects.create(scene=self.fight, contact=self.contact, action="gain", award_once=True)
        SceneGangStanding.objects.create(scene=self.fight, gang=self.gang, standing_change=2)
        from game.models.combat import CombatEncounter

        CombatEncounter.objects.create(
            scene=self.fight,
            enemy=self.enemy,
            victory_scene=self.end,
            defeat_scene=self.end,
            victory_arrival_flavor="Win flavor",
            defeat_arrival_flavor="Lose flavor",
        )

    def test_build_payload_matches_import_schema(self):
        payload = build_quest_export_payload("export-one")
        self.assertIn("quest", payload)
        self.assertIn("scenes", payload)
        self.assertEqual(payload["quest"]["key"], "export-one")
        self.assertEqual(payload["quest"]["entrance_scene"], "export-one__start")
        self.assertEqual(default_quest_export_path(payload), Path("yaml_files/quests/intro/export-one.yaml"))

        fight = next(scene for scene in payload["scenes"] if scene["key"] == "export-one__fight")
        self.assertIn("arrival", fight)
        self.assertIn("combat_encounter", fight)
        self.assertEqual(fight["combat_encounter"]["enemy"], "terrell")
        self.assertEqual(fight["arrival"]["discover_territory"], "the_docks")
        self.assertEqual(fight["arrival"]["gang_standing_changes"][0]["gang"], "dockers")

    def test_export_command_writes_yaml_and_round_trips(self):
        with TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir) / "export-one.yaml"
            call_command("export_quest", "export-one", "--out", str(out_path))
            self.assertTrue(out_path.exists())
            exported = yaml.safe_load(out_path.read_text(encoding="utf-8"))
            self.assertEqual(exported["quest"]["key"], "export-one")

            call_command("import_quest", str(out_path))
            self.assertTrue(Quest.objects.filter(key="export-one").exists())
            self.assertTrue(Scene.objects.filter(key="export-one__fight").exists())

    def test_export_command_errors_for_unknown_quest(self):
        with self.assertRaises(CommandError):
            call_command("export_quest", "missing-quest")
