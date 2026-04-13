def has_flag(session, flag: str) -> bool:
    return bool(session.flags.get(flag))

def set_flag(session, flag: str) -> None:
    session.flags[flag] = True
    session.save(update_fields=['flags'])

def clear_flag(session, flag: str) -> None:
    session.flags.pop(flag, None)
    session.save(update_fields=['flags'])
