#!/usr/bin/env python3
"""
Polls the ArchiveTeam YouTube tracker JSON API every 5 minutes
and appends stats to youtube_tracker_stats.csv.

Columns: timestamp (UTC ISO-8601), claims (items out/in-progress), done, todo, total
"""

import csv
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

STATS_URL = "https://v1.api.tracker.archiveteam.org/youtube/stats.json"
CSV_FILE = Path(__file__).parent / "youtube_tracker_stats.csv"
INTERVAL_SECONDS = 5 * 60

FIELDNAMES = ["timestamp", "claims", "done", "todo", "total"]


def fetch_stats() -> dict:
    resp = requests.get(STATS_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    claims = data.get("total_items_out")   # items currently checked out / in-progress
    done   = data.get("total_items_done")
    todo   = data.get("total_items_todo")
    total  = data.get("total_items")

    return {"claims": claims, "done": done, "todo": todo, "total": total}


def ensure_csv_header():
    if not CSV_FILE.exists():
        with CSV_FILE.open("w", newline="") as f:
            csv.DictWriter(f, fieldnames=FIELDNAMES).writeheader()


def append_row(stats: dict):
    row = {
        "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        **stats,
    }
    with CSV_FILE.open("a", newline="") as f:
        csv.DictWriter(f, fieldnames=FIELDNAMES).writerow(row)
    print(
        f"[{row['timestamp']}]  claims={row['claims']:>10,}  done={row['done']:>10,}"
        f"  todo={row['todo']:>10,}  total={row['total']:>10,}"
    )


def main():
    once = "--once" in sys.argv

    ensure_csv_header()
    if not once:
        print(f"Logging to: {CSV_FILE}")
        print(f"Polling every {INTERVAL_SECONDS // 60} minutes. Press Ctrl+C to stop.\n")

    while True:
        try:
            stats = fetch_stats()
            append_row(stats)
        except requests.RequestException as exc:
            print(f"  [network error] {exc}", file=sys.stderr)
        except Exception as exc:
            print(f"  [unexpected error] {exc}", file=sys.stderr)

        if once:
            break
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
