from django.core.management.base import BaseCommand

from game.services.export_game_state import export_game_state


class Command(BaseCommand):
    help = "Export content graph data for LLM authoring"

    def add_arguments(self, parser):
        parser.add_argument(
            "--out",
            default=None,
            help="Output path for export file. Defaults to exports/game_state.json (or .yaml with --yaml).",
        )
        parser.add_argument(
            "--include-scene-body",
            action="store_true",
            help="Include full Scene.body text in the export (off by default).",
        )
        parser.add_argument(
            "--yaml",
            action="store_true",
            help="Write YAML instead of JSON.",
        )

    def handle(self, *args, **options):
        use_yaml = options["yaml"]
        output_path = options["out"] or (
            "exports/game_state.yaml" if use_yaml else "exports/game_state.json"
        )
        include_scene_body = options["include_scene_body"]
        output_format = "yaml" if use_yaml else "json"
        payload = export_game_state(
            path=output_path,
            include_scene_body=include_scene_body,
            output_format=output_format,
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Exported game state to "
                f"{output_path} "
                f"(quests={payload['counts']['quests']}, "
                f"scenes={payload['counts']['scenes']}, "
                f"jobs={payload['counts']['jobs']})."
            )
        )
