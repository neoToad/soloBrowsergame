"""Compatibility wrapper for legacy imports.

Importer implementations now live in per-domain modules:
- items.py
- enemies_contacts.py
- world.py
- hubs.py
- quests.py
"""

from .enemies_contacts import import_enemies_and_contacts_data
from .hubs import import_hubs_data
from .items import import_items_data
from .quests import import_quest_data
from .world import import_world_data

__all__ = [
    "import_items_data",
    "import_enemies_and_contacts_data",
    "import_world_data",
    "import_hubs_data",
    "import_quest_data",
]
