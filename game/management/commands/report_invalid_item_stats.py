from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand

from game.models.items import Item


class Command(BaseCommand):
    help = "Report items with invalid effect_stat/passive_stat targets."

    def handle(self, *args, **options):
        invalid_count = 0
        for item in Item.objects.all().order_by("key"):
            try:
                item.full_clean()
            except ValidationError as exc:
                invalid_count += 1
                self.stdout.write(self.style.WARNING(f"{item.key}: {exc.message_dict}"))

        if invalid_count:
            self.stdout.write(self.style.WARNING(f"Found {invalid_count} item(s) with invalid stat targets."))
            return
        self.stdout.write(self.style.SUCCESS("No invalid item stat targets found."))
