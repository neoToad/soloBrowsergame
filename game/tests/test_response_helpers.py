import json

from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from game.presentation.responses import (
    attach_triggers,
    empty_response,
    error_response,
    redirect_or_htmx,
)


class ResponseHelpersTest(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_redirect_or_htmx_returns_fragment_for_htmx_request(self):
        request = self.factory.post("/game/choose/1/", HTTP_HX_REQUEST="true")

        response = redirect_or_htmx(
            request,
            redirect_name="game_hub",
            template_name="game/partials/scene_error.html",
            context={"error_message": "Denied", "error_status": 403},
            status=403,
        )

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'id="scene-panel"', status_code=403)
        self.assertContains(response, "Denied", status_code=403)

    def test_redirect_or_htmx_redirects_for_non_htmx_request(self):
        request = self.factory.post("/game/choose/1/")

        response = redirect_or_htmx(
            request,
            redirect_name="game_hub",
            template_name="game/partials/scene_error.html",
            context={"error_message": "Ignored", "error_status": 200},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("game_hub"))

    def test_error_response_htmx_attaches_default_trigger(self):
        request = self.factory.post("/game/choose/1/", HTTP_HX_REQUEST="true")

        response = error_response(request, message="Nope", status=403)

        self.assertEqual(response.status_code, 403)
        triggers = json.loads(response.headers["HX-Trigger"])
        self.assertEqual(
            triggers,
            {"app.error": {"message": "Nope", "status": 403}},
        )

    def test_error_response_htmx_uses_custom_triggers(self):
        request = self.factory.post("/game/choose/1/", HTTP_HX_REQUEST="true")
        custom_triggers = {"custom.event": {"value": 1}}

        response = error_response(
            request,
            message="Nope",
            status=403,
            triggers=custom_triggers,
        )

        triggers = json.loads(response.headers["HX-Trigger"])
        self.assertEqual(triggers, custom_triggers)

    def test_error_response_non_htmx_renders_full_template_with_merged_context(self):
        request = self.factory.get("/game/")

        response = error_response(
            request,
            message="Original",
            status=409,
            context={"error_message": "Overridden", "error_status": 418},
        )

        self.assertEqual(response.status_code, 409)
        self.assertContains(response, "[ REQUEST FAILED ]", status_code=409)
        self.assertContains(response, "Overridden", status_code=409)
        self.assertContains(response, "Status 418", status_code=409)

    def test_empty_response_returns_empty_body_with_status(self):
        response = empty_response(status=204)

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")

    def test_empty_response_attaches_triggers_when_provided(self):
        triggers = {"toast": {"level": "info"}}

        response = empty_response(status=202, triggers=triggers)

        self.assertEqual(response.status_code, 202)
        self.assertEqual(json.loads(response.headers["HX-Trigger"]), triggers)

    def test_attach_triggers_is_noop_when_triggers_none(self):
        response = empty_response(status=200)

        returned = attach_triggers(response, triggers=None)

        self.assertIs(returned, response)
        self.assertNotIn("HX-Trigger", response.headers)
