import json
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
from game.tests.factories import bootstrap_game_session


class JobEndpointsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.session = bootstrap_game_session(self.client)
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

    def _wire_single_path_job(self, job):
        approach = JobApproach.objects.create(
            job=job,
            key="alley",
            label="Alley",
            roll_stat="agility",
            base_difficulty=10,
        )
        JobBeatVariant.objects.create(
            job=job,
            beat_number=2,
            key="push",
            title="Push Through",
            approach=approach,
            requires_roll=False,
        )
        return approach

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
        body = response.content.decode()
        self.assertIn("[ DISTRICT TARGETS ]", body)
        self.assertIn("[ ACTIVE RUN ]", body)

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
        triggers = json.loads(response.headers.get("HX-Trigger", "{}"))
        self.assertIn("app.error", triggers)
        self.assertIn("cooldown", response.content.decode().lower())

    @patch("game.services.jobs_rolls.roll_d20", return_value=20)
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

    def test_scene_detail_hub_renders_jobs_and_contacts_panels(self):
        job = self._make_job(key="jobs__scene-detail")
        contact = Contact.objects.create(key="scene-contact", name="Scene Contact", description="")
        ContactJobOffer.objects.create(
            key="scene-contact-offer",
            contact=contact,
            job=job,
            scene=self.scene,
            cooldown_turns=0,
        )

        response = self.client.get(reverse("scene_detail", kwargs={"scene_key": self.scene.key}))

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("[ DISTRICT TARGETS ]", body)
        self.assertIn("[ CONTACTS ]", body)

    @patch("game.services.jobs_rewards.random.uniform", return_value=1.0)
    @patch("game.services.jobs_rewards.random.randint", return_value=100)
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

    @patch("game.services.jobs_rewards.random.uniform", return_value=1.0)
    @patch("game.services.jobs_rewards.random.randint", return_value=100)
    @patch("game.services.jobs_rolls.roll_d20", return_value=20)
    def test_full_replay_loop_allows_replay_after_cooldown(
        self, _mock_roll, _mock_randint, _mock_uniform
    ):
        job = self._make_job(key="jobs__replay", base_cooldown_turns=2)
        approach = self._wire_single_path_job(job)

        response = self.client.post(
            reverse("job_recon_commit", kwargs={"job_key": job.key}),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        run = JobRun.objects.get(session=self.session, job=job, status=JobRun.STATUS_ACTIVE)

        response = self.client.post(
            reverse("job_run_beat_1", kwargs={"run_id": run.id}),
            {"approach": approach.key},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("job_run_beat_2", kwargs={"run_id": run.id}),
            {"action": "push"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("job_run_resolve", kwargs={"run_id": run.id}),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        run.refresh_from_db()
        self.assertEqual(run.status, JobRun.STATUS_COMPLETED)

        state = PlayerJobState.objects.get(session=self.session, job=job)
        self.assertEqual(state.run_count, 1)

        response = self.client.post(
            reverse("job_recon_commit", kwargs={"job_key": job.key}),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("cooldown", response.content.decode().lower())

        response = self.client.post(
            reverse("job_recon_walk_away", kwargs={"job_key": job.key}),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("job_recon_commit", kwargs={"job_key": job.key}),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            JobRun.objects.filter(
                session=self.session,
                job=job,
                status=JobRun.STATUS_ACTIVE,
            ).count(),
            1,
        )

    @patch("game.services.jobs_rewards.random.uniform", return_value=1.0)
    @patch("game.services.jobs_rewards.random.randint", return_value=100)
    @patch("game.services.jobs_rolls.roll_d20", return_value=20)
    def test_contact_offer_unlock_and_offer_cooldown_are_enforced_independently(
        self, _mock_roll, _mock_randint, _mock_uniform
    ):
        job = self._make_job(
            key="jobs__contact_unlock",
            base_cooldown_turns=2,
        )
        approach = self._wire_single_path_job(job)
        contact = Contact.objects.create(key="dock-foreman", name="Dock Foreman", description="")
        offer = ContactJobOffer.objects.create(
            key="dock-foreman-offer",
            contact=contact,
            job=job,
            scene=self.scene,
            min_run_count=1,
            cooldown_turns=4,
        )

        response = self.client.post(
            reverse("job_contact_start", kwargs={"offer_id": offer.id}),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("min run count", response.content.decode().lower())

        response = self.client.post(
            reverse("job_recon_commit", kwargs={"job_key": job.key}),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        recon_run = JobRun.objects.get(session=self.session, job=job, status=JobRun.STATUS_ACTIVE)

        self.assertEqual(
            self.client.post(
                reverse("job_run_beat_1", kwargs={"run_id": recon_run.id}),
                {"approach": approach.key},
                HTTP_HX_REQUEST="true",
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                reverse("job_run_beat_2", kwargs={"run_id": recon_run.id}),
                {"action": "push"},
                HTTP_HX_REQUEST="true",
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                reverse("job_run_resolve", kwargs={"run_id": recon_run.id}),
                HTTP_HX_REQUEST="true",
            ).status_code,
            200,
        )

        response = self.client.post(
            reverse("job_contact_start", kwargs={"offer_id": offer.id}),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("cooldown", response.content.decode().lower())

        self.assertEqual(
            self.client.post(
                reverse("job_recon_walk_away", kwargs={"job_key": job.key}),
                HTTP_HX_REQUEST="true",
            ).status_code,
            200,
        )
        response = self.client.post(
            reverse("job_contact_start", kwargs={"offer_id": offer.id}),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        contact_run = JobRun.objects.get(
            session=self.session,
            contact_offer=offer,
            status=JobRun.STATUS_ACTIVE,
        )
        self.assertEqual(contact_run.source, JobRun.SOURCE_CONTACT)

        self.assertEqual(
            self.client.post(
                reverse("job_run_beat_1", kwargs={"run_id": contact_run.id}),
                {"approach": approach.key},
                HTTP_HX_REQUEST="true",
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                reverse("job_run_beat_2", kwargs={"run_id": contact_run.id}),
                {"action": "push"},
                HTTP_HX_REQUEST="true",
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                reverse("job_run_resolve", kwargs={"run_id": contact_run.id}),
                HTTP_HX_REQUEST="true",
            ).status_code,
            200,
        )

        self.assertEqual(
            self.client.post(
                reverse("job_recon_walk_away", kwargs={"job_key": job.key}),
                HTTP_HX_REQUEST="true",
            ).status_code,
            200,
        )
        response = self.client.post(
            reverse("job_contact_start", kwargs={"offer_id": offer.id}),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("cooldown", response.content.decode().lower())

        self.assertEqual(
            self.client.post(
                reverse("job_recon_walk_away", kwargs={"job_key": job.key}),
                HTTP_HX_REQUEST="true",
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                reverse("job_recon_walk_away", kwargs={"job_key": job.key}),
                HTTP_HX_REQUEST="true",
            ).status_code,
            200,
        )
        response = self.client.post(
            reverse("job_contact_start", kwargs={"offer_id": offer.id}),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)


