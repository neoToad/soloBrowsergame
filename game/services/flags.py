from __future__ import annotations

from enum import Enum
from typing import Iterable


class FlagKey(str, Enum):
    BEAT2_PENALTY = "beat2_penalty"


def has_flag(session, flag: str | FlagKey) -> bool:
    """Return True when a named session flag is currently set."""
    return bool(session.flags.get(_normalize(flag)))


def set_flag(session, flag: str | FlagKey) -> None:
    """Set a named session flag to True and persist the session flags map."""
    _update_flags(session, set_flags=(_normalize(flag),))


def clear_flag(session, flag: str | FlagKey) -> None:
    """Remove a named session flag if present and persist the session flags map."""
    _update_flags(session, clear_flags=(_normalize(flag),))


def approach_selected_flag(approach_key: str) -> str:
    return f"approach_{approach_key}"


def approach_failed_flag(approach_key: str) -> str:
    return f"{approach_selected_flag(approach_key)}_failed"


def clear_job_approach_flags(session, approach_keys: Iterable[str]) -> None:
    clear_flags = [FlagKey.BEAT2_PENALTY.value]
    for key in approach_keys:
        clear_flags.append(approach_selected_flag(key))
        clear_flags.append(approach_failed_flag(key))
    _update_flags(session, clear_flags=clear_flags)


def set_approach_outcome(session, approach_key: str, *, success: bool) -> None:
    selected_flag = approach_selected_flag(approach_key)
    failed_flag = approach_failed_flag(approach_key)
    if success:
        _update_flags(
            session,
            set_flags=(selected_flag,),
            clear_flags=(failed_flag, FlagKey.BEAT2_PENALTY.value),
        )
    else:
        _update_flags(
            session,
            set_flags=(selected_flag, failed_flag, FlagKey.BEAT2_PENALTY.value),
        )


def _normalize(flag: str | FlagKey) -> str:
    value = flag.value if isinstance(flag, FlagKey) else str(flag)
    value = value.strip()
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
