from django.db import models
from .player import GameSession


def log_event(session, text: str) -> None:
    """Thin helper to create an EventLog entry. Use this instead of calling
    EventLog.objects.create() directly so all call sites are consistent."""
    EventLog.objects.create(session=session, text=text)


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
