from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from game.models import (
    Contact,
    ContactJobOffer,
    GameSession,
    Job,
    JobApproach,
    JobBeatVariant,
    JobRun,
    PlayerContactOfferState,
    PlayerJobState,
    PlayerStats,
    Scene,
)
from game.models.jobs import RECON_TIER_HIGH, RECON_TIER_LOW, RECON_TIER_MID
from game.services import flags
from game.services import jobs


class JobsServiceTest(TestCase):
    def setUp(self):
        self.hub = Scene.objects.create(
            key="jobs__hub",
            title="Jobs Hub",
            body="",
            scene_type="hub",
        )
        self.session = GameSession.objects.create(
            session_key="jobs-test-session",
            current_scene=self.hub,
        )
        self.stats = PlayerStats.objects.create(
            session=self.session,
            strength=8,
            agility=8,
            intellect=6,
            charisma=8,
            hp=10,
            max_hp=10,
        )

    def _make_job(self, key="jobs__store_hit", **overrides):
        defaults = {
            "key": key,
            "title": "Store Hit",
            "description": "",
            "base_cooldown_turns": 4,
            "base_cash_min": 100,
            "base_cash_max": 100,
            "base_heat": 10,
            "base_rep": 5,
            "recon_text_low": "low",
            "recon_text_mid": "mid",
            "recon_text_high": "high",
        }
        defaults.update(overrides)
        job = Job.objects.create(**defaults)
        job.district_hubs.add(self.hub)
        return job

    def test_get_recon_tier_thresholds(self):
        self.assertEqual(jobs.get_recon_tier(SimpleNamespace(intellect=6)), RECON_TIER_LOW)
        self.assertEqual(jobs.get_recon_tier(SimpleNamespace(intellect=7)), RECON_TIER_MID)
        self.assertEqual(jobs.get_recon_tier(SimpleNamespace(intellect=12)), RECON_TIER_HIGH)

    def test_list_district_targets_reports_cooldown_state(self):
        job = self._make_job()
        PlayerJobState.objects.create(
            session=self.session,
            job=job,
            run_count=1,
            cooldown_until_turn=5,
        )
        self.session.turn_counter = 3
        self.session.save(update_fields=["turn_counter"])

        ctx = SimpleNamespace(stats=SimpleNamespace(intellect=10), inventory={}, completed_map={}, flags={})
        rows = jobs.list_district_targets(self.session, self.hub, ctx)

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertFalse(row["available"])
        self.assertEqual(row["cooldown_turns_remaining"], 2)
        self.assertIn("cooldown", row["locked_reasons"])

    @patch("game.services.jobs.roll_d20", return_value=1)
    def test_resolve_beat_1_failure_sets_required_flags(self, _mock_roll):
        job = self._make_job()
        run = JobRun.objects.create(
            session=self.session,
            job=job,
            source=JobRun.SOURCE_RECON,
            recon_tier=RECON_TIER_LOW,
            current_beat=1,
        )
        approach = JobApproach.objects.create(
            job=job,
            key="alley",
            label="Alley",
            min_recon_tier=RECON_TIER_LOW,
            roll_stat="strength",
            base_difficulty=20,
        )

        jobs.resolve_beat_1(self.session, run, approach)
        run.refresh_from_db()
        self.session.refresh_from_db()

        self.assertFalse(run.beat_1_success)
        self.assertEqual(run.current_beat, 2)
        self.assertTrue(flags.has_flag(self.session, "approach_alley"))
        self.assertTrue(flags.has_flag(self.session, "approach_alley_failed"))
        self.assertTrue(flags.has_flag(self.session, jobs.BEAT2_PENALTY_FLAG))

    def test_resolve_beat_2_uses_selected_approach_branch(self):
        job = self._make_job()
        approach_a = JobApproach.objects.create(
            job=job,
            key="front",
            label="Front",
            roll_stat="agility",
            base_difficulty=8,
        )
        approach_b = JobApproach.objects.create(
            job=job,
            key="roof",
            label="Roof",
            roll_stat="agility",
            base_difficulty=8,
        )
        variant_a = JobBeatVariant.objects.create(
            job=job,
            beat_number=2,
            key="complication-front",
            title="Front Complication",
            approach=approach_a,
            requires_roll=False,
        )
        JobBeatVariant.objects.create(
            job=job,
            beat_number=2,
            key="complication-roof",
            title="Roof Complication",
            approach=approach_b,
            requires_roll=False,
        )
        run = JobRun.objects.create(
            session=self.session,
            job=job,
            source=JobRun.SOURCE_RECON,
            recon_tier=RECON_TIER_MID,
            current_beat=2,
            selected_approach=approach_b,
        )
        flags.set_flag(self.session, "approach_front")

        result = jobs.resolve_beat_2(self.session, run, "complication-front")
        run.refresh_from_db()

        self.assertEqual(result["variant"].id, variant_a.id)
        self.assertEqual(run.current_beat, 3)
        self.assertTrue(run.beat_2_success)

    @patch("game.services.jobs.random.uniform", return_value=1.2)
    @patch("game.services.jobs.random.randint", return_value=100)
    def test_apply_job_rewards_uses_run_bucket_and_recon_modifiers(self, _mock_randint, _mock_uniform):
        job = self._make_job(base_heat=10, base_rep=5)
        run = JobRun.objects.create(
            session=self.session,
            job=job,
            source=JobRun.SOURCE_RECON,
            recon_tier=RECON_TIER_HIGH,
            current_beat=3,
        )
        PlayerJobState.objects.create(session=self.session, job=job, run_count=3)

        reward = jobs.apply_job_rewards(self.session, run)
        self.stats.refresh_from_db()
        run.refresh_from_db()

        self.assertEqual(reward["cash"], 144)
        self.assertEqual(reward["heat"], 8)
        self.assertEqual(reward["rep"], 7)
        self.assertEqual(self.stats.cash, 144)
        self.assertEqual(self.stats.heat, 8)
        self.assertEqual(self.stats.rep, 7)
        self.assertEqual(run.cash_awarded, 144)

    def test_apply_job_cooldowns_increments_runs_and_sets_milestone_flag(self):
        job = self._make_job(base_cooldown_turns=4)
        contact = Contact.objects.create(key="mickey", name="Mickey", description="")
        offer = ContactJobOffer.objects.create(
            key="mickey-store-hit",
            contact=contact,
            job=job,
            scene=self.hub,
            cooldown_turns=2,
        )
        run = JobRun.objects.create(
            session=self.session,
            job=job,
            contact_offer=offer,
            source=JobRun.SOURCE_CONTACT,
            recon_tier=RECON_TIER_HIGH,
            current_beat=3,
        )
        PlayerJobState.objects.create(session=self.session, job=job, run_count=2)
        self.session.turn_counter = 10
        self.session.save(update_fields=["turn_counter"])

        jobs.apply_job_cooldowns(self.session, run)
        job_state = PlayerJobState.objects.get(session=self.session, job=job)
        offer_state = PlayerContactOfferState.objects.get(session=self.session, offer=offer)
        self.session.refresh_from_db()

        self.assertEqual(job_state.run_count, 3)
        self.assertEqual(job_state.cooldown_until_turn, 14)
        self.assertEqual(offer_state.cooldown_until_turn, 12)
        self.assertTrue(flags.has_flag(self.session, f"ran_{job.key}_3x"))

    def test_start_contact_job_uses_high_tier_recon(self):
        job = self._make_job()
        contact = Contact.objects.create(key="court-clerk", name="Court Clerk", description="")
        offer = ContactJobOffer.objects.create(
            key="court-clerk-store-hit",
            contact=contact,
            job=job,
            scene=self.hub,
            cooldown_turns=0,
        )

        run = jobs.start_contact_job(self.session, offer)

        self.assertEqual(run.source, JobRun.SOURCE_CONTACT)
        self.assertEqual(run.recon_tier, RECON_TIER_HIGH)

    def test_increment_turn_advances_session_counter(self):
        self.assertEqual(self.session.turn_counter, 0)
        jobs.increment_turn(self.session)
        self.session.refresh_from_db()
        self.assertEqual(self.session.turn_counter, 1)
