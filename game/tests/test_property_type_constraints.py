from django.core.exceptions import ValidationError
from django.test import TestCase

from game.models.property import Property


class PropertyTypeConstraintTest(TestCase):
    def test_property_type_territory_is_rejected(self):
        prop = Property(
            key="legacy-territory",
            name="Legacy Territory",
            property_type="territory",
        )
        with self.assertRaises(ValidationError):
            prop.full_clean()
