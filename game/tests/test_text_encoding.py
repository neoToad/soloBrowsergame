from pathlib import Path

from django.test import SimpleTestCase


class TextEncodingGuardTest(SimpleTestCase):
    def test_no_common_mojibake_signatures(self):
        root = Path(__file__).resolve().parents[2]
        targets = [root / "game", root / "templates", root / ".docs"]
        extensions = {".py", ".html", ".md", ".txt", ".yaml", ".yml"}
        bad_tokens = [
            bytes((0xE2, 0x80, 0x94)).decode("latin-1"),  # em dash mojibake
            bytes((0xE2, 0x80, 0x93)).decode("latin-1"),  # en dash mojibake
            bytes((0xE2, 0x86, 0x92)).decode("latin-1"),  # right arrow mojibake
            bytes((0xE2, 0x80)).decode("latin-1"),        # broken unicode prefix
            bytes((0xC3, 0x97)).decode("latin-1"),        # multiplication sign mojibake
            bytes((0xC3, 0xA2)).decode("latin-1"),        # common bad lead-in
            bytes((0xE2, 0x94, 0x80)).decode("latin-1"),  # box drawing line mojibake
            bytes((0xE2, 0x89, 0xA5)).decode("latin-1"),  # >= mojibake
            bytes((0xE2, 0x89, 0xA4)).decode("latin-1"),  # <= mojibake
        ]

        findings = []
        for base in targets:
            for path in base.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in extensions:
                    continue
                text = path.read_text(encoding="utf-8")
                for token in bad_tokens:
                    if token in text:
                        findings.append(f"{path.relative_to(root)} contains {token!r}")

        self.assertEqual(findings, [], "\n".join(findings))
