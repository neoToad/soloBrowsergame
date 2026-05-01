from django.test import Client, TestCase

from django.db import IntegrityError

from game.models import PlayerDiscoveredTerritory, PlayerTerritory, Scene, Territory
from game.tests.factories import bootstrap_game_session


class TerritoryModelsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.session = bootstrap_game_session(self.client)

    def test_create_territory_with_income_and_resolution_scene(self):
        resolution_scene = Scene.objects.create(
            key="territory__resolution",
            title="Territory Resolution",
            body="",
            scene_type="normal",
        )

        territory = Territory.objects.create(
            key="dockside",
            name="Dockside",
            description="Waterfront district",
            cash_per_turn=15,
            heat_per_turn=2,
            rep_per_turn=3,
            is_contestable=True,
            resolution_scene=resolution_scene,
        )

        fetched = Territory.objects.get(pk=territory.pk)
        self.assertEqual(fetched.key, "dockside")
        self.assertEqual(fetched.cash_per_turn, 15)
        self.assertEqual(fetched.resolution_scene, resolution_scene)

    def test_create_player_territory_and_query_by_session(self):
        territory = Territory.objects.create(key="midtown", name="Midtown")
        player_territory = PlayerTerritory.objects.create(
            session=self.session,
            territory=territory,
            is_contested=False,
        )

        self.assertTrue(
            PlayerTerritory.objects.filter(
                pk=player_territory.pk,
                session=self.session,
                territory=territory,
            ).exists()
        )
        self.assertEqual(self.session.territories.count(), 1)

    def test_player_discovered_territory_is_unique_per_session_territory(self):
        territory = Territory.objects.create(key="north-end", name="North End")
        PlayerDiscoveredTerritory.objects.create(session=self.session, territory=territory)

        with self.assertRaises(IntegrityError):
            PlayerDiscoveredTerritory.objects.create(session=self.session, territory=territory)
