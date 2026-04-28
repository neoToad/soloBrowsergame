import factory
from factory.django import DjangoModelFactory


class BaseFactory(DjangoModelFactory):
    class Meta:
        abstract = True


def unique_slug(prefix: str) -> factory.Sequence:
    return factory.Sequence(lambda n: f"{prefix}-{n}")
