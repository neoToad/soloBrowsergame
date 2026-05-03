from django.db import models
from .player import GameSession


_EVENT_LOG_CAP = 5


def log_event(session, text: str) -> None:
    EventLog.objects.create(session=session, text=text)
    _trim_overflow(session)


def flush_event_log(session, texts) -> None:
    if not texts:
        return
    EventLog.objects.bulk_create(
        [EventLog(session=session, text=t) for t in texts]
    )
    _trim_overflow(session)


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

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.session} — {self.text[:50]}"
