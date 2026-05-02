from django.core.management.base import BaseCommand

from game.services.quest_export import (
    build_quest_export_payload,
    default_quest_export_path,
    render_quest_yaml,
)


class Command(BaseCommand):
    help = "Export a single quest to canonical YAML"

    def add_arguments(self, parser):
        parser.add_argument("quest_key", type=str, help="Quest key to export")
        parser.add_argument(
            "--out",
            default=None,
            help="Output path for YAML. Defaults to yaml_files/quests/<arc|misc>/<quest_key>.yaml",
        )

    def handle(self, *args, **options):
        payload = build_quest_export_payload(options["quest_key"])
        out_path = options["out"] or str(default_quest_export_path(payload))
        output = render_quest_yaml(payload)
        with open(out_path, "w", encoding="utf-8") as handle:
            handle.write(output)
        self.stdout.write(
            self.style.SUCCESS(
                f"Exported quest {payload['quest']['key']} to {out_path} "
                f"(scenes={len(payload['scenes'])})."
            )
        )
