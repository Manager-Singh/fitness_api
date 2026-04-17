"""Section 14.1 — daily HeightLedger writes must stay centralized."""

from pathlib import Path

from django.test import SimpleTestCase


class HeightLedgerWriterTests(SimpleTestCase):
    def test_only_spec_runtime_creates_height_ledger(self):
        root = Path(__file__).resolve().parents[2]
        offenders = []
        for path in root.rglob("*.py"):
            s = str(path)
            if "/venv/" in s or "migrations" in s or "users/tests/" in s:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "HeightLedger.objects.create" not in text:
                continue
            if s.endswith("users/spec_runtime.py"):
                continue
            offenders.append(s)
        self.assertEqual(
            offenders,
            [],
            msg="HeightLedger.objects.create found outside users/spec_runtime.py: " + repr(offenders),
        )
