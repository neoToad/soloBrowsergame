from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from ..models import (
    ContactJobOffer,
    Job,
    JobApproach,
    JobBeatVariant,
    JobRun,
    PlayerContext,
    PlayerContact,
    PlayerContactOfferState,
    PlayerJobState,
)
from ..models.jobs import (
    RECON_TIER_HIGH,
    RECON_TIER_LOW,
    RECON_TIER_MID,
    RECON_TIER_MIN_CUNNING,
)
from ..services import flags
from ..services.inventory import get_player_inventory
from ..utils import get_effective_stats, roll_d20, stat_modifier


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
BEAT2_PENALTY_FLAG = "beat2_penalty"
BEAT2_PENALTY_DC = 2


# Slice 5 will tune these values if balancing changes.
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
        "cash_multiplier_min": 1.3,
        "cash_multiplier_max": 1.45,
        "heat_multiplier": 0.8,
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
    session.turn_counter += 1
    session.save(update_fields=["turn_counter"])
    return session.turn_counter


def get_recon_tier(effective_stats) -> str:
    cunning_value = getattr(effective_stats, "intellect", 0)
    if cunning_value >= RECON_TIER_MIN_CUNNING[RECON_TIER_HIGH]:
        return RECON_TIER_HIGH
    if cunning_value >= RECON_TIER_MIN_CUNNING[RECON_TIER_MID]:
        return RECON_TIER_MID
    return RECON_TIER_LOW


def get_recon_modifiers(tier: str) -> dict[str, float | int]:
    if tier not in RECON_MODIFIERS:
        raise JobRulesError(f"Unknown recon tier: {tier}")
    return dict(RECON_MODIFIERS[tier])


def list_district_targets(session, scene, ctx) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    active_job_ids = set(
        JobRun.objects.filter(
            session=session,
            status=JobRun.STATUS_ACTIVE,
        ).values_list("job_id", flat=True)
    )
    tier = get_recon_tier(ctx.stats)

    for job in Job.objects.filter(is_active=True, district_hubs=scene).prefetch_related(
        "unlock_requirements__requirements"
    ):
        state = _get_or_create_job_state(session, job)
        locked_reasons: list[str] = []

        if not _requirements_pass(job.unlock_requirements.all(), ctx):
            locked_reasons.append("requirements")

        turns_remaining = max(0, state.cooldown_until_turn - session.turn_counter)
        if turns_remaining > 0:
            locked_reasons.append("cooldown")

        if job.id in active_job_ids:
            locked_reasons.append("active_run")

        rows.append(
            {
                "job": job,
                "job_state": state,
                "available": not locked_reasons,
                "locked_reasons": locked_reasons,
                "cooldown_turns_remaining": turns_remaining,
                "recon_tier": tier,
                "recon_modifiers": get_recon_modifiers(tier),
                "recon_text": _get_recon_text_for_tier(job, tier),
            }
        )

    return rows


def list_contact_offers(session, scene, ctx) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    active_job_ids = set(
        JobRun.objects.filter(
            session=session,
            status=JobRun.STATUS_ACTIVE,
        ).values_list("job_id", flat=True)
    )

    offers = ContactJobOffer.objects.filter(
        is_active=True,
    ).filter(Q(scene=scene) | Q(scene__isnull=True)).prefetch_related(
        "unlock_requirements__requirements"
    ).select_related("job", "contact")

    for offer in offers:
        offer_state = _get_or_create_contact_offer_state(session, offer)
        job_state = _get_or_create_job_state(session, offer.job)

        locked_reasons: list[str] = []
        if not _requirements_pass(offer.unlock_requirements.all(), ctx):
            locked_reasons.append("requirements")

        if offer.required_flag and not flags.has_flag(session, offer.required_flag):
            locked_reasons.append("required_flag")

        if job_state.run_count < offer.min_run_count:
            locked_reasons.append("min_run_count")

        turns_remaining = max(0, offer_state.cooldown_until_turn - session.turn_counter)
        if turns_remaining > 0:
            locked_reasons.append("cooldown")

        if offer.job_id in active_job_ids:
            locked_reasons.append("active_run")

        rows.append(
            {
                "offer": offer,
                "offer_state": offer_state,
                "available": not locked_reasons,
                "locked_reasons": locked_reasons,
                "cooldown_turns_remaining": turns_remaining,
                "recon_tier": RECON_TIER_HIGH,
                "recon_modifiers": get_recon_modifiers(RECON_TIER_HIGH),
                "is_first_meeting": not offer_state.met_contact,
            }
        )

    return rows


