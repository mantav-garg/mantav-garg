"""
Runs every registered data-source parser, saves each to CSV, then renders
an isometric SVG - in every theme registered in svg_generator.PALETTES -
for every dataset.

Usernames are set as variables below, no command-line args needed:
    python main.py

To add a new color theme, you don't need to touch this file at all: just
add an entry to PALETTES in svg_generator.py and it will automatically be
picked up here and rendered for every data source below.
"""

from __future__ import annotations

import csv
from pathlib import Path

from parsers import github_parser, leetcode_parser
from svg_generator import PALETTES, render_svg_from_csv

GITHUB_USERNAME = "mantav-garg"
LEETCODE_USERNAME = "MantavGarg"
DATA_DIR = Path("data")
OUTPUT_DIR = Path("output")
TRANSPARENT_BACKGROUND = False

THEMES = tuple(PALETTES.keys())
# ---------------------------------------------------------------------------
# Data source registry
#
# To add another data parser down the line:
#   1. Write parsers/<name>_parser.py with a fetch_<name>(username) function
#      that returns a list of (date, count) tuples.
#   2. Add an entry below pointing at it.
# That's it - CSV saving and SVG generation (both themes) happen
# automatically for every entry in this list.
# ---------------------------------------------------------------------------

DATA_SOURCES = [
    {
        "name": "github",
        "fetch": lambda: github_parser.fetch_github_contributions(GITHUB_USERNAME),
        "csv_path": DATA_DIR / "github_contributions.csv",
        "label": "TOTAL CONTRIBUTIONS",
    },
    {
        "name": "leetcode",
        "fetch": lambda: leetcode_parser.fetch_leetcode_submissions(LEETCODE_USERNAME),
        "csv_path": DATA_DIR / "leetcode_submissions.csv",
        "label": "TOTAL SUBMISSIONS",
    },
]


def save_csv(rows: list[tuple[str, int]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "count"])
        writer.writerows(rows)


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for source in DATA_SOURCES:
        name = source["name"]
        print(f"[{name}] fetching...")
        try:
            rows = source["fetch"]()
        except Exception as exc:
            print(f"[{name}] skipped: {exc}")
            continue

        save_csv(rows, source["csv_path"])
        print(f"[{name}] saved {len(rows)} rows -> {source['csv_path']}")

        for theme in THEMES:
            svg = render_svg_from_csv(
                source["csv_path"], theme, source["label"], transparent=TRANSPARENT_BACKGROUND
            )
            out_path = OUTPUT_DIR / f"{name}-{theme}.svg"
            out_path.write_text(svg, encoding="utf-8")
            print(f"[{name}] wrote {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
