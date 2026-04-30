from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class TerritoryDataMigrationTest(TransactionTestCase):
    migrate_from = ("game", "0056_scene_receive_territory_scene_lose_territory")
    migrate_to = ("game", "0057_migrate_territory_data_from_property")

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])
        old_apps = self.executor.loader.project_state([self.migrate_from]).apps

        GameSession = old_apps.get_model("game", "GameSession")
        Scene = old_apps.get_model("game", "Scene")
        Property = old_apps.get_model("game", "Property")
        PlayerProperty = old_apps.get_model("game", "PlayerProperty")

        session = GameSession.objects.create(session_key="migration-test-session")
        territory_resolution_scene = Scene.objects.create(
            key="migration__territory_resolution",
            title="Territory Resolution",
            body="",
            scene_type="normal",
        )
        regular_resolution_scene = Scene.objects.create(
            key="migration__regular_resolution",
            title="Regular Resolution",
            body="",
            scene_type="normal",
        )

        territory_property = Property.objects.create(
            key="old-docks",
            name="Old Docks",
            description="Legacy territory property",
            property_type="territory",
            cash_per_turn=10,
            heat_per_turn=2,
            rep_per_turn=1,
            is_contestable=True,
            resolution_scene_id=territory_resolution_scene.id,
        )
        regular_property = Property.objects.create(
            key="laundromat",
            name="Laundromat",
            property_type="business",
            resolution_scene_id=regular_resolution_scene.id,
        )

        PlayerProperty.objects.create(
            session_id=session.id,
            property_id=territory_property.id,
            is_contested=True,
        )
        PlayerProperty.objects.create(
            session_id=session.id,
            property_id=regular_property.id,
            is_contested=False,
        )

        Scene.objects.create(
            key="migration__receive_territory_property",
            title="Receive Territory Property",
            body="",
            scene_type="normal",
            receive_property_id=territory_property.id,
        )
        Scene.objects.create(
            key="migration__lose_territory_property",
            title="Lose Territory Property",
            body="",
            scene_type="normal",
            lose_property_id=territory_property.id,
        )
        Scene.objects.create(
            key="migration__receive_regular_property",
            title="Receive Regular Property",
            body="",
            scene_type="normal",
            receive_property_id=regular_property.id,
        )

        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_to])
        self.apps = self.executor.loader.project_state([self.migrate_to]).apps

    def test_migrates_territory_rows_player_ownership_and_scene_mappings(self):
        Territory = self.apps.get_model("game", "Territory")
        PlayerTerritory = self.apps.get_model("game", "PlayerTerritory")
        Scene = self.apps.get_model("game", "Scene")

        self.assertEqual(Territory.objects.count(), 1)
        territory = Territory.objects.get(key="old-docks")
        self.assertEqual(territory.name, "Old Docks")
        self.assertEqual(territory.cash_per_turn, 10)
        self.assertEqual(territory.heat_per_turn, 2)
        self.assertEqual(territory.rep_per_turn, 1)
        self.assertTrue(territory.is_contestable)

        self.assertEqual(PlayerTerritory.objects.count(), 1)
        player_territory = PlayerTerritory.objects.get(territory_id=territory.id)
        self.assertTrue(player_territory.is_contested)

        receive_scene = Scene.objects.get(key="migration__receive_territory_property")
        lose_scene = Scene.objects.get(key="migration__lose_territory_property")
        regular_scene = Scene.objects.get(key="migration__receive_regular_property")
        self.assertEqual(receive_scene.receive_territory_id, territory.id)
        self.assertEqual(lose_scene.lose_territory_id, territory.id)
        self.assertIsNone(regular_scene.receive_territory_id)