@transaction.atomic
def start_recon(session, job: Job) -> dict[str, Any]:
    effective_stats = _get_effective_stats_for_session(session)
    ctx = _build_player_context(session, effective_stats)
    _assert_job_startable(session, job, ctx)

    tier = get_recon_tier(effective_stats)
    return {
        "job": job,
        "recon_tier": tier,
        "recon_modifiers": get_recon_modifiers(tier),
        "recon_text": _get_recon_text_for_tier(job, tier),
        "approaches": list(_available_approaches_for_tier(job, tier)),
    }


@transaction.atomic
def commit_recon(session, job: Job) -> JobRun:
    effective_stats = _get_effective_stats_for_session(session)
    ctx = _build_player_context(session, effective_stats)
    _assert_job_startable(session, job, ctx)

    tier = get_recon_tier(effective_stats)
    run = JobRun.objects.create(
        session=session,
        job=job,
        source=JobRun.SOURCE_RECON,
        recon_tier=tier,
        current_beat=1,
        started_turn=session.turn_counter,
        status=JobRun.STATUS_ACTIVE,
    )
    increment_turn(session)
    return run


@transaction.atomic
def start_contact_job(session, contact_offer: ContactJobOffer) -> JobRun:
    if not contact_offer.is_active:
        raise JobRulesError("Contact offer is not active.")

    effective_stats = _get_effective_stats_for_session(session)
    ctx = _build_player_context(session, effective_stats)

    _assert_contact_offer_startable(session, contact_offer, ctx)

    offer_state = _get_or_create_contact_offer_state(session, contact_offer)
    if not offer_state.met_contact:
        offer_state.met_contact = True
        offer_state.save(update_fields=["met_contact"])

    run = JobRun.objects.create(
        session=session,
        job=contact_offer.job,
        contact_offer=contact_offer,
        source=JobRun.SOURCE_CONTACT,
        recon_tier=RECON_TIER_HIGH,
        current_beat=1,
        started_turn=session.turn_counter,
        status=JobRun.STATUS_ACTIVE,
    )
    increment_turn(session)
    return run


@transaction.atomic
def resolve_beat_1(session, run: JobRun, approach: JobApproach) -> dict[str, Any]:
    _assert_active_run(session, run, expected_beat=1)
    if approach.job_id != run.job_id:
        raise JobRulesError("Approach does not belong to this run's job.")

    if _tier_rank(approach.min_recon_tier) > _tier_rank(run.recon_tier):
        raise JobRulesError("Recon tier too low for this approach.")

    effective_stats = _get_effective_stats_for_session(session)
    roll = _roll_check(effective_stats, approach.roll_stat, approach.base_difficulty)

    run.selected_approach = approach
    run.beat_1_success = roll.success
    run.current_beat = 2
    run.save(update_fields=["selected_approach", "beat_1_success", "current_beat"])

    approach_flag = f"approach_{approach.key}"
    failed_flag = f"{approach_flag}_failed"

    flags.set_flag(session, approach_flag)
    if roll.success:
        flags.clear_flag(session, failed_flag)
        flags.clear_flag(session, BEAT2_PENALTY_FLAG)
    else:
        flags.set_flag(session, failed_flag)
        flags.set_flag(session, BEAT2_PENALTY_FLAG)

    increment_turn(session)
    return {
        "run": run,
        "approach": approach,
        "roll": roll,
    }


