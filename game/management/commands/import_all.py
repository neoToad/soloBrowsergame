from django.core.management.base import BaseCommand

from game.services.importers import import_all_sources


class Command(BaseCommand):
    help = "Import all game data YAML files from a directory (or explicit file paths)"

    def add_arguments(self, parser):
        parser.add_argument(
            "paths",
            nargs="*",
            default=["yaml_files"],
            help="Directories or YAML files to import (default: yaml_files/)",
        )

    def handle(self, *args, **options):
        result, buckets = import_all_sources(options["paths"])
        total = sum(len(entries) for entries in buckets.values())
        self.stdout.write(f"Found {total} importable file(s)")
        for import_type, entries in buckets.items():
            for file_path, _ in entries:
                self.stdout.write(f"  {import_type}: {file_path}")
        for warning in result.warnings:
            self.stdout.write(self.style.WARNING(f"WARNING: {warning}"))
        self.stdout.write(self.style.SUCCESS("All imports complete."))
