#!/usr/bin/env python3
"""Check that the bundled reverter CSV matches the Monaco all.json source."""

from __future__ import annotations

import argparse
import contextlib
import csv
import io
import json
import logging
import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
ROOT = TOOLS_DIR.parent
DEFAULT_CSV = ROOT / "data" / "pejvo_piv_20260620_reverter.csv"
DEFAULT_MONACO_ALL = ROOT.parent / "kanji-esperanto-monaco" / "all.json"
EXPECTED_SAMPLE_OUTPUT = (
    "kiam okcidento renkontas orienton kaj surmetas orientan veston, "
    "unu sola lingvo akiras du aspektojn — ambaŭ belajn —, kaj naskiĝas nova kompreno."
)

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TOOLS_DIR))

logging.getLogger("streamlit.runtime.caching.cache_data_api").setLevel(logging.ERROR)

from build_reverter_dictionary_from_all_json import rows_from_all_json  # noqa: E402
with contextlib.redirect_stderr(io.StringIO()):
    from esperanto_converter import (  # noqa: E402
        build_mapping_index,
        convert_kanji_esperanto_to_alphabet,
        read_assignment_csv,
        sample_text,
    )


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize_row(row: dict) -> dict[str, str]:
    fields = ["esperanto", "kanji", "priority", "source_root", "source_line"]
    return {field: str(row.get(field, "")) for field in fields}


def check_csv_sync(monaco_all_path: Path, csv_path: Path) -> list[str]:
    data = json.loads(monaco_all_path.read_text(encoding="utf-8"))
    expected = [normalize_row(row) for row in rows_from_all_json(data)]
    actual = [normalize_row(row) for row in load_csv_rows(csv_path)]

    errors: list[str] = []
    if len(expected) != len(actual):
        errors.append(f"row count differs: expected {len(expected)}, actual {len(actual)}")

    for index, (expected_row, actual_row) in enumerate(zip(expected, actual), start=2):
        if expected_row != actual_row:
            errors.append(
                "first differing CSV row "
                f"{index}: expected {expected_row}, actual {actual_row}"
            )
            break
    return errors


def check_sample_conversion(csv_path: Path) -> list[str]:
    df = read_assignment_csv(csv_path)
    mapping = build_mapping_index(df)
    converted = convert_kanji_esperanto_to_alphabet(sample_text(), mapping)
    if converted != EXPECTED_SAMPLE_OUTPUT:
        return [f"sample conversion differs: expected {EXPECTED_SAMPLE_OUTPUT!r}, actual {converted!r}"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--monaco-all", type=Path, default=DEFAULT_MONACO_ALL)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    args = parser.parse_args()

    errors: list[str] = []
    if not args.monaco_all.exists():
        errors.append(f"Monaco all.json was not found: {args.monaco_all}")
    if not args.csv.exists():
        errors.append(f"reverter CSV was not found: {args.csv}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    errors.extend(check_csv_sync(args.monaco_all, args.csv))
    errors.extend(check_sample_conversion(args.csv))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(
            "Run: python3 tools/build_reverter_dictionary_from_all_json.py "
            f"{args.monaco_all} {args.csv}",
            file=sys.stderr,
        )
        return 1

    print(f"OK: {args.csv} matches {args.monaco_all}")
    print("OK: sample conversion matches the expected current sentence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