@transaction.atomic
def resolve_beat_2(session, run: JobRun, action: str) -> dict[str, Any]:
    _assert_active_run(session, run, expected_beat=2)

    selected_approach = _get_selected_approach_from_flags_or_run(session, run)
    if selected_approach is None:
        raise JobRulesError("No selected approach available for beat 2.")

    variant = (
        JobBeatVariant.objects.filter(
            job=run.job,
            beat_number=2,
            approach=selected_approach,
            key=action,
        )
        .order_by("order", "id")
        .first()
    )
    if variant is None:
        raise JobRulesError("Invalid beat 2 action for selected approach.")

    roll = None
    success = True
    if variant.requires_roll:
        effective_stats = _get_effective_stats_for_session(session)
        dc = variant.base_difficulty
        if flags.has_flag(session, BEAT2_PENALTY_FLAG):
            dc += BEAT2_PENALTY_DC
        roll = _roll_check(effective_stats, variant.roll_stat, dc)
        success = roll.success

    run.beat_2_success = success
    run.current_beat = 3
    run.save(update_fields=["beat_2_success", "current_beat"])

    increment_turn(session)
    return {
        "run": run,
        "variant": variant,
        "roll": roll,
    }


@transaction.atomic
def resolve_beat_3(session, run: JobRun) -> dict[str, Any]:
    _assert_active_run(session, run, expected_beat=3)

    rewards = apply_job_rewards(session, run)
    cooldowns = apply_job_cooldowns(session, run)

    run.status = JobRun.STATUS_COMPLETED
    run.completed_turn = session.turn_counter
    run.completed_at = timezone.now()
    run.save(update_fields=["status", "completed_turn", "completed_at"])

    increment_turn(session)
    return {
        "run": run,
        "rewards": rewards,
        "cooldowns": cooldowns,
    }


@transaction.atomic
def abort_job_run(session, run: JobRun) -> JobRun:
    if run.session_id != session.id:
        raise JobRulesError("Run does not belong to this session.")
    if run.status != JobRun.STATUS_ACTIVE:
        raise JobRulesError("Run is not active.")

    run.status = JobRun.STATUS_ABORTED
    run.completed_turn = session.turn_counter
    run.completed_at = timezone.now()
    run.save(update_fields=["status", "completed_turn", "completed_at"])
    increment_turn(session)
    return run


@transaction.atomic
def apply_job_rewards(session, run: JobRun) -> dict[str, int]:
    if run.session_id != session.id:
        raise JobRulesError("Run does not belong to this session.")

    stats = session.stats
    job_state = _get_or_create_job_state(session, run.job)
    bucket = _reward_bucket_for_run_count(job_state.run_count)

    cash_floor = min(run.job.base_cash_min, run.job.base_cash_max)
    cash_ceil = max(run.job.base_cash_min, run.job.base_cash_max)
    base_cash = random.randint(cash_floor, cash_ceil)

    run_cash_multiplier = random.uniform(
        bucket["cash_multiplier_min"],
        bucket["cash_multiplier_max"],
    )
    recon_mods = get_recon_modifiers(run.recon_tier)

    final_cash = round(base_cash * run_cash_multiplier * recon_mods["cash_multiplier"])
    final_heat = round(run.job.base_heat * bucket["heat_multiplier"] + recon_mods["heat_flat"])
    final_rep = round(run.job.base_rep * bucket["rep_multiplier"] + recon_mods["rep_flat"])

    stats.cash += final_cash
    stats.heat = max(0, stats.heat + final_heat)
    stats.rep += final_rep
    stats.save(update_fields=["cash", "heat", "rep"])

    run.cash_awarded = final_cash
    run.heat_applied = final_heat
    run.rep_awarded = final_rep
    run.save(update_fields=["cash_awarded", "heat_applied", "rep_awarded"])

    return {
        "cash": final_cash,
        "heat": final_heat,
        "rep": final_rep,
    }


@transaction.atomic
def apply_job_cooldowns(session, run: JobRun) -> dict[str, Any]:
    if run.session_id != session.id:
        raise JobRulesError("Run does not belong to this session.")

    job_state = _get_or_create_job_state(session, run.job)
    job_state.run_count += 1
    job_state.cooldown_until_turn = session.turn_counter + run.job.base_cooldown_turns
    job_state.save(update_fields=["run_count", "cooldown_until_turn"])

    if run.contact_offer_id:
        offer_state = _get_or_create_contact_offer_state(session, run.contact_offer)
        offer_state.met_contact = True
        offer_state.cooldown_until_turn = (
            session.turn_counter + run.contact_offer.cooldown_turns
        )
        offer_state.save(update_fields=["met_contact", "cooldown_until_turn"])

    milestone_flag = None
    if job_state.run_count in RUN_MILESTONES:
        milestone_flag = f"ran_{run.job.key}_{job_state.run_count}x"
        flags.set_flag(session, milestone_flag)

    return {
        "job_state": job_state,
        "milestone_flag": milestone_flag,
    }


