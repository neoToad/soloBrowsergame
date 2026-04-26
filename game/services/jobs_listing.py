from __future__ import annotations

from typing import Any

from django.db.models import Q

from ..models import ContactJobOffer, Job, JobBeatVariant, JobRun, PlayerContext
from ..models.jobs import RECON_TIER_HIGH, RECON_TIER_MID
from ..services import flags
from .jobs_common import get_or_create_contact_offer_state, get_or_create_job_state
from .jobs_eligibility import _requirements_pass
from .jobs_flags import _get_selected_approach_from_flags_or_run
from .jobs_rolls import _available_approaches_for_tier, get_recon_modifiers, get_recon_tier


def list_district_targets(session, scene, ctx) -> list[dict[str, Any]]:
    """Build district job cards with availability and recon metadata for a hub scene."""
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
        state = get_or_create_job_state(session, job)
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
    """Build contact-offer cards with lock reasons and cooldown metadata."""
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
        offer_state = get_or_create_contact_offer_state(session, offer)
        job_state = get_or_create_job_state(session, offer.job)

        locked_reasons: list[str] = []
        if not _requirements_pass(offer.unlock_requirements.all(), ctx):
            locked_reasons.append("requirements")

        if offer.required_flag and not flags.has_flag(session, offer.required_flag):
            locked_reasons.append("required_flag")

        if job_state.run_count < offer.min_run_count:
            locked_reasons.append("min_run_count")

        offer_turns_remaining = max(0, offer_state.cooldown_until_turn - session.turn_counter)
        job_turns_remaining = max(0, job_state.cooldown_until_turn - session.turn_counter)
        turns_remaining = max(offer_turns_remaining, job_turns_remaining)
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


def build_jobs_hub_context(
    session,
    scene,
    effective_stats,
    inventory,
    completed_map,
) -> dict[str, Any]:
    """Build jobs-related context payload used by the hub scene templates."""
    if not scene.is_hub:
        return {
            "district_job_targets": [],
            "contact_job_offers": [],
            "active_job_run": None,
            "active_job_approaches": [],
            "active_job_beat_2_actions": [],
        }

    ctx = PlayerContext(
        stats=effective_stats,
        inventory=inventory,
        completed_map=completed_map,
        flags=session.flags,
    )
    district_targets = list_district_targets(session, scene, ctx)
    contact_offers = list_contact_offers(session, scene, ctx)

    active_run = (
        JobRun.objects.filter(
            session=session,
            status=JobRun.STATUS_ACTIVE,
        )
        .select_related("job", "selected_approach", "contact_offer", "contact_offer__contact")
        .order_by("-started_at")
        .first()
    )

    approaches = []
    beat_2_actions = []
    if active_run is not None:
        if active_run.current_beat == 1:
            approaches = list(_available_approaches_for_tier(active_run.job, active_run.recon_tier))
        elif active_run.current_beat == 2:
            selected_approach = _get_selected_approach_from_flags_or_run(session, active_run)
            if selected_approach is not None:
                beat_2_actions = list(
                    JobBeatVariant.objects.filter(
                        job=active_run.job,
                        beat_number=2,
                        approach=selected_approach,
                    ).order_by("order", "id")
                )

    return {
        "district_job_targets": district_targets,
        "contact_job_offers": contact_offers,
        "active_job_run": active_run,
        "active_job_approaches": approaches,
        "active_job_beat_2_actions": beat_2_actions,
    }


def _get_recon_text_for_tier(job: Job, tier: str) -> str:
    if tier == RECON_TIER_HIGH:
        return job.recon_text_high
    if tier == RECON_TIER_MID:
        return job.recon_text_mid
    return job.recon_text_low
