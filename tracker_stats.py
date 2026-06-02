#!/usr/bin/env python3
"""
Polls the ArchiveTeam YouTube tracker JSON API every 5 minutes
and appends stats to youtube_tracker_stats.csv.
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

FIELDNAMES = [
    "timestamp", "claims", "done", "todo", "total",
    "ikata_items", "ikata_bytes", "ikata_rank",
    "days_to_top20", "days_to_top5", "days_to_top1",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://tracker.archiveteam.org/youtube/",
    "Origin": "https://tracker.archiveteam.org",
}


def parse_timestamp(s: str):
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            pass
    return None


def get_rate_bytes_per_day() -> float | None:
    """Compute bytes/day rate from all ikata_bytes rows in the CSV."""
    if not CSV_FILE.exists():
        return None
    with CSV_FILE.open(newline="") as f:
        rows = list(csv.DictReader(f))
    points = []
    for r in rows:
        raw = r.get("ikata_bytes", "").strip()
        if not raw:
            continue
        try:
            ts = parse_timestamp(r.get("timestamp", ""))
            if ts:
                points.append((ts, float(raw)))
        except ValueError:
            pass
    if len(points) < 2:
        return None
    elapsed = (points[-1][0] - points[0][0]).total_seconds()
    if elapsed <= 0:
        return None
    return (points[-1][1] - points[0][1]) / elapsed * 86_400


def eta_days(current: float, target: float, rate: float | None):
    if current is None or target is None or not rate or rate <= 0:
        return None
    if current >= target:
        return 0.0
    return round((target - current) / rate, 1)


def fetch_stats() -> dict:
    resp = requests.get(STATS_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    ikata_bytes = data.get("downloader_bytes", {}).get("Ikata")
    ikata_items = data.get("downloader_count", {}).get("Ikata")

    sorted_bytes = sorted(data.get("downloader_bytes", {}).values(), reverse=True)
    ikata_rank = sum(1 for b in sorted_bytes if b > (ikata_bytes or 0)) + 1

    rate  = get_rate_bytes_per_day()
    top20 = sorted_bytes[19] if len(sorted_bytes) >= 20 else None
    top5  = sorted_bytes[4]  if len(sorted_bytes) >= 5  else None
    top1  = sorted_bytes[0]  if sorted_bytes else None

    return {
        "claims": data.get("total_items_out"),
        "done":   data.get("total_items_done"),
        "todo":   data.get("total_items_todo"),
        "total":  data.get("total_items"),
        "ikata_items":    ikata_items,
        "ikata_bytes":    ikata_bytes,
        "ikata_rank":     ikata_rank,
        "days_to_top20":  eta_days(ikata_bytes, top20, rate),
        "days_to_top5":   eta_days(ikata_bytes, top5,  rate),
        "days_to_top1":   eta_days(ikata_bytes, top1,  rate),
    }


def ensure_csv_header():
    if not CSV_FILE.exists():
        with CSV_FILE.open("w", newline="") as f:
            csv.DictWriter(f, fieldnames=FIELDNAMES).writeheader()
        return
    # Migrate header if columns have changed
    with CSV_FILE.open(newline="") as f:
        reader = csv.DictReader(f)
        current_fields = list(reader.fieldnames or [])
        rows = list(reader)
    if current_fields != FIELDNAMES:
        with CSV_FILE.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)


def append_row(stats: dict):
    row = {"timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S"), **stats}
    with CSV_FILE.open("a", newline="") as f:
        csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore").writerow(row)
    print(
        f"[{row['timestamp']}]  rank=#{row['ikata_rank']}  "
        f"items={row['ikata_items']:>8,}  "
        f"→top20={row['days_to_top20']}d  "
        f"→top5={row['days_to_top5']}d  "
        f"→#1={row['days_to_top1']}d"
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
