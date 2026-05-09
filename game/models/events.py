import uuid
from django.db import models
from .player import GameSession


_EVENT_LOG_CAP = 5


def log_event(session, text: str) -> None:
    batch_id = uuid.uuid4()
    EventLog.objects.create(session=session, text=text, batch_id=batch_id)
    _trim_overflow(session)


def flush_event_log(session, texts) -> None:
    if not texts:
        return
    batch_id = uuid.uuid4()
    for text in texts:
        EventLog.objects.create(session=session, text=text, batch_id=batch_id)
    _trim_overflow(session)


def get_latest_batch(session):
    """Return all EventLog rows belonging to the most recent batch."""
    latest = EventLog.objects.filter(session=session).order_by('-timestamp').first()
    if latest is None:
        return []
    if latest.batch_id is None:
        return [latest]
    return list(
        EventLog.objects
        .filter(session=session, batch_id=latest.batch_id)
        .order_by('timestamp')
    )


def _trim_overflow(session) -> None:
    overflow_ids = (
        EventLog.objects
        .filter(session=session)
        .order_by('-timestamp')
        .values_list('id', flat=True)[_EVENT_LOG_CAP:]
    )
    if overflow_ids:
        EventLog.objects.filter(id__in=list(overflow_ids)).delete()


class EventLog(models.Model):
    session   = models.ForeignKey(
                    GameSession,
                    related_name='log',
                    on_delete=models.CASCADE
                )
    timestamp = models.DateTimeField(auto_now_add=True)
    text      = models.TextField()
    batch_id  = models.UUIDField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.session} — {self.text[:50]}"
