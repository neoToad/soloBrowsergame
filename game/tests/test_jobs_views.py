from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from game.models import (
    Contact,
    ContactJobOffer,
    Job,
    JobApproach,
    JobBeatVariant,
    JobRun,
    PlayerJobState,
    PlayerStats,
)
from game.models.jobs import RECON_TIER_HIGH
from game.tests.test_factories import make_game_session


class JobEndpointsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.session = make_game_session(self.client)
        self.scene = self.session.current_scene

    def _make_job(self, key="jobs__warehouse", **overrides):
        defaults = {
            "key": key,
            "title": "Warehouse Hit",
            "description": "",
            "base_cooldown_turns": 3,
            "base_cash_min": 100,
            "base_cash_max": 100,
            "base_heat": 5,
            "base_rep": 2,
            "recon_text_low": "low",
            "recon_text_mid": "mid",
            "recon_text_high": "high",
        }
        defaults.update(overrides)
        job = Job.objects.create(**defaults)
        job.district_hubs.add(self.scene)
        return job

    def test_job_recon_commit_happy_path_htmx(self):
        job = self._make_job()

        response = self.client.post(
            reverse("job_recon_commit", kwargs={"job_key": job.key}),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="scene-panel"', response.content.decode())
        run = JobRun.objects.get(session=self.session, job=job)
        self.assertEqual(run.status, JobRun.STATUS_ACTIVE)
        self.assertEqual(run.current_beat, 1)

    def test_job_recon_commit_gated_by_cooldown_returns_403(self):
        job = self._make_job()
        PlayerJobState.objects.create(
            session=self.session,
            job=job,
            run_count=1,
            cooldown_until_turn=20,
        )

        response = self.client.post(
            reverse("job_recon_commit", kwargs={"job_key": job.key}),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("cooldown", response.content.decode().lower())

    @patch("game.services.jobs.roll_d20", return_value=20)
    def test_job_run_beat_1_happy_path(self, _mock_roll):
        job = self._make_job()
        run = JobRun.objects.create(
            session=self.session,
            job=job,
            source=JobRun.SOURCE_RECON,
            current_beat=1,
        )
        approach = JobApproach.objects.create(
            job=job,
            key="alley",
            label="Alley",
            roll_stat="agility",
            base_difficulty=10,
        )

        response = self.client.post(
            reverse("job_run_beat_1", kwargs={"run_id": run.id}),
            {"approach": approach.key},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        run.refresh_from_db()
        self.assertTrue(run.beat_1_success)
        self.assertEqual(run.current_beat, 2)

    def test_job_run_beat_1_for_run_from_other_session_returns_403(self):
        other_session = self.session.__class__.objects.create(
            session_key="other-jobs-view-session",
            current_scene=self.scene,
        )
        PlayerStats.objects.create(session=other_session)
        other_job = self._make_job(key="jobs__other")
        other_run = JobRun.objects.create(
            session=other_session,
            job=other_job,
            source=JobRun.SOURCE_RECON,
            current_beat=1,
        )
        approach = JobApproach.objects.create(
            job=other_job,
            key="dock",
            label="Dock",
            roll_stat="agility",
            base_difficulty=10,
        )

        response = self.client.post(
            reverse("job_run_beat_1", kwargs={"run_id": other_run.id}),
            {"approach": approach.key},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 403)

    def test_job_contact_start_happy_path_sets_contact_source(self):
        job = self._make_job(key="jobs__contact-job")
        contact = Contact.objects.create(key="carla", name="Carla", description="")
        offer = ContactJobOffer.objects.create(
            key="carla_contact_job",
            contact=contact,
            job=job,
            scene=self.scene,
            cooldown_turns=0,
        )

        response = self.client.post(
            reverse("job_contact_start", kwargs={"offer_id": offer.id}),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        run = JobRun.objects.get(session=self.session, contact_offer=offer)
        self.assertEqual(run.source, JobRun.SOURCE_CONTACT)
        self.assertEqual(run.recon_tier, RECON_TIER_HIGH)

    @patch("game.services.jobs.random.uniform", return_value=1.0)
    @patch("game.services.jobs.random.randint", return_value=100)
    def test_job_run_resolve_happy_path_completes_run(self, _mock_randint, _mock_uniform):
        job = self._make_job(key="jobs__resolve")
        run = JobRun.objects.create(
            session=self.session,
            job=job,
            source=JobRun.SOURCE_RECON,
            current_beat=3,
            status=JobRun.STATUS_ACTIVE,
        )

        response = self.client.post(
            reverse("job_run_resolve", kwargs={"run_id": run.id}),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        run.refresh_from_db()
        self.session.stats.refresh_from_db()
        self.assertEqual(run.status, JobRun.STATUS_COMPLETED)
        self.assertEqual(self.session.stats.cash, 90)

    def test_job_run_beat_2_missing_action_returns_400(self):
        job = self._make_job(key="jobs__beat2")
        run = JobRun.objects.create(
            session=self.session,
            job=job,
            source=JobRun.SOURCE_RECON,
            current_beat=2,
        )
        approach = JobApproach.objects.create(
            job=job,
            key="roof",
            label="Roof",
            roll_stat="agility",
            base_difficulty=10,
        )
        JobBeatVariant.objects.create(
            job=job,
            beat_number=2,
            key="act",
            title="Act",
            approach=approach,
            requires_roll=False,
        )

        response = self.client.post(
            reverse("job_run_beat_2", kwargs={"run_id": run.id}),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 400)