def _available_approaches_for_tier(job: Job, tier: str):
    return job.approaches.filter(
        min_recon_tier__in=_tiers_at_or_below(tier)
    ).order_by("order", "id")


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


def _requirements_pass(groups, ctx: PlayerContext) -> bool:
    return all(group.evaluate(ctx) for group in groups)


def _build_player_context(session, effective_stats) -> PlayerContext:
    from ..services.session import get_completed_map

    inventory = get_player_inventory(session)
    completed_map = get_completed_map(session)
    contacts = {
        pc.contact_id: pc
        for pc in PlayerContact.objects.filter(session=session).only("id", "contact_id")
    }
    return PlayerContext(
        stats=effective_stats,
        inventory=inventory,
        completed_map=completed_map,
        flags=session.flags,
        contacts=contacts,
    )


def _get_effective_stats_for_session(session):
    inventory = get_player_inventory(session)
    return get_effective_stats(session.stats, inventory)


def _assert_job_startable(session, job: Job, ctx: PlayerContext) -> None:
    if not job.is_active:
        raise JobRulesError("Job is not active.")

    if JobRun.objects.filter(
        session=session,
        job=job,
        status=JobRun.STATUS_ACTIVE,
    ).exists():
        raise JobRulesError("Job already has an active run.")

    state = _get_or_create_job_state(session, job)
    if state.cooldown_until_turn > session.turn_counter:
        raise JobRulesError("Job is on cooldown.")

    if not _requirements_pass(job.unlock_requirements.all(), ctx):
        raise JobRulesError("Job unlock requirements are not met.")


def _assert_contact_offer_startable(session, offer: ContactJobOffer, ctx: PlayerContext) -> None:
    _assert_job_startable(session, offer.job, ctx)

    if offer.required_flag and not flags.has_flag(session, offer.required_flag):
        raise JobRulesError("Offer required flag is missing.")

    if not _requirements_pass(offer.unlock_requirements.all(), ctx):
        raise JobRulesError("Offer unlock requirements are not met.")

    job_state = _get_or_create_job_state(session, offer.job)
    if job_state.run_count < offer.min_run_count:
        raise JobRulesError("Offer min run count not met.")

    offer_state = _get_or_create_contact_offer_state(session, offer)
    if offer_state.cooldown_until_turn > session.turn_counter:
        raise JobRulesError("Offer is on cooldown.")


def _assert_active_run(session, run: JobRun, expected_beat: int) -> None:
    if run.session_id != session.id:
        raise JobRulesError("Run does not belong to this session.")
    if run.status != JobRun.STATUS_ACTIVE:
        raise JobRulesError("Run is not active.")
    if run.current_beat != expected_beat:
        raise JobRulesError(f"Run is on beat {run.current_beat}, expected {expected_beat}.")


def _get_or_create_job_state(session, job: Job) -> PlayerJobState:
    state, _ = PlayerJobState.objects.get_or_create(session=session, job=job)
    return state


def _get_or_create_contact_offer_state(session, offer: ContactJobOffer) -> PlayerContactOfferState:
    state, _ = PlayerContactOfferState.objects.get_or_create(session=session, offer=offer)
    return state


def _get_selected_approach_from_flags_or_run(session, run: JobRun) -> JobApproach | None:
    for approach in run.job.approaches.all().order_by("order", "id"):
        if flags.has_flag(session, f"approach_{approach.key}"):
            return approach
    return run.selected_approach


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


def _get_recon_text_for_tier(job: Job, tier: str) -> str:
    if tier == RECON_TIER_HIGH:
        return job.recon_text_high
    if tier == RECON_TIER_MID:
        return job.recon_text_mid
    return job.recon_text_low
