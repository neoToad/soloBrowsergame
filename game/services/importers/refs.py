from __future__ import annotations

from django.db.models import Model

from game.models.world import Scene

from .types import ImportResult


def get_by_key_or_warn(model: type[Model], key: str | None, result: ImportResult) -> Model | None:
    if not key:
        return None
    try:
        return model.objects.get(key=key)
    except model.DoesNotExist:
        result.warn(f"{model.__name__} '{key}' not found in DB; FK set to null")
        return None


def resolve_scene(
    key: str | None,
    scene_map: dict[str, Scene],
    result: ImportResult,
) -> Scene | None:
    if key is None:
        return None
    if key in scene_map:
        return scene_map[key]
    try:
        return Scene.objects.get(key=key)
    except Scene.DoesNotExist:
        result.warn(f"Scene '{key}' not found in DB; FK set to null")
        return None
