import factory

from game.models import Item

from .base import BaseFactory


class ItemFactory(BaseFactory):
    class Meta:
        model = Item

    key = factory.Sequence(lambda n: f"item-{n}")
    name = factory.Sequence(lambda n: f"Test Item {n}")
    description = ""
    is_consumable = False
    effect_type = ""
    effect_stat = ""
    effect_value = 0
    passive_stat = ""
    passive_value = 0

    class Params:
        consumable = factory.Trait(is_consumable=True)
        healing = factory.Trait(
            is_consumable=True,
            effect_type="heal_hp",
            effect_value=5,
        )
        strength_boost = factory.Trait(
            effect_type="add_stat",
            effect_stat="strength",
            effect_value=1,
        )
