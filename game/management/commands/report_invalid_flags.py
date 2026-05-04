from django.core.management.base import BaseCommand

from game.models import Choice
from game.services.flag_registry import is_valid_flag_name, normalize_flag_name


class Command(BaseCommand):
    help = "Report choices with invalid flag names."

    def handle(self, *args, **options):
        invalid_count = 0

        for choice in Choice.objects.all().order_by("id"):
            invalid_fields = {}
            for field in ("set_flag_name", "clear_flag_name"):
                raw = getattr(choice, field)
                normalized = normalize_flag_name(raw, allow_blank=True)
                if normalized and not is_valid_flag_name(normalized):
                    invalid_fields[field] = normalized
            if invalid_fields:
                invalid_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Choice#{choice.pk} ({choice.scene_id} -> {choice.label}): {invalid_fields}"
                    )
                )

        if invalid_count:
            self.stdout.write(self.style.WARNING(f"Found {invalid_count} row(s) with invalid flag names."))
            return
        self.stdout.write(self.style.SUCCESS("No invalid flag names found."))
