import json

from django.http import HttpResponse
from django.shortcuts import redirect, render


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


def attach_triggers(response, triggers=None):
    if not triggers:
        return response
    response["HX-Trigger"] = json.dumps(triggers)
    return response


def dual_event_triggers(*, camel_event, camel_payload, dot_event=None, dot_payload=None):
    return {
        camel_event: camel_payload,
        (dot_event or _camel_to_dot_event(camel_event)): (
            dot_payload if dot_payload is not None else camel_payload
        ),
    }


def _camel_to_dot_event(name):
    chars = []
    for char in name:
        if char.isupper():
            chars.append(".")
            chars.append(char.lower())
        else:
            chars.append(char)
    return "".join(chars).lstrip(".")


def render_htmx_fragment(request, template_name, context, *, status=200, triggers=None):
    response = render(request, template_name, context, status=status)
    return attach_triggers(response, triggers)


def redirect_or_htmx(
    request,
    *,
    redirect_name,
    redirect_kwargs=None,
    template_name,
    context,
    status=200,
    triggers=None,
):
    if is_htmx(request):
        return render_htmx_fragment(
            request,
            template_name,
            context,
            status=status,
            triggers=triggers,
        )
    return redirect(redirect_name, **(redirect_kwargs or {}))


def error_response(
    request,
    *,
    message,
    status=400,
    htmx_template="game/partials/scene_error.html",
    full_template="game/error.html",
    context=None,
    triggers=None,
):
    payload = {"error_message": message, "error_status": status}
    if context:
        payload.update(context)
    if is_htmx(request):
        return render_htmx_fragment(
            request,
            htmx_template,
            payload,
            status=status,
            triggers=triggers or {"app.error": {"message": message, "status": status}},
        )
    return render(request, full_template, payload, status=status)


def empty_response(*, status=200, triggers=None):
    response = HttpResponse("", status=status)
    return attach_triggers(response, triggers)
