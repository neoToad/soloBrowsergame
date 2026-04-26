from __future__ import annotations

from ..models.jobs import (
    RECON_TIER_HIGH,
    RECON_TIER_LOW,
    RECON_TIER_MID,
    RECON_TIER_MIN_CUNNING,
)
from ..utils import roll_d20, stat_modifier
from .jobs_common import JobRulesError, RECON_MODIFIERS, REWARD_BUCKETS, RollOutcome


def get_recon_tier(effective_stats) -> str:
    """Map effective intellect to the configured recon tier."""
    cunning_value = getattr(effective_stats, "intellect", 0)
    if cunning_value >= RECON_TIER_MIN_CUNNING[RECON_TIER_HIGH]:
        return RECON_TIER_HIGH
    if cunning_value >= RECON_TIER_MIN_CUNNING[RECON_TIER_MID]:
        return RECON_TIER_MID
    return RECON_TIER_LOW


def get_recon_modifiers(tier: str) -> dict[str, float | int]:
    """Return recon reward modifiers for a tier or raise JobRulesError for invalid input."""
    if tier not in RECON_MODIFIERS:
        raise JobRulesError(f"Unknown recon tier: {tier}")
    return dict(RECON_MODIFIERS[tier])


def _tier_rank(tier: str) -> int:
    if tier == RECON_TIER_LOW:
        return 0
    if tier == RECON_TIER_MID:
        return 1
    if tier == RECON_TIER_HIGH:
        return 2
    raise JobRulesError(f"Unknown tier: {tier}")


def _tiers_at_or_below(tier: str) -> list[str]:
    rank = _tier_rank(tier)
    out: list[str] = []
    for candidate in (RECON_TIER_LOW, RECON_TIER_MID, RECON_TIER_HIGH):
        if _tier_rank(candidate) <= rank:
            out.append(candidate)
    return out


def _available_approaches_for_tier(job, tier: str):
    return job.approaches.filter(
        min_recon_tier__in=_tiers_at_or_below(tier)
    ).order_by("order", "id")


def _roll_check(effective_stats, stat_name: str, dc: int) -> RollOutcome:
    stat_value = getattr(effective_stats, stat_name, 10)
    modifier = stat_modifier(stat_value)
    roll = roll_d20()
    total = roll + modifier
    return RollOutcome(
        roll=roll,
        modifier=modifier,
        total=total,
        dc=dc,
        stat=stat_name,
        success=total >= dc,
    )


def _reward_bucket_for_run_count(run_count: int) -> dict[str, float]:
    for bucket in REWARD_BUCKETS:
        max_runs = bucket["max_runs"]
        if run_count < bucket["min_runs"]:
            continue
        if max_runs is None or run_count <= max_runs:
            return bucket
    raise JobRulesError(f"No reward bucket configured for run count: {run_count}")
