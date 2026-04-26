from __future__ import annotations

import random
from typing import Any

from django.db import transaction

from ..services import flags
from .jobs_common import (
    RUN_MILESTONES,
    JobRulesError,
    get_or_create_contact_offer_state,
    get_or_create_job_state,
)
from .jobs_rolls import _reward_bucket_for_run_count, get_recon_modifiers


@transaction.atomic
def apply_job_rewards(session, run) -> dict[str, int]:
    """Compute and persist cash/heat/rep outcomes for a completed run."""
    if run.session_id != session.id:
        raise JobRulesError("Run does not belong to this session.")

    stats = session.stats
    job_state = get_or_create_job_state(session, run.job)
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
def apply_job_cooldowns(session, run) -> dict[str, Any]:
    """Update per-job/contact cooldown state and milestone flags after run completion."""
    if run.session_id != session.id:
        raise JobRulesError("Run does not belong to this session.")

    job_state = get_or_create_job_state(session, run.job)
    job_state.run_count += 1
    job_state.cooldown_until_turn = session.turn_counter + run.job.base_cooldown_turns
    job_state.save(update_fields=["run_count", "cooldown_until_turn"])

    if run.contact_offer_id:
        offer_state = get_or_create_contact_offer_state(session, run.contact_offer)
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
