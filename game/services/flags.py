from __future__ import annotations

from django.core.exceptions import ValidationError

from .flag_registry import FlagKey, normalize_flag_name


def has_flag(session, flag: str | FlagKey) -> bool:
    """Return True when a named session flag is currently set."""
    return bool(session.flags.get(_normalize(flag)))


def set_flag(session, flag: str | FlagKey) -> None:
    """Set a named session flag to True and persist the session flags map."""
    _update_flags(session, set_flags=(_normalize(flag),))


def clear_flag(session, flag: str | FlagKey) -> None:
    """Remove a named session flag if present and persist the session flags map."""
    _update_flags(session, clear_flags=(_normalize(flag),))


def _normalize(flag: str | FlagKey) -> str:
    try:
        value = normalize_flag_name(flag, allow_blank=False)
    except ValidationError as exc:
        raise ValueError(exc.messages[0]) from exc
    if not value:
        raise ValueError("Flag name must be non-empty.")
    return value


def _update_flags(session, *, set_flags: Iterable[str] = (), clear_flags: Iterable[str] = ()) -> None:
    flags = dict(session.flags or {})
    for flag in clear_flags:
        flags.pop(_normalize(flag), None)
    for flag in set_flags:
        flags[_normalize(flag)] = True
    session.flags = flags
    session.save(update_fields=["flags"])
