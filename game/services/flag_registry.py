from __future__ import annotations

import re
from enum import Enum
from typing import Iterable

from django.core.exceptions import ValidationError


class FlagKey(str, Enum):
    BEAT2_PENALTY = "beat2_penalty"


# Existing authored story flags currently used by fixture content.
STORY_FLAG_KEYS = frozenset(
    {
        "box_busted",
        "box_clean_exit",
        "box_rough_exit",
        "debt_cased",
        "debt_defeat",
        "debt_neutral",
        "debt_victory",
        "fence_defeat",
        "fence_lockup_scouted",
        "fence_neutral",
        "fence_victory",
        "first_word_burned",
        "first_word_paid_in_full",
        "first_word_partial",
        "corkys_dealers_in",
        "corkys_sal_holds",
        "corkys_sal_caved",
        "corkys_read_room",
        "hunt_defeat",
        "hunt_victory",
        "phase6_secret",
        "test",
        "the_call_fought_out",
        "the_call_lost",
        "the_call_talked_out",
        "the_ride_straight",
        "the_ride_covered",
        "the_ride_lost",
        "morris_job_clean",
        "morris_job_hot",
    }
)

REGISTERED_FLAG_KEYS = frozenset({*STORY_FLAG_KEYS, *(key.value for key in FlagKey)})

_DYNAMIC_PATTERNS = (
    re.compile(r"^approach_[a-z0-9_]+(?:_failed)?$"),
    re.compile(r"^ran_[a-z0-9_]+_(?:3|5|10)x$"),
)


def normalize_flag_name(value: str | FlagKey | None, *, allow_blank: bool = True) -> str:
    if value is None:
        return ""
    normalized = value.value if isinstance(value, FlagKey) else str(value)
    normalized = normalized.strip()
    if not normalized and not allow_blank:
        raise ValidationError("Flag name must be non-empty.")
    return normalized


def is_valid_flag_name(value: str) -> bool:
    if value in REGISTERED_FLAG_KEYS:
        return True
    return any(pattern.fullmatch(value) for pattern in _DYNAMIC_PATTERNS)


def validate_flag_name(
    value: str | FlagKey | None,
    *,
    allow_blank: bool = True,
    field_label: str = "Flag",
    legacy_values: Iterable[str] = (),
) -> str:
    normalized = normalize_flag_name(value, allow_blank=allow_blank)
    if not normalized:
        return normalized
    if normalized in legacy_values:
        return normalized
    if is_valid_flag_name(normalized):
        return normalized
    raise ValidationError(
        f"{field_label} '{normalized}' is not in the flag registry. "
        "Use a registered key or a supported dynamic pattern "
        "('approach_<key>', 'approach_<key>_failed', 'ran_<job_key>_<3|5|10>x')."
    )
