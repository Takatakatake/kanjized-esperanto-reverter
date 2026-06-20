#!/usr/bin/env python3
"""Build a reverter CSV from kanji-esperanto-monaco all.json."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


ESPERANTO_CARET_MAP = {
    "c": "ĉ",
    "g": "ĝ",
    "h": "ĥ",
    "j": "ĵ",
    "s": "ŝ",
    "u": "ŭ",
}


def to_unicode_esperanto_root(value: str, fallback: str = "") -> str:
    root = (value or fallback or "").strip().strip(",")
    if "," in root:
        parts = [part.strip() for part in root.split(",") if part.strip()]
        root = parts[0] if parts else root

    out = []
    i = 0
    while i < len(root):
        ch = root[i]
        if i + 1 < len(root) and root[i + 1] == "^":
            mapped = ESPERANTO_CARET_MAP.get(ch.lower())
            if mapped:
                out.append(mapped)
                i += 2
                continue
        out.append(ch)
        i += 1
    return "".join(out).lower()


def rows_from_all_json(data: dict) -> list[dict[str, object]]:
    rows = []
    for index, item in enumerate(data.get("items", [])):
        kanji = str(item.get("body", "")).strip()
        if not kanji:
            continue
        esperanto = to_unicode_esperanto_root(
            str(item.get("sourceRoot", "")),
            str(item.get("prefix", "")),
        )
        if not esperanto:
            continue
        priority = item.get("priority", index)
        try:
            priority = int(priority)
        except (TypeError, ValueError):
            priority = index
        rows.append(
            {
                "esperanto": esperanto,
                "kanji": kanji,
                "priority": priority,
                "source_root": str(item.get("sourceRoot", "")).strip(),
                "source_line": item.get("sourceLine", ""),
            }
        )

    rows.sort(key=lambda row: (-len(row["kanji"]), row["priority"], row["kanji"], row["esperanto"]))
    return rows


def write_rows(rows: list[dict[str, object]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["esperanto", "kanji", "priority", "source_root", "source_line"],
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "Usage: tools/build_reverter_dictionary_from_all_json.py <all.json> <out.csv>",
            file=sys.stderr,
        )
        return 2

    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    data = json.loads(in_path.read_text(encoding="utf-8"))
    rows = rows_from_all_json(data)
    write_rows(rows, out_path)

    print(f"wrote {len(rows)} rows to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
