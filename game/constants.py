HUB_START_SCENE_KEY = 'hub__apartment'
SESSION_KEY = 'game_session_id'

STAT_DISPLAY_NAMES = {
    'strength': 'muscle',
    'agility': 'reflexes',
    'intellect': 'cunning',
    'charisma': 'nerve',
}

STAT_DB_NAMES = {display: db for db, display in STAT_DISPLAY_NAMES.items()}

# Backward-compatible alias. Use STAT_DB_NAMES for display -> DB lookups.
STAT_FIELD_MAP = STAT_DB_NAMES

USE_ITEM_FLAVOR = {
    'heal_hp':  "You take a pull from the flask. Steadier now.",
    'add_stat': "You feel sharper. More focused.",
}
