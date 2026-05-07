from __future__ import annotations

import os
from pathlib import Path

import yaml
from django.core.management import CommandError
from django.db import transaction

from .enemies_contacts import import_enemies_and_contacts_data
from .hubs import import_hubs_data
from .items import import_items_data
from .quests import import_quest_data
from .world import import_world_data
from .types import ImportResult, ImportType

TYPE_ORDER = [
    ImportType.ITEMS,
    ImportType.ENEMIES_CONTACTS,
    ImportType.HUBS,
    ImportType.WORLD,
    ImportType.QUEST,
]

IMPORT_HANDLERS = {
    ImportType.ITEMS: import_items_data,
    ImportType.ENEMIES_CONTACTS: import_enemies_and_contacts_data,
    ImportType.HUBS: import_hubs_data,
    ImportType.WORLD: import_world_data,
    ImportType.QUEST: import_quest_data,
}


def detect_import_type(data: dict) -> ImportType | None:
    keys = set(data.keys())
    if "quest" in keys:
        return ImportType.QUEST
    if "hubs" in keys:
        return ImportType.HUBS
    if "items" in keys:
        return ImportType.ITEMS
    if keys & {"enemies", "contacts"}:
        return ImportType.ENEMIES_CONTACTS
    if keys & {"gangs", "properties", "territories"}:
        return ImportType.WORLD
    return None


def load_yaml(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise CommandError(f"YAML root must be a mapping: {path}")
    return data


def discover_yaml_files(paths: list[str]) -> list[str]:
    files: list[str] = []
    for path in paths:
        if os.path.isdir(path):
            for root, _, filenames in os.walk(path):
                for filename in filenames:
                    if filename.endswith(".yaml") or filename.endswith(".yml"):
                        files.append(os.path.join(root, filename))
        elif os.path.isfile(path):
            files.append(path)
        else:
            raise CommandError(f"Path not found: {path}")
    return files


def _import_typed_data(import_type: ImportType, data: dict) -> ImportResult:
    handler = IMPORT_HANDLERS.get(import_type)
    if handler is None:
        raise CommandError(f"Unsupported import type: {import_type.value}")
    return handler(data)


def import_all_sources(paths: list[str]) -> tuple[ImportResult, dict[str, list[tuple[str, dict]]]]:
    buckets: dict[ImportType, list[tuple[str, dict]]] = {key: [] for key in TYPE_ORDER}
    for file_path in discover_yaml_files(paths):
        data = load_yaml(file_path)
        import_type = detect_import_type(data)
        if import_type is None:
            continue
        buckets[import_type].append((file_path, data))

    result = ImportResult()
    with transaction.atomic():
        for import_type in TYPE_ORDER:
            for _, data in buckets[import_type]:
                result.merge(_import_typed_data(import_type, data))
    return result, {key.value: value for key, value in buckets.items()}


def _coerce_import_type(import_type: str | ImportType) -> ImportType:
    if isinstance(import_type, ImportType):
        return import_type
    try:
        return ImportType(import_type)
    except ValueError as exc:
        raise CommandError(f"Unsupported import type: {import_type}") from exc


def import_single_source(path: str, expected_type: str | ImportType) -> ImportResult:
    data = load_yaml(path)
    detected = detect_import_type(data)
    expected = _coerce_import_type(expected_type)
    if detected != expected:
        raise CommandError(f"Expected import type '{expected.value}' but found '{detected.value if detected else 'unknown'}'")
    with transaction.atomic():
        return _import_typed_data(expected, data)
