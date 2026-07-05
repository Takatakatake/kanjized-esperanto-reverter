#!/usr/bin/env python3
"""Build the 2-column snippet CSV from the bundled reverter CSV.

The snippet CSV (エスペラント語根-漢字対応表_スニペット用最小限.csv) is the app's second
dictionary choice, and its UI label promises conversion results identical to the main
PEJVO/PIV dictionary. This tool derives it from data/pejvo_piv_20260620_reverter.csv —
same rows, same order, esperanto+kanji columns only — in the exact committed byte
format: UTF-8 without BOM, CRLF line endings, no header, no quoting.

Run it whenever the main CSV is regenerated (dictionary revision rN) and commit both
files together; tools/check_dictionary_sync.py fails CI if they drift.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
ROOT = TOOLS_DIR.parent
DEFAULT_MAIN_CSV = ROOT / "data" / "pejvo_piv_20260620_reverter.csv"
DEFAULT_SNIPPET_CSV = ROOT / "エスペラント語根-漢字対応表_スニペット用最小限.csv"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_MAIN_CSV, help="source 5-column reverter CSV")
    parser.add_argument("--out", type=Path, default=DEFAULT_SNIPPET_CSV, help="snippet CSV to (re)write")
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"ERROR: reverter CSV was not found: {args.csv}", file=sys.stderr)
        return 1

    with args.csv.open(encoding="utf-8", newline="") as handle:
        rows = [(row["esperanto"], row["kanji"]) for row in csv.DictReader(handle)]

    with args.out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\r\n")
        writer.writerows(rows)

    print(f"wrote {len(rows)} rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
