from django.test import Client, TestCase

from game.models import Scene
from game.services.inventory import get_player_inventory
from game.services.session import build_render_context, get_completed_map
from game.tests.factories import bootstrap_game_session
from game.utils import get_effective_stats


class SessionTerritoryContextTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.session = bootstrap_game_session(self.client)

    def test_render_context_uses_player_territory_for_owned_territory_ids(self):
        from game.models.property import PlayerProperty, PlayerTerritory, Property, Territory

        territory = Territory.objects.create(key="west-harbor", name="West Harbor")
        normal_property = Property.objects.create(
            key="bookmaker",
            name="Bookmaker",
            property_type="business",
        )
        PlayerProperty.objects.create(session=self.session, property=normal_property)
        PlayerTerritory.objects.create(session=self.session, territory=territory)

        scene = Scene.objects.create(
            key="context__territory",
            title="Context",
            body="",
            scene_type="normal",
        )
        inventory = get_player_inventory(self.session)
        completed_map = get_completed_map(self.session)
        effective_stats = get_effective_stats(self.session.stats, inventory)
        context = build_render_context(
            self.session,
            scene,
            self.session.stats,
            effective_stats,
            inventory,
            completed_map,
            combat_state=None,
        )

        self.assertEqual(list(context["all_territories"]), [territory])
        self.assertIn(territory.id, context["owned_territory_ids"])
        self.assertEqual(len(context["player_properties"]), 1)
        self.assertEqual(context["player_properties"][0].property_id, normal_property.id)
