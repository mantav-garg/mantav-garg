"""
Parses a LeetCode user's public submission calendar and saves it as a
CSV of (date, count) rows.

Source: LeetCode's public GraphQL endpoint (matchedUser.userCalendar).
No auth/token is required for public profiles.
"""

from __future__ import annotations

import csv
import datetime
import json
from pathlib import Path

import requests

# Used only when running this file directly (see bottom of file).
USERNAME = "leetcode"

GRAPHQL_URL = "https://leetcode.com/graphql"

QUERY = """
query userProfileCalendar($username: String!) {
  matchedUser(username: $username) {
    userCalendar {
      submissionCalendar
    }
  }
}
"""


def fetch_leetcode_submissions(username: str) -> list[tuple[str, int]]:
    """Return a list of (date, count) tuples for the given LeetCode user."""
    response = requests.post(
        GRAPHQL_URL,
        json={"query": QUERY, "variables": {"username": username}},
        headers={
            "Content-Type": "application/json",
            "Referer": f"https://leetcode.com/{username}/",
        },
        timeout=15,
    )
    response.raise_for_status()

    payload = response.json()
    matched_user = payload.get("data", {}).get("matchedUser")
    if not matched_user:
        raise ValueError(f"LeetCode user '{username}' was not found.")

    calendar_raw = matched_user["userCalendar"]["submissionCalendar"]
    calendar = json.loads(calendar_raw)  # {"<unix_timestamp>": count, ...}

    data: list[tuple[str, int]] = []
    for timestamp, count in calendar.items():
        date = datetime.datetime.utcfromtimestamp(int(timestamp)).strftime("%Y-%m-%d")
        data.append((date, int(count)))

    data.sort(key=lambda row: row[0])
    return data


def save_to_csv(rows: list[tuple[str, int]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "count"])
        writer.writerows(rows)


if __name__ == "__main__":
    rows = fetch_leetcode_submissions(USERNAME)
    out_path = Path("data") / "leetcode_submissions.csv"
    save_to_csv(rows, out_path)
    print(f"wrote {len(rows)} rows -> {out_path}")
