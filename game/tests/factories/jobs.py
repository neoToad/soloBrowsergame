import factory

from game.models import ContactJobOffer, Job, JobApproach, JobBeatVariant, JobRun
from game.models.jobs import RECON_TIER_LOW

from .base import BaseFactory
from .player import GameSessionFactory
from .world import ContactFactory, SceneFactory


class JobFactory(BaseFactory):
    class Meta:
        model = Job

    key = factory.Sequence(lambda n: f"job-{n}")
    title = factory.Sequence(lambda n: f"Job {n}")
    description = ""
    is_active = True
    base_cooldown_turns = 3
    base_cash_min = 0
    base_cash_max = 0
    base_heat = 0
    base_rep = 0
    recon_text_low = "low"
    recon_text_mid = "mid"
    recon_text_high = "high"

    @factory.post_generation
    def district_hubs(self, create, extracted, **kwargs):
        if not create or not extracted:
            return
        for scene in extracted:
            self.district_hubs.add(scene)


class JobApproachFactory(BaseFactory):
    class Meta:
        model = JobApproach

    job = factory.SubFactory(JobFactory)
    key = factory.Sequence(lambda n: f"approach-{n}")
    label = factory.Sequence(lambda n: f"Approach {n}")
    order = 0
    min_recon_tier = RECON_TIER_LOW
    roll_stat = "agility"
    base_difficulty = 10


class JobBeatVariantFactory(BaseFactory):
    class Meta:
        model = JobBeatVariant

    job = factory.SubFactory(JobFactory)
    beat_number = 2
    key = factory.Sequence(lambda n: f"beat-{n}")
    title = factory.Sequence(lambda n: f"Beat {n}")
    body = ""
    order = 0
    approach = None
    requires_roll = False
    roll_stat = ""
    base_difficulty = 10
    allow_abort = False


class ContactJobOfferFactory(BaseFactory):
    class Meta:
        model = ContactJobOffer

    contact = factory.SubFactory(ContactFactory)
    job = factory.SubFactory(JobFactory)
    scene = factory.SubFactory(SceneFactory, hub=True)
    key = factory.Sequence(lambda n: f"offer-{n}")
    order = 0
    is_active = True
    min_run_count = 0
    required_flag = ""
    cooldown_turns = 0
    first_meeting_text = ""
    standard_offer_text = ""
    nothing_available_text = ""


class JobRunFactory(BaseFactory):
    class Meta:
        model = JobRun

    session = factory.SubFactory(GameSessionFactory)
    job = factory.SubFactory(JobFactory)
    contact_offer = None
    source = JobRun.SOURCE_RECON
    recon_tier = RECON_TIER_LOW
    current_beat = 0
    status = JobRun.STATUS_ACTIVE
    selected_approach = None
    beat_1_success = None
    beat_2_success = None
    cash_awarded = 0
    heat_applied = 0
    rep_awarded = 0
    started_turn = 0
    completed_turn = None
    completed_at = None
