from django.core.management.base import BaseCommand

from game.services.importers.orchestrator import import_single_source


class Command(BaseCommand):
    help = "Import items from a YAML file"

    def add_arguments(self, parser):
        parser.add_argument("yaml_path", type=str, help="Path to the items YAML file")

    def handle(self, *args, **options):
        result = import_single_source(options["yaml_path"], expected_type="items")
        for warning in result.warnings:
            self.stdout.write(self.style.WARNING(f"WARNING: {warning}"))
        self.stdout.write(self.style.SUCCESS("Item import complete."))
