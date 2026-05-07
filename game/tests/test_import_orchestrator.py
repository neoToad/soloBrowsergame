from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from django.test import TestCase

from game.services.importers.orchestrator import detect_import_type, import_single_source
from game.services.importers.types import ImportResult, ImportType


class ImportOrchestratorTests(TestCase):
    def test_detect_import_type_returns_enum_values(self):
        self.assertEqual(detect_import_type({"items": []}), ImportType.ITEMS)
        self.assertEqual(detect_import_type({"enemies": []}), ImportType.ENEMIES_CONTACTS)
        self.assertEqual(detect_import_type({"contacts": []}), ImportType.ENEMIES_CONTACTS)
        self.assertEqual(detect_import_type({"hubs": []}), ImportType.HUBS)
        self.assertEqual(detect_import_type({"gangs": []}), ImportType.WORLD)
        self.assertEqual(detect_import_type({"quest": {}}), ImportType.QUEST)
        self.assertIsNone(detect_import_type({"unknown": []}))

    def test_import_single_source_uses_registry_handler(self):
        with TemporaryDirectory() as tmp_dir:
            yaml_path = Path(tmp_dir) / "items.yaml"
            yaml_path.write_text("items: []\n", encoding="utf-8")

            mock_handler = Mock(return_value=ImportResult())
            with patch.dict(
                "game.services.importers.orchestrator.IMPORT_HANDLERS",
                {ImportType.ITEMS: mock_handler},
                clear=False,
            ):
                result = import_single_source(str(yaml_path), expected_type=ImportType.ITEMS)

        self.assertIsInstance(result, ImportResult)
        mock_handler.assert_called_once_with({"items": []})
