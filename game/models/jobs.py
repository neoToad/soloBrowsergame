from django.db import models

from ..constants import STAT_FIELD_MAP
from .requirements import RequirementGroup


RECON_TIER_LOW = "low"
RECON_TIER_MID = "mid"
RECON_TIER_HIGH = "high"
RECON_TIER_CHOICES = [
    (RECON_TIER_LOW, "Low"),
    (RECON_TIER_MID, "Mid"),
    (RECON_TIER_HIGH, "High"),
]
RECON_TIER_MIN_CUNNING = {
    RECON_TIER_LOW: 0,
    RECON_TIER_MID: 7,
    RECON_TIER_HIGH: 12,
}


class Job(models.Model):
    key = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)
    base_cooldown_turns = models.PositiveIntegerField(default=3)

    base_cash_min = models.PositiveIntegerField(default=0)
    base_cash_max = models.PositiveIntegerField(default=0)
    base_heat = models.IntegerField(default=0)
    base_rep = models.IntegerField(default=0)

    recon_text_low = models.TextField(blank=True)
    recon_text_mid = models.TextField(blank=True)
    recon_text_high = models.TextField(blank=True)

    district_hubs = models.ManyToManyField(
        "Scene",
        blank=True,
        related_name="district_jobs",
        limit_choices_to={"scene_type": "hub"},
        help_text="Hub scenes where this job target appears for recon.",
    )
    unlock_requirements = models.ManyToManyField(
        RequirementGroup,
        blank=True,
        related_name="gated_jobs",
    )

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


class JobApproach(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="approaches")
    key = models.SlugField(
        help_text="Approach key used for flags, e.g. 'alley' in approach_alley."
    )
    label = models.CharField(max_length=200)
    order = models.IntegerField(default=0)

    min_recon_tier = models.CharField(
        max_length=10,
        choices=RECON_TIER_CHOICES,
        default=RECON_TIER_LOW,
    )
    roll_stat = models.CharField(
        max_length=50,
        choices=[(v, v) for v in STAT_FIELD_MAP.values()],
    )
    base_difficulty = models.IntegerField(default=10)

    class Meta:
        ordering = ["job", "order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["job", "key"],
                name="uq_jobapproach_job_key",
            )
        ]

    def __str__(self):
        return f"{self.job.key} / {self.label}"


class JobBeatVariant(models.Model):
    BEAT_CHOICES = [
        (0, "Beat 0 - Recon"),
        (1, "Beat 1 - Approach"),
        (2, "Beat 2 - Complication"),
        (3, "Beat 3 - Resolution"),
    ]

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="beat_variants")
    beat_number = models.PositiveSmallIntegerField(choices=BEAT_CHOICES)
    key = models.SlugField()
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    order = models.IntegerField(default=0)

    approach = models.ForeignKey(
        JobApproach,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="beat_variants",
        help_text="Optional approach-specific variant; commonly used for Beat 2 branching.",
    )
    requires_roll = models.BooleanField(default=False)
    roll_stat = models.CharField(
        max_length=50,
        blank=True,
        choices=[("", "---")] + [(v, v) for v in STAT_FIELD_MAP.values()],
    )
    base_difficulty = models.IntegerField(default=10)
    allow_abort = models.BooleanField(default=False)

    class Meta:
        ordering = ["job", "beat_number", "order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["job", "beat_number", "key"],
                name="uq_jobbeatvariant_job_beat_key",
            )
        ]

    def __str__(self):
        return f"{self.job.key} / beat {self.beat_number} / {self.key}"


class PlayerJobState(models.Model):
    session = models.ForeignKey(
        "GameSession",
        on_delete=models.CASCADE,
        related_name="job_states",
    )
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="player_states")
    run_count = models.PositiveIntegerField(default=0)
    cooldown_until_turn = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "job"],
                name="uq_playerjobstate_session_job",
            )
        ]

    def __str__(self):
        return f"{self.session_id} / {self.job.key}"


class ContactJobOffer(models.Model):
    contact = models.ForeignKey(
        "Contact",
        on_delete=models.CASCADE,
        related_name="job_offers",
    )
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="contact_offers")
    scene = models.ForeignKey(
        "Scene",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contact_job_offers",
        limit_choices_to={"scene_type": "hub"},
        help_text="Hub scene where this contact can offer this job.",
    )

    key = models.SlugField(unique=True)
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    min_run_count = models.PositiveIntegerField(default=0)
    required_flag = models.CharField(max_length=100, blank=True)
    unlock_requirements = models.ManyToManyField(
        RequirementGroup,
        blank=True,
        related_name="gated_contact_job_offers",
    )

    cooldown_turns = models.PositiveIntegerField(default=0)

    first_meeting_text = models.TextField(blank=True)
    standard_offer_text = models.TextField(blank=True)
    nothing_available_text = models.TextField(blank=True)

    class Meta:
        ordering = ["contact", "order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["contact", "job"],
                name="uq_contactjoboffer_contact_job",
            )
        ]

    def __str__(self):
        return f"{self.contact.name} -> {self.job.title}"


class PlayerContactOfferState(models.Model):
    session = models.ForeignKey(
        "GameSession",
        on_delete=models.CASCADE,
        related_name="contact_offer_states",
    )
    offer = models.ForeignKey(
        ContactJobOffer,
        on_delete=models.CASCADE,
        related_name="player_states",
    )
    cooldown_until_turn = models.PositiveIntegerField(default=0)
    met_contact = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "offer"],
                name="uq_playercontactofferstate_session_offer",
            )
        ]

    def __str__(self):
        return f"{self.session_id} / {self.offer.key}"


class JobRun(models.Model):
    SOURCE_RECON = "recon"
    SOURCE_CONTACT = "contact"
    SOURCE_CHOICES = [
        (SOURCE_RECON, "Recon"),
        (SOURCE_CONTACT, "Contact"),
    ]

    STATUS_ACTIVE = "active"
    STATUS_COMPLETED = "completed"
    STATUS_ABORTED = "aborted"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_ABORTED, "Aborted"),
    ]

    session = models.ForeignKey(
        "GameSession",
        on_delete=models.CASCADE,
        related_name="job_runs",
    )
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="runs")
    contact_offer = models.ForeignKey(
        ContactJobOffer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="runs",
    )

    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_RECON)
    recon_tier = models.CharField(
        max_length=10,
        choices=RECON_TIER_CHOICES,
        default=RECON_TIER_LOW,
    )
    current_beat = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)

    selected_approach = models.ForeignKey(
        JobApproach,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="runs",
    )

    beat_1_success = models.BooleanField(null=True, blank=True)
    beat_2_success = models.BooleanField(null=True, blank=True)
    cash_awarded = models.IntegerField(default=0)
    heat_applied = models.IntegerField(default=0)
    rep_awarded = models.IntegerField(default=0)

    started_turn = models.PositiveIntegerField(default=0)
    completed_turn = models.PositiveIntegerField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.session_id} / {self.job.key} / {self.status}"
