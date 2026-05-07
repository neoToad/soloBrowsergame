from dataclasses import dataclass, field
from enum import Enum


class ImportType(str, Enum):
    ITEMS = "items"
    ENEMIES_CONTACTS = "enemies_contacts"
    HUBS = "hubs"
    WORLD = "world"
    QUEST = "quest"


@dataclass
class ImportCounts:
    created: int = 0
    updated: int = 0
    deleted: int = 0


@dataclass
class ImportResult:
    counts: dict[str, ImportCounts] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def record_created(self, key: str) -> None:
        self.counts.setdefault(key, ImportCounts()).created += 1

    def record_updated(self, key: str) -> None:
        self.counts.setdefault(key, ImportCounts()).updated += 1

    def record_deleted(self, key: str, amount: int = 1) -> None:
        self.counts.setdefault(key, ImportCounts()).deleted += amount

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def merge(self, other: "ImportResult") -> None:
        for name, counts in other.counts.items():
            target = self.counts.setdefault(name, ImportCounts())
            target.created += counts.created
            target.updated += counts.updated
            target.deleted += counts.deleted
        self.warnings.extend(other.warnings)
