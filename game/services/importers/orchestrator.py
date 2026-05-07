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
from .types import ImportResult

TYPE_ORDER = ["items", "enemies_contacts", "hubs", "world", "quest"]


def detect_import_type(data: dict) -> str | None:
    keys = set(data.keys())
    if "quest" in keys:
        return "quest"
    if "hubs" in keys:
        return "hubs"
    if "items" in keys:
        return "items"
    if keys & {"enemies", "contacts"}:
        return "enemies_contacts"
    if keys & {"gangs", "properties", "territories"}:
        return "world"
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


def _import_typed_data(import_type: str, data: dict) -> ImportResult:
    if import_type == "items":
        return import_items_data(data)
    if import_type == "enemies_contacts":
        return import_enemies_and_contacts_data(data)
    if import_type == "hubs":
        return import_hubs_data(data)
    if import_type == "quest":
        return import_quest_data(data)
    if import_type == "world":
        return import_world_data(data)
    raise CommandError(f"Unsupported import type: {import_type}")


def import_all_sources(paths: list[str]) -> tuple[ImportResult, dict[str, list[tuple[str, dict]]]]:
    buckets: dict[str, list[tuple[str, dict]]] = {key: [] for key in TYPE_ORDER}
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
    return result, buckets


def import_single_source(path: str, expected_type: str) -> ImportResult:
    data = load_yaml(path)
    detected = detect_import_type(data)
    if detected != expected_type:
        raise CommandError(f"Expected import type '{expected_type}' but found '{detected or 'unknown'}'")
    with transaction.atomic():
        return _import_typed_data(expected_type, data)
