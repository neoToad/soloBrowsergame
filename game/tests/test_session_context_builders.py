from django.test import Client, TestCase

from game.models import Contact, Gang, Scene
from game.models.player import PlayerContact, PlayerGangStanding
from game.models.property import (
    PlayerDiscoveredTerritory,
    PlayerProperty,
    PlayerTerritory,
    Property,
    Territory,
)
from game.services.inventory import get_player_inventory
from game.services.session import (
    build_core_context,
    build_hub_context,
    build_social_context,
    get_completed_map,
)
from game.tests.factories import bootstrap_game_session
from game.utils import get_effective_stats


class SessionContextProvidersTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.session = bootstrap_game_session(self.client)
        self.inventory = get_player_inventory(self.session)
        self.completed_map = get_completed_map(self.session)
        self.effective_stats = get_effective_stats(self.session.stats, self.inventory)

    def test_build_core_context_contains_expected_keys_and_values(self):
        scene = self.session.current_scene
        context = build_core_context(
            self.session,
            scene,
            self.session.stats,
            self.effective_stats,
            self.inventory,
            self.completed_map,
            combat_state=None,
        )

        expected_keys = {
            "session",
            "scene",
            "choices",
            "stats",
            "effective_stats",
            "stat_bonuses",
            "stat_bonus_breakdown",
            "inventory",
            "logs",
            "oob",
            "combat_state",
            "turn_summary",
            "roll_result",
            "damage_result",
        }
        self.assertTrue(expected_keys.issubset(set(context.keys())))
        self.assertIs(context["session"], self.session)
        self.assertIs(context["scene"], scene)
        self.assertTrue(context["oob"])

    def test_build_hub_context_sets_notice_board_for_hub_only(self):
        hub_scene = self.session.current_scene
        non_hub_scene = Scene.objects.create(
            key="context__non_hub",
            title="Non Hub",
            body="",
            scene_type="normal",
        )

        hub_context = build_hub_context(
            self.session,
            hub_scene,
            self.effective_stats,
            self.inventory,
            self.completed_map,
        )
        non_hub_context = build_hub_context(
            self.session,
            non_hub_scene,
            self.effective_stats,
            self.inventory,
            self.completed_map,
        )

        self.assertIn("notice_board", hub_context)
        self.assertIsNotNone(hub_context["notice_board"])
        self.assertEqual(set(hub_context["notice_board"].keys()), {"available", "locked", "completed"})
        self.assertIsNone(non_hub_context["notice_board"])

    def test_build_social_context_exposes_representative_social_and_property_values(self):
        territory = Territory.objects.create(key="ctx-territory", name="Ctx Territory")
        hidden_territory = Territory.objects.create(key="ctx-hidden", name="Ctx Hidden")
        prop = Property.objects.create(key="ctx-prop", name="Ctx Property", property_type="business")
        contact = Contact.objects.create(key="ctx-contact", name="Ctx Contact")
        gang = Gang.objects.create(key="ctx-gang", name="Ctx Gang")

        PlayerProperty.objects.create(session=self.session, property=prop)
        PlayerDiscoveredTerritory.objects.create(session=self.session, territory=territory)
        PlayerTerritory.objects.create(session=self.session, territory=territory)
        PlayerContact.objects.create(session=self.session, contact=contact)
        PlayerGangStanding.objects.create(session=self.session, gang=gang, standing=2)

        context = build_social_context(self.session)

        self.assertEqual(list(context["player_properties"])[0].property_id, prop.id)
        self.assertEqual(list(context["visible_territories"]), [territory])
        self.assertNotIn(hidden_territory, list(context["visible_territories"]))
        self.assertIn(territory.id, context["owned_territory_ids"])
        self.assertEqual(list(context["player_contacts"])[0].contact_id, contact.id)
        self.assertEqual(list(context["player_gang_standings"])[0].gang_id, gang.id)
