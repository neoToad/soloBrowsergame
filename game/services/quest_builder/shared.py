from django.core.exceptions import ValidationError


CARD_WIDTH = 220
CARD_HEIGHT = 100
GRID_START_X = 60
GRID_START_Y = 60
GRID_X_GAP = 280
GRID_Y_GAP = 200
CANVAS_PADDING = 120
PARALLEL_ARROW_SPACING = 12


def raise_authoring_validation_error(exc: ValidationError) -> None:
    message_dict = getattr(exc, "message_dict", None)
    if message_dict:
        details = "; ".join(
            f"{field}: {', '.join(messages)}" for field, messages in message_dict.items()
        )
    else:
        details = "; ".join(exc.messages)
    raise ValueError(details) from exc
