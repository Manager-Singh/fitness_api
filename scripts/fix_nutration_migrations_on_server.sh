#!/usr/bin/env bash
# Run on production from the Django project root (directory containing manage.py).
set -euo pipefail

MIG_DIR="nutration/migrations"
FILE_0015="${MIG_DIR}/0015_modulefood_adult_score.py"
FILE_0013="${MIG_DIR}/0013_alter_module_options_module_sort_order.py"

cd "$(dirname "$0")/.."

if [[ ! -f manage.py ]]; then
  echo "Error: run from repo root (manage.py not found)." >&2
  exit 1
fi

# Remove obsolete split migrations if present.
rm -f "${MIG_DIR}/0013_module_sort_order.py" "${MIG_DIR}/0014_alter_module_options.py"

if [[ ! -f "$FILE_0013" ]]; then
  echo "Error: missing $FILE_0013 — git pull the latest main first." >&2
  exit 1
fi

if [[ ! -f "$FILE_0015" ]]; then
  echo "Error: missing $FILE_0015" >&2
  exit 1
fi

# Ensure 0015 depends on the combined 0013 (not deleted 0014).
python3 <<'PY'
from pathlib import Path

path = Path("nutration/migrations/0015_modulefood_adult_score.py")
text = path.read_text()
want = '("nutration", "0013_alter_module_options_module_sort_order")'
if want not in text:
    if "0014_alter_module_options" in text:
        text = text.replace(
            '("nutration", "0014_alter_module_options")',
            want,
        )
        path.write_text(text)
        print("Patched 0015 dependency -> 0013_alter_module_options_module_sort_order")
    else:
        raise SystemExit("0015 does not reference 0014 or 0013_alter; inspect manually.")
else:
    print("0015 dependency already correct.")
PY

echo "Running migrate..."
python manage.py migrate nutration
python manage.py makemigrations --check
echo "Done."
