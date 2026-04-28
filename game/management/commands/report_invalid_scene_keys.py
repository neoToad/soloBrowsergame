from django.core.management.base import BaseCommand
from django.utils.text import slugify

from game.models import Scene


class Command(BaseCommand):
    help = "Report quest scenes whose keys do not match {quest_key}__{scene_slug}; optionally fix them."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Rename invalid scene keys to the proposed convention key when no collision exists.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show proposed renames without applying them.",
        )

    def handle(self, *args, **options):
        should_fix = options["fix"]
        dry_run = options["dry_run"]
        invalid_count = 0
        fixed_count = 0
        conflict_count = 0

        scenes = Scene.objects.select_related("quest").order_by("id")
        for scene in scenes:
            if not scene.quest_id:
                continue
            expected_prefix = f"{scene.quest.key}__"
            expected_key = f"{expected_prefix}{slugify(scene.title)}"
            if scene.key.startswith(expected_prefix):
                suffix = scene.key[len(expected_prefix):]
                if suffix and slugify(suffix) == suffix:
                    continue

            invalid_count += 1
            self.stdout.write(
                self.style.WARNING(
                    f"Scene#{scene.pk} current='{scene.key}' expected_prefix='{expected_prefix}' proposed='{expected_key}'"
                )
            )

            if not should_fix:
                continue

            if scene.key == expected_key:
                continue

            if Scene.objects.exclude(pk=scene.pk).filter(key=expected_key).exists():
                conflict_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"  conflict: cannot rename Scene#{scene.pk} to '{expected_key}' because it already exists."
                    )
                )
                continue

            if dry_run:
                self.stdout.write(self.style.WARNING(f"  dry-run: would rename to '{expected_key}'"))
                continue

            old_key = scene.key
            scene.key = expected_key
            scene.clean()
            scene.save(update_fields=["key"])
            fixed_count += 1
            self.stdout.write(self.style.SUCCESS(f"  renamed: '{old_key}' -> '{scene.key}'"))

        if should_fix:
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        f"Found {invalid_count} invalid scene key(s). Dry-run only; no changes applied."
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Found {invalid_count} invalid scene key(s); fixed {fixed_count}; conflicts {conflict_count}."
                    )
                )
            return

        if invalid_count:
            self.stdout.write(self.style.WARNING(f"Found {invalid_count} invalid scene key(s)."))
            return
        self.stdout.write(self.style.SUCCESS("No invalid scene keys found."))
