from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from ..models import ContactJobOffer, Job, PlayerContactOfferState, PlayerJobState
from ..models.jobs import (
    RECON_TIER_HIGH,
    RECON_TIER_LOW,
    RECON_TIER_MID,
)
from .flags import FlagKey


RECON_MODIFIERS = {
    RECON_TIER_LOW: {
        "cash_multiplier": 0.9,
        "heat_flat": 1,
        "rep_flat": -1,
    },
    RECON_TIER_MID: {
        "cash_multiplier": 1.0,
        "heat_flat": 0,
        "rep_flat": 0,
    },
    RECON_TIER_HIGH: {
        "cash_multiplier": 1.2,
        "heat_flat": -1,
        "rep_flat": 1,
    },
}

RUN_MILESTONES = (3, 5, 10)
BEAT2_PENALTY_FLAG = FlagKey.BEAT2_PENALTY.value
BEAT2_PENALTY_DC = 2


# Run-bucket reward policy:
#   0-2 runs  -> base rates (learning the job)
#   3-6 runs  -> cash +15-25%, heat -10%, rep +20% (familiar, efficient)
#   7+  runs  -> cash +30-45%, heat -20%, rep back to base (routine, unremarkable)
# Final cash = base_cash * run_bucket_cash_multiplier * recon_tier_cash_multiplier
REWARD_BUCKETS = (
    {
        "min_runs": 0,
        "max_runs": 2,
        "cash_multiplier_min": 1.0,
        "cash_multiplier_max": 1.0,
        "heat_multiplier": 1.0,
        "rep_multiplier": 1.0,
    },
    {
        "min_runs": 3,
        "max_runs": 6,
        "cash_multiplier_min": 1.15,
        "cash_multiplier_max": 1.25,
        "heat_multiplier": 0.9,
        "rep_multiplier": 1.2,
    },
    {
        "min_runs": 7,
        "max_runs": None,
        "cash_multiplier_min": 1.30,
        "cash_multiplier_max": 1.45,
        "heat_multiplier": 0.80,
        "rep_multiplier": 1.0,
    },
)


class JobRulesError(ValueError):
    pass


@dataclass(frozen=True)
class RollOutcome:
    roll: int
    modifier: int
    total: int
    dc: int
    stat: str
    success: bool


@transaction.atomic
def increment_turn(session) -> int:
    """Increment and persist the session turn counter, returning the new value."""
    session.turn_counter += 1
    session.save(update_fields=["turn_counter"])
    return session.turn_counter


def get_or_create_job_state(session, job: Job) -> PlayerJobState:
    state, _ = PlayerJobState.objects.get_or_create(session=session, job=job)
    return state


def get_or_create_contact_offer_state(
    session, offer: ContactJobOffer
) -> PlayerContactOfferState:
    state, _ = PlayerContactOfferState.objects.get_or_create(session=session, offer=offer)
    return state
