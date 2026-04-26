from __future__ import annotations

from ..models import Job, JobApproach, JobRun
from ..services import flags
from .jobs_common import BEAT2_PENALTY_FLAG


def _clear_approach_flags(session, job: Job) -> None:
    """Clear all approach and penalty flags for a job so prior runs don't bleed into new ones."""
    for key in job.approaches.values_list("key", flat=True):
        session.flags.pop(f"approach_{key}", None)
        session.flags.pop(f"approach_{key}_failed", None)
    session.flags.pop(BEAT2_PENALTY_FLAG, None)
    session.save(update_fields=["flags"])


def _get_selected_approach_from_flags_or_run(session, run: JobRun) -> JobApproach | None:
    for approach in run.job.approaches.all().order_by("order", "id"):
        if flags.has_flag(session, f"approach_{approach.key}"):
            return approach
    return run.selected_approach
