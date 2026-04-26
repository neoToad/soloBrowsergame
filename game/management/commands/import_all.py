import os
import yaml

from django.core.management import CommandError
from django.core.management.base import BaseCommand
from django.db import transaction

from game.models.world import Arc, Quest, Scene, Choice, Contact, SceneItem, SceneContact, Gang
from game.models.items import Item
from game.models.requirements import Requirement, RequirementGroup
from game.models.combat import CombatEncounter, Enemy
from game.models.property import Property


# Processing order matters: items and enemies/contacts must exist before hubs
# and quests reference them. World (gangs/properties) can run independently but
# properties may reference scenes, so run after hubs/quests when possible.
_TYPE_ORDER = ["items", "enemies_contacts", "hubs", "quest", "world"]


def _detect_type(data):
    keys = set(data.keys())
    if "quest" in keys:
        return "quest"
    if "hubs" in keys:
        return "hubs"
    if "items" in keys:
        return "items"
    if keys & {"enemies", "contacts"}:
        return "enemies_contacts"
    if keys & {"gangs", "properties"}:
        return "world"
    return None


class Command(BaseCommand):
    help = "Import all game data YAML files from a directory (or explicit file paths)"

    def add_arguments(self, parser):
        parser.add_argument(
            "paths",
            nargs="*",
            default=["yaml_files"],
            help="Directories or YAML files to import (default: yaml_files/)",
        )

    def handle(self, *args, **options):
        yaml_files = []
        for path in options["paths"]:
            if os.path.isdir(path):
                for root, _, filenames in os.walk(path):
                    for fn in filenames:
                        if fn.endswith(".yaml") or fn.endswith(".yml"):
                            yaml_files.append(os.path.join(root, fn))
            elif os.path.isfile(path):
                yaml_files.append(path)
            else:
                raise CommandError(f"Path not found: {path}")

        # Load and bucket by detected type
        buckets: dict[str, list] = {t: [] for t in _TYPE_ORDER}
        for fp in yaml_files:
            with open(fp, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                self.stdout.write(self.style.WARNING(f"  Skipping {fp} — not a mapping"))
                continue
            dtype = _detect_type(data)
            if dtype is None:
                self.stdout.write(self.style.WARNING(f"  Skipping {fp} — unrecognised top-level keys"))
                continue
            buckets[dtype].append((fp, data))

        total = sum(len(v) for v in buckets.values())
        self.stdout.write(f"Found {total} importable file(s)")

        with transaction.atomic():
            for fp, data in buckets["items"]:
                self.stdout.write(f"\n-- Items: {fp}")
                self._import_items(data)

            for fp, data in buckets["enemies_contacts"]:
                self.stdout.write(f"\n-- Enemies/Contacts: {fp}")
                self._import_enemies_and_contacts(data)

            for fp, data in buckets["hubs"]:
                self.stdout.write(f"\n-- Hubs: {fp}")
                self._import_hubs(data)

            for fp, data in buckets["quest"]:
                self.stdout.write(f"\n-- Quest: {fp}")
                self._import_quest(data)

            for fp, data in buckets["world"]:
                self.stdout.write(f"\n-- World: {fp}")
                self._import_world(data)

        self.stdout.write(self.style.SUCCESS("\nAll imports complete."))

    # ------------------------------------------------------------------
    # Items
    # ------------------------------------------------------------------

    def _import_items(self, data):
        items = data.get("items") or []
        for idata in items:
            obj, created = Item.objects.update_or_create(
                key=idata["key"],
                defaults={
                    "name": idata["name"],
                    "description": idata["description"],
                    "is_consumable": idata.get("is_consumable", False),
                    "effect_type": idata.get("effect_type") or "",
                    "effect_stat": idata.get("effect_stat") or "",
                    "effect_value": idata.get("effect_value", 0),
                    "passive_stat": idata.get("passive_stat") or "",
                    "passive_value": idata.get("passive_value", 0),
                },
            )
            self.stdout.write(f"  Item: {'Created' if created else 'Updated'} '{obj.key}'")
        self.stdout.write(f"  {len(items)} item(s) processed")

    # ------------------------------------------------------------------
    # Enemies & Contacts
    # ------------------------------------------------------------------

    def _import_enemies_and_contacts(self, data):
        enemies = data.get("enemies") or []
        for edata in enemies:
            obj, created = Enemy.objects.update_or_create(
                key=edata["key"],
                defaults={
                    "name": edata["name"],
                    "description": edata["description"],
                    "max_hp": edata.get("max_hp", 10),
                    "attack_modifier": edata.get("attack_modifier", 0),
                    "defense": edata.get("defense", 8),
                    "damage_min": edata.get("damage_min", 1),
                    "damage_max": edata.get("damage_max", 4),
                },
            )
            self.stdout.write(f"  Enemy: {'Created' if created else 'Updated'} '{obj.key}'")
        self.stdout.write(f"  {len(enemies)} enemy/enemies processed")

        contacts = data.get("contacts") or []
        for cdata in contacts:
            obj, created = Contact.objects.update_or_create(
                key=cdata["key"],
                defaults={
                    "name": cdata["name"],
                    "description": cdata.get("description", ""),
                },
            )
            self.stdout.write(f"  Contact: {'Created' if created else 'Updated'} '{obj.key}'")
        self.stdout.write(f"  {len(contacts)} contact(s) processed")

    # ------------------------------------------------------------------
    # Hubs
    # ------------------------------------------------------------------

    def _import_hubs(self, data):
        scene_map: dict[str, Scene] = {}
        hubs = data.get("hubs") or []

        for hdata in hubs:
            roll = hdata.get("roll", {}) or {}
            arrival = hdata.get("arrival", {}) or {}
            scene, created = Scene.objects.update_or_create(
                key=hdata["key"],
                defaults={
                    "scene_type": hdata["scene_type"],
                    "title": hdata["title"],
                    "body": hdata["body"],
                    "order": hdata.get("order", 0),
                    "requires_roll": roll.get("requires_roll", False),
                    "roll_stat": roll.get("roll_stat") or "",
                    "roll_difficulty": roll.get("roll_difficulty") or 10,
                    "ending_type": "",
                    "cash_change": arrival.get("cash_change", 0),
                    "rep_change": arrival.get("rep_change", 0),
                    "heat_change": arrival.get("heat_change", 0),
                    "consume_item": self._get_or_warn(Item, arrival.get("consume_item")),
                    "receive_property": None,
                    "lose_property": None,
                },
            )
            scene_map[scene.key] = scene
            self.stdout.write(f"  Scene: {'Created' if created else 'Updated'} '{scene.key}'")

        for hdata in hubs:
            scene_obj = scene_map[hdata["key"]]
            self._import_choices(hdata, scene_obj, scene_map)
            for choice_data in (hdata.get("choices") or []):
                choice_obj = Choice.objects.get(
                    scene=scene_obj,
                    label=choice_data["label"],
                    order=choice_data.get("order", 0),
                )
                groups = self._import_requirement_groups(choice_data.get("requirements") or [])
                choice_obj.requirements.set(groups)
            self._import_scene_items(hdata, scene_obj)
            self._import_scene_contacts(hdata, scene_obj)

        self.stdout.write(f"  {len(hubs)} hub scene(s) processed")

    # ------------------------------------------------------------------
    # Quest
    # ------------------------------------------------------------------

    def _import_quest(self, data):
        qdata = data["quest"]
        arc = None
        if qdata.get("arc"):
            arc = Arc.objects.get(key=qdata["arc"])

        quest, created = Quest.objects.update_or_create(
            key=qdata["key"],
            defaults={
                "title": qdata["title"],
                "description": qdata["description"],
                "is_repeatable": qdata.get("is_repeatable", False),
                "arc_order": qdata.get("arc_order", 0),
                "arc": arc,
                "entrance_scene": None,
            },
        )
        self.stdout.write(f"  Quest: {'Created' if created else 'Updated'} '{quest.key}'")

        scene_map: dict[str, Scene] = {}
        for sdata in data["scenes"]:
            roll = sdata.get("roll", {}) or {}
            ending = sdata.get("ending", {}) or {}
            arrival = sdata.get("arrival", {}) or {}
            ending_type = ending.get("ending_type") or sdata.get("ending_type") or ""
            if sdata.get("scene_type") == "ending" and not ending_type:
                raise CommandError(
                    f"Scene '{sdata['key']}' is scene_type='ending' but has no ending.ending_type value."
                )
            scene, created = Scene.objects.update_or_create(
                key=sdata["key"],
                defaults={
                    "quest": quest,
                    "scene_type": sdata["scene_type"],
                    "title": sdata["title"],
                    "body": sdata["body"],
                    "order": sdata.get("order", 0),
                    "requires_roll": roll.get("requires_roll", False),
                    "roll_stat": roll.get("roll_stat") or "",
                    "roll_difficulty": roll.get("roll_difficulty") or 10,
                    "ending_type": ending_type,
                    "cash_change": arrival.get("cash_change", sdata.get("cash_change", 0)),
                    "rep_change": arrival.get("rep_change", sdata.get("rep_change", 0)),
                    "heat_change": arrival.get("heat_change", sdata.get("heat_change", 0)),
                    "consume_item": self._get_or_warn(Item, arrival.get("consume_item")),
                    "receive_property": None,
                    "lose_property": None,
                },
            )
            scene_map[scene.key] = scene
            self.stdout.write(f"  Scene: {'Created' if created else 'Updated'} '{scene.key}'")

        quest.entrance_scene = scene_map[qdata["entrance_scene"]]
        quest.save()

        for sdata in data["scenes"]:
            scene_obj = scene_map[sdata["key"]]
            self._import_choices(sdata, scene_obj, scene_map)

        for sdata in data["scenes"]:
            scene_obj = scene_map[sdata["key"]]
            for choice_data in (sdata.get("choices") or []):
                choice_obj = Choice.objects.get(
                    scene=scene_obj,
                    label=choice_data["label"],
                    order=choice_data.get("order", 0),
                )
                groups = self._import_requirement_groups(choice_data.get("requirements") or [])
                choice_obj.requirements.set(groups)

        quest_groups = self._import_requirement_groups(qdata.get("requirements") or [])
        quest.requirements.set(quest_groups)

        for sdata in data["scenes"]:
            scene_obj = scene_map[sdata["key"]]
            self._import_scene_items(sdata, scene_obj)
            self._import_scene_contacts(sdata, scene_obj)
            self._import_combat_encounter(sdata, scene_obj, scene_map)

        Scene.objects.filter(quest=quest).exclude(key__in=scene_map).update(quest=None)
        hub_keys = qdata.get("hub_scenes") or []
        quest.hub_scenes.set(Scene.objects.filter(key__in=hub_keys))

        self.stdout.write(f"  {len(data['scenes'])} scene(s) processed")

    # ------------------------------------------------------------------
    # World (Gangs & Properties)
    # ------------------------------------------------------------------

    def _import_world(self, data):
        gangs = data.get("gangs") or []
        for gdata in gangs:
            obj, created = Gang.objects.update_or_create(
                key=gdata["key"],
                defaults={
                    "name": gdata["name"],
                    "description": gdata.get("description", ""),
                },
            )
            self.stdout.write(f"  Gang: {'Created' if created else 'Updated'} '{obj.key}'")
        self.stdout.write(f"  {len(gangs)} gang(s) processed")

        properties = data.get("properties") or []
        for pdata in properties:
            obj, created = Property.objects.update_or_create(
                name=pdata["name"],
                defaults={
                    "property_type": pdata["property_type"],
                    "cash_per_turn": pdata.get("cash_per_turn", 0),
                    "heat_per_turn": pdata.get("heat_per_turn", 0),
                    "rep_per_turn": pdata.get("rep_per_turn", 0),
                    "is_contestable": pdata.get("is_contestable", False),
                    "resolution_scene": self._get_or_warn(Scene, pdata.get("resolution_scene")),
                },
            )
            self.stdout.write(f"  Property: {'Created' if created else 'Updated'} '{obj.name}'")
        self.stdout.write(f"  {len(properties)} property/properties processed")

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _get_or_warn(self, model, key):
        if not key:
            return None
        try:
            return model.objects.get(key=key)
        except model.DoesNotExist:
            self.stdout.write(self.style.WARNING(f"  WARNING: {model.__name__} '{key}' not found in DB — FK set to null"))

    def _resolve_scene(self, key, scene_map):
        if key is None:
            return None
        if key in scene_map:
            return scene_map[key]
        try:
            return Scene.objects.get(key=key)
        except Scene.DoesNotExist:
            self.stdout.write(self.style.WARNING(f"  WARNING: scene '{key}' not found in DB — FK set to null"))

    def _import_choices(self, scene_data, scene_obj, scene_map):
        for choice in (scene_data.get("choices") or []):
            obj, _ = Choice.objects.update_or_create(
                scene=scene_obj,
                label=choice["label"],
                order=choice.get("order", 0),
                defaults={
                    "arrival_flavor":         choice.get("arrival_flavor") or "",
                    "failure_arrival_flavor": choice.get("failure_arrival_flavor") or "",
                    "set_flag_name":          choice.get("set_flag_name") or "",
                    "clear_flag_name":        choice.get("clear_flag_name") or "",
                    "target_scene":           self._resolve_scene(choice.get("target_scene"), scene_map),
                    "success_scene":          self._resolve_scene(choice.get("success_scene"), scene_map),
                    "failure_scene":          self._resolve_scene(choice.get("failure_scene"), scene_map),
                },
            )
            obj.requirements.clear()

    def _import_requirement_groups(self, groups_data):
        groups = []
        for gdata in (groups_data or []):
            group, _ = RequirementGroup.objects.get_or_create(label=gdata["label"])
            group.logic = gdata.get("logic", "all")
            group.save()
            group.requirements.clear()
            for cdata in (gdata.get("conditions") or []):
                req = Requirement.objects.create(
                    condition_type=cdata["condition_type"],
                    flag_name=cdata.get("flag_name") or "",
                    stat_name=cdata.get("stat_name") or "",
                    stat_value=cdata.get("stat_value") or 0,
                    required_ending_type=cdata.get("required_ending_type") or "",
                    required_item=self._get_or_warn(Item, cdata.get("required_item")),
                    required_quest=self._get_or_warn(Quest, cdata.get("required_quest")),
                    required_contact=self._get_or_warn(Contact, cdata.get("required_contact")),
                )
                group.requirements.add(req)
            groups.append(group)
        return groups

    def _import_scene_items(self, scene_data, scene_obj):
        SceneItem.objects.filter(scene=scene_obj).delete()
        for entry in (scene_data.get("scene_items") or scene_data.get("items") or []):
            SceneItem.objects.create(
                scene=scene_obj,
                item=self._get_or_warn(Item, entry["item"]),
                quantity=entry.get("quantity", 1),
                award_once=entry.get("award_once", True),
            )

    def _import_scene_contacts(self, scene_data, scene_obj):
        SceneContact.objects.filter(scene=scene_obj).delete()
        for entry in (scene_data.get("scene_contacts") or scene_data.get("contacts") or []):
            SceneContact.objects.create(
                scene=scene_obj,
                contact=self._get_or_warn(Contact, entry["contact"]),
                action=entry.get("action", "gain"),
                award_once=entry.get("award_once", True),
            )

    def _import_combat_encounter(self, scene_data, scene_obj, scene_map):
        if scene_data.get("scene_type") != "combat":
            return
        combat = scene_data.get("combat_encounter") or scene_data.get("combat") or {}
        enemy = self._get_or_warn(Enemy, combat.get("enemy"))
        if enemy is None:
            self.stdout.write(self.style.WARNING(f"  WARNING: skipping CombatEncounter for '{scene_obj.key}' — enemy not found"))
            return
        CombatEncounter.objects.update_or_create(
            scene=scene_obj,
            defaults={
                "enemy": enemy,
                "victory_scene": self._resolve_scene(combat.get("victory_scene"), scene_map),
                "defeat_scene":  self._resolve_scene(combat.get("defeat_scene"), scene_map),
                "victory_arrival_flavor": combat.get("victory_arrival_flavor") or "",
                "defeat_arrival_flavor":  combat.get("defeat_arrival_flavor") or "",
            },
        )