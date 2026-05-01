from django.core.management.base import BaseCommand

from game.services.importers.orchestrator import import_single_source


class Command(BaseCommand):
    help = "Import enemies and contacts from a YAML file"

    def add_arguments(self, parser):
        parser.add_argument(
            "yaml_path",
            type=str,
            help="Path to an enemies/contacts YAML file (supports enemies-only, contacts-only, or both)",
        )

    def handle(self, *args, **options):
        result = import_single_source(options["yaml_path"], expected_type="enemies_contacts")
        for warning in result.warnings:
            self.stdout.write(self.style.WARNING(f"WARNING: {warning}"))
        self.stdout.write(self.style.SUCCESS("Enemies/contacts import complete."))
