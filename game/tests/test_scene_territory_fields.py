from django.core.exceptions import ValidationError
from django.test import TestCase

from game.models import Scene, Territory


class SceneTerritoryFieldsTest(TestCase):
    def test_scene_can_store_receive_and_lose_territory(self):
        gained = Territory.objects.create(key="uptown", name="Uptown")
        lost = Territory.objects.create(key="downtown", name="Downtown")

        scene = Scene.objects.create(
            key="territory__arrival",
            title="Territory Arrival",
            body="",
            scene_type="normal",
            receive_territory=gained,
            lose_territory=lost,
        )

        scene.refresh_from_db()
        self.assertEqual(scene.receive_territory, gained)
        self.assertEqual(scene.lose_territory, lost)

    def test_clean_rejects_receive_property_and_receive_territory_together(self):
        territory = Territory.objects.create(key="harbor", name="Harbor")
        from game.models import Property

        prop = Property.objects.create(key="harbor-shop", name="Harbor Shop", property_type="business")
        scene = Scene(
            key="territory__conflict_receive",
            title="Conflict Receive",
            body="",
            scene_type="normal",
            receive_property=prop,
            receive_territory=territory,
        )

        with self.assertRaises(ValidationError):
            scene.full_clean()

    def test_clean_rejects_lose_property_and_lose_territory_together(self):
        territory = Territory.objects.create(key="old-town", name="Old Town")
        from game.models import Property

        prop = Property.objects.create(key="old-town-shop", name="Old Town Shop", property_type="business")
        scene = Scene(
            key="territory__conflict_lose",
            title="Conflict Lose",
            body="",
            scene_type="normal",
            lose_property=prop,
            lose_territory=territory,
        )

        with self.assertRaises(ValidationError):
            scene.full_clean()
