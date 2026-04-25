def has_flag(session, flag: str) -> bool:
    """Return True when a named session flag is currently set."""
    return bool(session.flags.get(flag))

def set_flag(session, flag: str) -> None:
    """Set a named session flag to True and persist the session flags map."""
    session.flags[flag] = True
    session.save(update_fields=['flags'])

def clear_flag(session, flag: str) -> None:
    """Remove a named session flag if present and persist the session flags map."""
    session.flags.pop(flag, None)
    session.save(update_fields=['flags'])
