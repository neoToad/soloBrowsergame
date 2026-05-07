from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase
from django.urls import reverse

from game.tests.factories import ItemFactory, bootstrap_game_session


class UseItemTest(TestCase):
    def setUp(self):
        from game.models import Item, PlayerInventory

        self.client = Client()
        self.session = bootstrap_game_session(self.client)
        self.stats = self.session.stats
        self.heal_potion = Item.objects.create(
            key="test_potion",
            name="Test Potion",
            description="Heals you.",
            is_consumable=True,
            effect_type="heal_hp",
            effect_value=10,
        )
        self.inventory_item = PlayerInventory.objects.create(
            session=self.session, item=self.heal_potion, quantity=1
        )

    def test_use_item_success(self):
        from game.models import PlayerInventory

        self.stats.hp = self.stats.max_hp - 5
        self.stats.save()

        response = self.client.post(
            reverse("use_item", kwargs={"item_id": self.heal_potion.pk}),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.stats.refresh_from_db()
        self.assertEqual(self.stats.hp, self.stats.max_hp)
        self.assertFalse(
            PlayerInventory.objects.filter(session=self.session, item=self.heal_potion).exists()
        )

    def test_use_item_not_in_inventory(self):
        self.inventory_item.delete()

        response = self.client.post(
            reverse("use_item", kwargs={"item_id": self.heal_potion.pk}),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 400)

    def test_use_item_rejects_get_with_405(self):
        response = self.client.get(
            reverse("use_item", kwargs={"item_id": self.heal_potion.pk}),
        )

        self.assertEqual(response.status_code, 405)


class InventoryServiceTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.session = bootstrap_game_session(self.client)
        self.stats = self.session.stats

    def test_use_item_add_stat_effect_increases_stat_and_consumes_item(self):
        from game.models import PlayerInventory
        from game.services.inventory import apply_item_effect

        item = ItemFactory(
            key="inv__add_str",
            name="Strength Tonic",
            is_consumable=True,
            effect_type="add_stat",
            effect_stat="strength",
            effect_value=2,
        )
        pi = PlayerInventory.objects.create(session=self.session, item=item, quantity=1)
        inventory = {item.id: pi}
        original_str = self.stats.strength

        apply_item_effect(self.session, self.stats, inventory, item)

        self.stats.refresh_from_db()
        self.assertEqual(self.stats.strength, original_str + 2)
        self.assertFalse(PlayerInventory.objects.filter(session=self.session, item=item).exists())

    def test_use_item_add_stat_effect_ignores_invalid_effect_stat(self):
        from game.models import PlayerInventory
        from game.services.inventory import apply_item_effect

        item = ItemFactory(
            key="inv__bad_add_stat",
            name="Glitched Tonic",
            is_consumable=True,
            effect_type="add_stat",
            effect_stat="luck",
            effect_value=5,
        )
        pi = PlayerInventory.objects.create(session=self.session, item=item, quantity=1)
        inventory = {item.id: pi}
        original_str = self.stats.strength

        apply_item_effect(self.session, self.stats, inventory, item)

        self.stats.refresh_from_db()
        self.assertEqual(self.stats.strength, original_str)
        self.assertFalse(PlayerInventory.objects.filter(session=self.session, item=item).exists())

    def test_consume_item_decrements_quantity_without_deleting_when_qty_gt_1(self):
        from game.models import PlayerInventory
        from game.services.inventory import consume_item

        item = ItemFactory(key="inv__multi", name="Multi Item")
        pi = PlayerInventory.objects.create(session=self.session, item=item, quantity=2)
        inventory = {item.id: pi}

        consume_item(self.session, item, inventory)

        pi.refresh_from_db()
        self.assertEqual(pi.quantity, 1)

    def test_award_scene_items_respects_award_once_flag(self):
        from game.models import PlayerInventory
        from game.models.world import SceneItem
        from game.services.inventory import award_scene_items

        scene = self.session.current_scene
        item = ItemFactory(key="inv__award_once", name="Once Item")
        SceneItem.objects.create(scene=scene, item=item, quantity=1, award_once=True)

        inventory = {}
        award_scene_items(self.session, scene, inventory)
        award_scene_items(self.session, scene, inventory)

        pi = PlayerInventory.objects.get(session=self.session, item=item)
        self.assertEqual(pi.quantity, 1)

    def test_award_scene_contacts_gain_and_lose(self):
        from game.models.player import PlayerContact
        from game.models.world import Contact, SceneContact
        from game.services.inventory import award_scene_contacts

        scene = self.session.current_scene
        gained = Contact.objects.create(key="inv__c_gain", name="Gained Contact", description="")
        lost = Contact.objects.create(key="inv__c_lose", name="Lost Contact", description="")
        SceneContact.objects.create(scene=scene, contact=gained, action="gain", award_once=False)
        SceneContact.objects.create(scene=scene, contact=lost, action="lose", award_once=False)

        existing_pc = PlayerContact.objects.create(session=self.session, contact=lost)
        contacts = {lost.id: existing_pc}

        awarded, removed = award_scene_contacts(self.session, scene, contacts)

        self.assertEqual([c.id for c in awarded], [gained.id])
        self.assertEqual([c.id for c in removed], [lost.id])
        self.assertTrue(PlayerContact.objects.filter(session=self.session, contact=gained).exists())
        self.assertFalse(PlayerContact.objects.filter(session=self.session, contact=lost).exists())

    def test_award_scene_discovered_territories_adds_receive_and_lose_targets(self):
        from game.models.property import PlayerDiscoveredTerritory, Territory
        from game.services.inventory import award_scene_discovered_territories, get_discovered_territories

        scene = self.session.current_scene
        gain_territory = Territory.objects.create(key="inv__gain_t", name="Gain Territory")
        lose_territory = Territory.objects.create(key="inv__lose_t", name="Lose Territory")
        discover_territory = Territory.objects.create(key="inv__discover_t", name="Discover Territory")
        scene.receive_territory = gain_territory
        scene.lose_territory = lose_territory
        scene.discover_territory = discover_territory
        scene.save(update_fields=["receive_territory", "lose_territory", "discover_territory"])

        discovered = get_discovered_territories(self.session)
        newly_discovered = award_scene_discovered_territories(self.session, scene, discovered)

        self.assertEqual(
            {t.id for t in newly_discovered},
            {gain_territory.id, lose_territory.id, discover_territory.id},
        )
        self.assertTrue(
            PlayerDiscoveredTerritory.objects.filter(session=self.session, territory=gain_territory).exists()
        )
        self.assertTrue(
            PlayerDiscoveredTerritory.objects.filter(session=self.session, territory=lose_territory).exists()
        )
        self.assertTrue(
            PlayerDiscoveredTerritory.objects.filter(session=self.session, territory=discover_territory).exists()
        )

    def test_apply_scene_gang_standing_changes_updates_player_standing(self):
        from game.models.player import PlayerGangStanding
        from game.models.world import Gang, SceneGangStanding
        from game.services.inventory import apply_scene_gang_standing_changes

        scene = self.session.current_scene
        gang_a = Gang.objects.create(key="inv__standing_a", name="Standing A")
        gang_b = Gang.objects.create(key="inv__standing_b", name="Standing B")
        SceneGangStanding.objects.create(scene=scene, gang=gang_a, standing_change=4)
        SceneGangStanding.objects.create(scene=scene, gang=gang_b, standing_change=-1)

        applied = apply_scene_gang_standing_changes(self.session, scene)

        self.assertEqual(len(applied), 2)
        self.assertEqual(
            PlayerGangStanding.objects.get(session=self.session, gang=gang_a).standing,
            4,
        )
        self.assertEqual(
            PlayerGangStanding.objects.get(session=self.session, gang=gang_b).standing,
            -1,
        )


class EffectiveStatsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.session = bootstrap_game_session(self.client)

    def test_get_effective_stats_applies_passive_item_bonuses(self):
        from game.models import Item, PlayerInventory
        from game.services.inventory import get_player_inventory
        from game.utils import get_effective_stats

        stats = self.session.stats
        stats.strength = 8
        stats.agility = 7
        stats.save()

        str_item = Item.objects.create(
            key="phase6__str_charm",
            name="STR Charm",
            description="Passive strength bonus.",
            passive_stat="strength",
            passive_value=2,
        )
        agi_item = Item.objects.create(
            key="phase6__agi_charm",
            name="AGI Charm",
            description="Passive agility bonus.",
            passive_stat="agility",
            passive_value=3,
        )
        second_str_item = Item.objects.create(
            key="phase6__str_charm_2",
            name="STR Charm 2",
            description="Another passive strength bonus.",
            passive_stat="strength",
            passive_value=1,
        )
        PlayerInventory.objects.create(session=self.session, item=str_item, quantity=1)
        PlayerInventory.objects.create(session=self.session, item=agi_item, quantity=1)
        PlayerInventory.objects.create(session=self.session, item=second_str_item, quantity=1)

        inventory = get_player_inventory(self.session)
        effective = get_effective_stats(stats, inventory)

        self.assertEqual(effective.strength, 11)
        self.assertEqual(effective.agility, 10)
        self.assertEqual(effective.bonuses["strength"], 3)
        self.assertEqual(effective.bonuses["agility"], 3)

    def test_get_effective_stats_ignores_invalid_passive_stat_names(self):
        from game.models import Item, PlayerInventory
        from game.services.inventory import get_player_inventory
        from game.utils import get_effective_stats

        stats = self.session.stats
        invalid_item = Item.objects.create(
            key="phase6__bad_passive",
            name="Broken Charm",
            description="Legacy bad stat target.",
            passive_stat="luck",
            passive_value=10,
        )
        PlayerInventory.objects.create(session=self.session, item=invalid_item, quantity=1)

        inventory = get_player_inventory(self.session)
        effective = get_effective_stats(stats, inventory)

        self.assertNotIn("luck", effective.bonuses)
        self.assertEqual(effective.strength, stats.strength)

    def test_get_stat_bonus_breakdown_returns_itemized_sources(self):
        from game.models import Item, PlayerInventory
        from game.services.inventory import get_player_inventory
        from game.utils import get_stat_bonus_breakdown

        stats = self.session.stats
        stats.strength = 9
        stats.save()

        brass_knuckles = Item.objects.create(
            key="phase6__brass_knuckles",
            name="Brass Knuckles",
            description="Heavy knuckles.",
            passive_stat="strength",
            passive_value=2,
        )
        PlayerInventory.objects.create(session=self.session, item=brass_knuckles, quantity=1)

        inventory = get_player_inventory(self.session)
        breakdown = get_stat_bonus_breakdown(stats, inventory)

        self.assertEqual(breakdown["strength"]["base"], 9)
        self.assertEqual(breakdown["strength"]["total_bonus"], 2)
        self.assertEqual(breakdown["strength"]["total"], 11)
        self.assertEqual(len(breakdown["strength"]["sources"]), 1)
        self.assertEqual(breakdown["strength"]["sources"][0]["item_name"], "Brass Knuckles")
        self.assertEqual(breakdown["strength"]["sources"][0]["value"], 2)
        self.assertEqual(breakdown["agility"]["sources"], [])


class ItemValidationTest(TestCase):
    def test_item_clean_rejects_invalid_effect_stat(self):
        from game.models import Item

        item = Item(
            key="inv__invalid_effect",
            name="Invalid Effect",
            description="",
            effect_type="add_stat",
            effect_stat="luck",
            effect_value=1,
        )
        with self.assertRaisesMessage(ValidationError, "effect_stat"):
            item.full_clean()

    def test_item_clean_rejects_invalid_passive_stat(self):
        from game.models import Item

        item = Item(
            key="inv__invalid_passive",
            name="Invalid Passive",
            description="",
            passive_stat="luck",
            passive_value=1,
        )
        with self.assertRaisesMessage(ValidationError, "passive_stat"):
            item.full_clean()


class ItemImporterValidationTest(TestCase):
    def test_import_items_data_rejects_invalid_stat_targets(self):
        from game.services.importers.domain import import_items_data

        with self.assertRaises(CommandError):
            import_items_data({
                "items": [
                    {
                        "key": "inv__import_invalid",
                        "name": "Bad Import",
                        "description": "",
                        "effect_type": "add_stat",
                        "effect_stat": "luck",
                        "effect_value": 1,
                    }
                ]
            })


class ReportInvalidItemStatsCommandTest(TestCase):
    def test_report_invalid_item_stats_command_reports_bad_rows(self):
        from game.models import Item

        Item.objects.create(
            key="inv__report_bad",
            name="Bad Row",
            description="",
            passive_stat="luck",
            passive_value=1,
        )
        out = StringIO()
        call_command("report_invalid_item_stats", stdout=out)
        self.assertIn("inv__report_bad", out.getvalue())


class ContactsModalRenderTest(TestCase):
    def setUp(self):
        from game.models.player import PlayerContact
        from game.models.world import Contact

        self.client = Client()
        self.session = bootstrap_game_session(self.client)
        self.contact = Contact.objects.create(
            key="inv__modal_contact",
            name="Wire",
            description="Knows who is moving product tonight.",
        )
        self.contact_no_desc = Contact.objects.create(
            key="inv__modal_contact_blank",
            name="Mute",
            description="",
        )
        PlayerContact.objects.create(session=self.session, contact=self.contact)
        PlayerContact.objects.create(session=self.session, contact=self.contact_no_desc)

    def test_contacts_render_as_clickable_buttons_with_dialogs(self):
        response = self.client.get(
            reverse("scene_detail", kwargs={"scene_key": self.session.current_scene.key})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="item-name-btn"', count=2)
        self.assertContains(response, f'id="contact-modal-{self.contact.id}"')
        self.assertContains(response, self.contact.description)

    def test_contact_modal_uses_fallback_when_description_missing(self):
        response = self.client.get(
            reverse("scene_detail", kwargs={"scene_key": self.session.current_scene.key})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'id="contact-modal-{self.contact_no_desc.id}"')
        self.assertContains(response, "No intel yet.")


class StatModalRenderTest(TestCase):
    def setUp(self):
        from game.models import PlayerInventory

        self.client = Client()
        self.session = bootstrap_game_session(self.client)
        self.session.stats.strength = 9
        self.session.stats.save(update_fields=["strength"])
        brass_knuckles = ItemFactory(
            key="inv__stat_modal_brass",
            name="Brass Knuckles",
            passive_stat="strength",
            passive_value=2,
        )
        PlayerInventory.objects.create(session=self.session, item=brass_knuckles, quantity=1)

    def test_stat_modal_renders_itemized_bonus_breakdown(self):
        response = self.client.get(
            reverse("scene_detail", kwargs={"scene_key": self.session.current_scene.key})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="stat-modal-strength"')
        self.assertContains(response, "Base 9")
        self.assertContains(response, "Brass Knuckles +2")
        self.assertContains(response, "Total 11")


class PropertiesModalRenderTest(TestCase):
    def setUp(self):
        from game.models.property import PlayerProperty, Property

        self.client = Client()
        self.session = bootstrap_game_session(self.client)
        self.property_with_desc = Property.objects.create(
            key="inv__prop_modal_desc",
            name="Ash Street Garage",
            description="A quiet place to stash gear and lay low.",
            property_type="business",
        )
        self.property_blank_desc = Property.objects.create(
            key="inv__prop_modal_blank",
            name="Burner Flat",
            description="",
            property_type="safehouse",
        )
        PlayerProperty.objects.create(session=self.session, property=self.property_with_desc)
        PlayerProperty.objects.create(session=self.session, property=self.property_blank_desc)

    def test_properties_render_as_clickable_buttons_with_dialogs(self):
        response = self.client.get(
            reverse("scene_detail", kwargs={"scene_key": self.session.current_scene.key})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'id="property-modal-{self.property_with_desc.id}"')
        self.assertContains(response, self.property_with_desc.description)
        self.assertContains(response, f'id="property-modal-{self.property_blank_desc.id}"')
        self.assertContains(response, "No intel yet.")

