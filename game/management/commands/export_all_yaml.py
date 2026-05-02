from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from game.services.domain_export import (
    build_contacts_payload,
    build_enemies_contacts_payload,
    build_enemies_payload,
    build_gangs_payload,
    build_hubs_payload,
    build_items_payload,
    build_properties_payload,
    build_territories_payload,
    build_world_payload,
    default_domain_export_paths,
    render_yaml,
)


VALID_TYPES = {"items", "enemies", "contacts", "hubs", "gangs", "properties", "territories"}


class Command(BaseCommand):
    help = "Export non-quest game YAML files (items, hubs, enemies/contacts, world data)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--out-dir",
            default="yaml_files",
            help="Base output directory (default: yaml_files)",
        )
        parser.add_argument(
            "--types",
            default="items,enemies,contacts,hubs,gangs,properties,territories",
            help="Comma-separated types to export",
        )
        parser.add_argument(
            "--combined-world",
            action="store_true",
            help="Write a single world.yaml containing gangs/properties/territories",
        )
        parser.add_argument(
            "--combined-enemies-contacts",
            action="store_true",
            help="Write a single enemies_and_contacts.yaml containing enemies + contacts",
        )

    def handle(self, *args, **options):
        requested_types = {part.strip() for part in options["types"].split(",") if part.strip()}
        invalid_types = sorted(requested_types - VALID_TYPES)
        if invalid_types:
            raise CommandError(f"Unsupported export type(s): {', '.join(invalid_types)}")

        paths = default_domain_export_paths(
            options["out_dir"],
            combined_world=options["combined_world"],
            combined_enemies_contacts=options["combined_enemies_contacts"],
        )

        exports: list[tuple[str, str]] = []
        if "items" in requested_types:
            exports.append(("items", render_yaml(build_items_payload())))
        if "hubs" in requested_types:
            exports.append(("hubs", render_yaml(build_hubs_payload())))

        wants_enemies_or_contacts = "enemies" in requested_types or "contacts" in requested_types
        if wants_enemies_or_contacts:
            if options["combined_enemies_contacts"]:
                exports.append(("enemies_contacts", render_yaml(build_enemies_contacts_payload())))
            else:
                if "enemies" in requested_types:
                    exports.append(("enemies", render_yaml(build_enemies_payload())))
                if "contacts" in requested_types:
                    exports.append(("contacts", render_yaml(build_contacts_payload())))

        wants_world_types = {"gangs", "properties", "territories"} & requested_types
        if wants_world_types:
            if options["combined_world"]:
                exports.append(("world", render_yaml(build_world_payload())))
            else:
                if "gangs" in requested_types:
                    exports.append(("gangs", render_yaml(build_gangs_payload())))
                if "properties" in requested_types:
                    exports.append(("properties", render_yaml(build_properties_payload())))
                if "territories" in requested_types:
                    exports.append(("territories", render_yaml(build_territories_payload())))

        for export_type, output in exports:
            out_path = paths[export_type]
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(output, encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Exported {export_type}: {out_path}"))
