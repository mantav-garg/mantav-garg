"""
Parses a GitHub user's public contribution graph and saves it as a CSV
of (date, count) rows.

Source: https://github.com/users/<username>/contributions
This is the same page GitHub renders on profile pages, so no auth/token
is required.

Note: GitHub's markup here is an HTML table of
<td class="ContributionCalendar-day" data-date="..." data-level="...">
cells - there's no data-count attribute anymore. The actual count only
appears as text in a sibling <tool-tip> element, e.g. "1 contribution on
June 25th." or "No contributions on June 18th.", so we pull it from there.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Used only when running this file directly (see bottom of file).
USERNAME = "octocat"

TOOLTIP_PATTERN = re.compile(r"(\d+|No)\s+contributions?")


def fetch_github_contributions(username: str) -> list[tuple[str, int]]:
    """Return a list of (date, count) tuples for the given GitHub user."""
    url = f"https://github.com/users/{username}/contributions"
    response = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Each day cell's contribution count lives in a separate <tool-tip>
    # element linked back to the cell via for="<cell id>".
    tooltip_by_cell_id = {}
    for tip in soup.find_all("tool-tip"):
        cell_id = tip.get("for")
        if cell_id:
            tooltip_by_cell_id[cell_id] = tip.get_text(strip=True)

    data: list[tuple[str, int]] = []
    for cell in soup.find_all("td", class_="ContributionCalendar-day"):
        date = cell.get("data-date")
        if not date:
            continue

        tooltip_text = tooltip_by_cell_id.get(cell.get("id"), "")
        match = TOOLTIP_PATTERN.match(tooltip_text)
        count = 0 if not match or match.group(1) == "No" else int(match.group(1))

        data.append((date, count))

    if not data:
        raise ValueError(
            f"No contribution cells found for '{username}' - the profile "
            "may not exist, may be private, or GitHub may have changed "
            "its markup again."
        )

    data.sort(key=lambda row: row[0])
    return data


def save_to_csv(rows: list[tuple[str, int]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "count"])
        writer.writerows(rows)


if __name__ == "__main__":
    rows = fetch_github_contributions(USERNAME)
    out_path = Path("data") / "github_contributions.csv"
    save_to_csv(rows, out_path)
    print(f"wrote {len(rows)} rows -> {out_path}")