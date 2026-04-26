from __future__ import annotations

from ..models import Job, JobApproach, JobRun
from ..services import flags


def _clear_approach_flags(session, job: Job) -> None:
    """Clear all approach and penalty flags for a job so prior runs don't bleed into new ones."""
    flags.clear_job_approach_flags(session, job.approaches.values_list("key", flat=True))


def _get_selected_approach_from_flags_or_run(session, run: JobRun) -> JobApproach | None:
    for approach in run.job.approaches.all().order_by("order", "id"):
        if flags.has_flag(session, flags.approach_selected_flag(approach.key)):
            return approach
    return run.selected_approach
