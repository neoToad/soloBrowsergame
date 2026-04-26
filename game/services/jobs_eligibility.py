from __future__ import annotations

from ..models import ContactJobOffer, Job, JobRun, PlayerContact, PlayerContext
from ..services import flags
from ..services.inventory import get_player_inventory
from .jobs_common import JobRulesError, get_or_create_contact_offer_state, get_or_create_job_state


def _requirements_pass(groups, ctx: PlayerContext) -> bool:
    return all(group.evaluate(ctx) for group in groups)


def _build_player_context(session, effective_stats) -> PlayerContext:
    from ..services.session import build_player_context, get_completed_map

    inventory = get_player_inventory(session)
    completed_map = get_completed_map(session)
    contacts = {
        pc.contact_id: pc
        for pc in PlayerContact.objects.filter(session=session).only("id", "contact_id")
    }
    return build_player_context(
        effective_stats,
        inventory,
        completed_map,
        flags=session.flags,
        contacts=contacts,
    )


def _get_effective_stats_for_session(session):
    from ..utils import get_effective_stats

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

    state = get_or_create_job_state(session, job)
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

    job_state = get_or_create_job_state(session, offer.job)
    if job_state.run_count < offer.min_run_count:
        raise JobRulesError("Offer min run count not met.")

    offer_state = get_or_create_contact_offer_state(session, offer)
    if offer_state.cooldown_until_turn > session.turn_counter:
        raise JobRulesError("Offer is on cooldown.")
