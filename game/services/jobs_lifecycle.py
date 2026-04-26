from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from ..models import ContactJobOffer, Job, JobApproach, JobBeatVariant, JobRun
from ..models.jobs import RECON_TIER_HIGH, RECON_TIER_MID
from ..services import flags
from .jobs_common import BEAT2_PENALTY_DC, BEAT2_PENALTY_FLAG, JobRulesError, increment_turn
from .jobs_eligibility import (
    _assert_contact_offer_startable,
    _assert_job_startable,
    _build_player_context,
    _get_effective_stats_for_session,
)
from .jobs_flags import _clear_approach_flags, _get_selected_approach_from_flags_or_run
from .jobs_rolls import _roll_check, _tier_rank, _available_approaches_for_tier, get_recon_modifiers, get_recon_tier
from .jobs_rewards import apply_job_cooldowns, apply_job_rewards
from .jobs_common import get_or_create_contact_offer_state


@transaction.atomic
def start_recon(session, job: Job) -> dict:
    """Validate a job can start and return recon preview payload without creating a run."""
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
    """Create an active job run from recon flow and advance the turn counter."""
    effective_stats = _get_effective_stats_for_session(session)
    ctx = _build_player_context(session, effective_stats)
    _assert_job_startable(session, job, ctx)

    _clear_approach_flags(session, job)
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
    """Create an active job run started from a contact offer and advance the turn counter."""
    if not contact_offer.is_active:
        raise JobRulesError("Contact offer is not active.")

    effective_stats = _get_effective_stats_for_session(session)
    ctx = _build_player_context(session, effective_stats)

    _assert_contact_offer_startable(session, contact_offer, ctx)

    _clear_approach_flags(session, contact_offer.job)
    offer_state = get_or_create_contact_offer_state(session, contact_offer)
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
def resolve_beat_1(session, run: JobRun, approach: JobApproach) -> dict:
    """Resolve beat 1 approach roll, persist run progression, and set approach flags."""
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
def resolve_beat_2(session, run: JobRun, action: str) -> dict:
    """Resolve beat 2 action (and optional roll), then advance run to beat 3."""
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
def resolve_beat_3(session, run: JobRun) -> dict:
    """Finalize beat 3 by applying rewards/cooldowns, completing the run, and advancing turn."""
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
    """Abort an active run for the session and advance the turn counter."""
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


def _assert_active_run(session, run: JobRun, expected_beat: int) -> None:
    if run.session_id != session.id:
        raise JobRulesError("Run does not belong to this session.")
    if run.status != JobRun.STATUS_ACTIVE:
        raise JobRulesError("Run is not active.")
    if run.current_beat != expected_beat:
        raise JobRulesError(f"Run is on beat {run.current_beat}, expected {expected_beat}.")


def _get_recon_text_for_tier(job: Job, tier: str) -> str:
    if tier == RECON_TIER_HIGH:
        return job.recon_text_high
    if tier == RECON_TIER_MID:
        return job.recon_text_mid
    return job.recon_text_low
