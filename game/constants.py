HUB_START_SCENE_KEY = 'hub__apartment'
SESSION_KEY = 'game_session_id'

# Canonical stat field names used in DB, services, requests, and fixtures.
STAT_DISPLAY_NAMES = {
    'strength': 'muscle',
    'agility': 'reflexes',
    'intellect': 'cunning',
    'charisma': 'nerve',
}

STAT_FIELDS = tuple(STAT_DISPLAY_NAMES.keys())

# Legacy aliases kept for backward compatibility with older tests/imports.
STAT_DB_NAMES = {display: db for db, display in STAT_DISPLAY_NAMES.items()}
STAT_FIELD_MAP = STAT_DB_NAMES

USE_ITEM_FLAVOR = {
    'heal_hp':  "The edges go soft. You keep moving.",
    'add_stat': "You feel sharper. More focused.",
}

LEVEL_UP_HP_RESTORE = 5
