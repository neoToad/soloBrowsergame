from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase

from game.models import Choice, Contact, ContactJobOffer, Job, Quest, Scene
from game.services import quest_builder


class FlagValidationModelTests(TestCase):
    def setUp(self):
        self.quest = Quest.objects.create(key="flag-val-quest", title="Flag Validation", description="")
        self.scene = Scene.objects.create(
            quest=self.quest,
            key="flag-val-quest__start",
            title="Start",
            body="",
            scene_type="normal",
        )
        self.target_scene = Scene.objects.create(
            quest=self.quest,
            key="flag-val-quest__target",
            title="Target",
            body="",
            scene_type="normal",
        )
        self.hub_scene = Scene.objects.create(
            key="flag-val-quest__hub",
            title="Hub",
            body="",
            scene_type="hub",
        )

    def test_choice_clean_accepts_registered_and_dynamic_flags(self):
        choice = Choice(
            scene=self.scene,
            label="Go",
            target_scene=self.target_scene,
            set_flag_name="box_clean_exit",
            clear_flag_name="approach_alley_failed",
        )
        choice.full_clean()

    def test_choice_clean_rejects_unregistered_flag(self):
        choice = Choice(
            scene=self.scene,
            label="Go",
            target_scene=self.target_scene,
            set_flag_name="bad flag with spaces",
        )
        with self.assertRaises(ValidationError):
            choice.full_clean()

    def test_choice_clean_allows_unchanged_legacy_flag(self):
        choice = Choice.objects.create(
            scene=self.scene,
            label="Legacy",
            target_scene=self.target_scene,
            set_flag_name="test",
        )
        Choice.objects.filter(pk=choice.pk).update(set_flag_name="legacy bad flag")
        choice.refresh_from_db()
        choice.label = "Legacy Edited"
        choice.full_clean()

    def test_contact_offer_required_flag_validation(self):
        contact = Contact.objects.create(key="flag-contact", name="Flag Contact")
        job = Job.objects.create(key="flag-job", title="Flag Job")
        offer = ContactJobOffer(
            key="flag-offer",
            contact=contact,
            job=job,
            scene=self.hub_scene,
            required_flag="ran_flag_job_3x",
        )
        offer.full_clean()
        offer.required_flag = "invalid required flag"
        with self.assertRaises(ValidationError):
            offer.full_clean()


class FlagValidationServiceTests(TestCase):
    def setUp(self):
        self.quest = Quest.objects.create(key="qb-flag-quest", title="QB", description="")
        self.scene = Scene.objects.create(
            quest=self.quest,
            key="qb-flag-quest__start",
            title="Start",
            body="",
            scene_type="normal",
        )
        self.target = Scene.objects.create(
            quest=self.quest,
            key="qb-flag-quest__target",
            title="Target",
            body="",
            scene_type="normal",
        )

    def test_quest_builder_create_choice_rejects_invalid_flag_name(self):
        with self.assertRaises(ValueError):
            quest_builder.create_choice(
                self.scene.id,
                {
                    "label": "Bad Flag",
                    "routing_type": "direct",
                    "target_scene": str(self.target.id),
                    "set_flag_name": "not valid",
                },
            )


class ReportInvalidFlagsCommandTests(TestCase):
    def test_report_invalid_flags_command_outputs_invalid_rows(self):
        quest = Quest.objects.create(key="flag-report-quest", title="Report", description="")
        scene = Scene.objects.create(
            quest=quest,
            key="flag-report-quest__start",
            title="Start",
            body="",
            scene_type="normal",
        )
        target = Scene.objects.create(
            quest=quest,
            key="flag-report-quest__target",
            title="Target",
            body="",
            scene_type="normal",
        )
        choice = Choice.objects.create(scene=scene, label="Go", target_scene=target, set_flag_name="test")
        Choice.objects.filter(pk=choice.pk).update(set_flag_name="invalid choice flag")

        contact = Contact.objects.create(key="flag-report-contact", name="Report Contact")
        job = Job.objects.create(key="flag-report-job", title="Report Job")
        offer = ContactJobOffer.objects.create(
            key="flag-report-offer",
            contact=contact,
            job=job,
            scene=scene,
            required_flag="test",
        )
        ContactJobOffer.objects.filter(pk=offer.pk).update(required_flag="invalid offer flag")

        out = StringIO()
        call_command("report_invalid_flags", stdout=out)
        output = out.getvalue()
        self.assertIn("Choice#", output)
        self.assertIn("ContactJobOffer#", output)
        self.assertIn("Found 2 row(s) with invalid flag names.", output)
