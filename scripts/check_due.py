#!/usr/bin/env python3
"""Fast, Drive-free pre-check used by poller.yml as an early-exit gate:
prints DUE (exit 0) if a story slot looks like it needs posting right now,
or NOT_DUE (exit 1) otherwise, so the workflow can skip the expensive
rclone/Drive-mount steps on the majority of ticks where nothing is
actually due (cron-job.org + GitHub's own schedule both fire every ~15
min, but a real slot only becomes due once or twice a day).

Deliberately conservative and fully independent from poller.py's own
matching logic (never imports it, never touches the Drive, never writes
anything) -- worst case if this check is ever wrong: a wasted mount (same
cost as before this existed) or a post delayed to the next ~15-min tick,
since poller.py's real logic (unchanged) is still the actual authority on
what gets posted. Deliberately does NOT try to replicate poller.py's
`check_missed_days` catch-up notification -- that only needs to run once a
day and will still run normally on whatever tick this check does let
through, since TopTop has a story scheduled every single day of the week.
"""
import datetime
import json
import os
import sys

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_PATH = os.path.join(PROJECT_DIR, "content", "posted_log.json")

SCHEDULE = [
    {"slot": "story", "weekdays": {0, 1, 2, 3}, "hour": 20, "minute": 0},
    {"slot": "story_1", "weekdays": {4, 5, 6}, "hour": 19, "minute": 30},
    {"slot": "story_2", "weekdays": {4, 5, 6}, "hour": 21, "minute": 30},
]


def load_log():
    if not os.path.exists(LOG_PATH):
        return {}
    with open(LOG_PATH, encoding="utf-8") as f:
        return json.load(f)


def any_due(now):
    today_key = now.date().isoformat()
    log = load_log()
    for entry in SCHEDULE:
        if now.weekday() not in entry["weekdays"]:
            continue
        scheduled = now.replace(hour=entry["hour"], minute=entry["minute"], second=0, microsecond=0)
        if now < scheduled:
            continue
        key = f"{today_key}_{entry['slot']}"
        if key not in log:
            return True
    return False


if __name__ == "__main__":
    due = any_due(datetime.datetime.now())
    print("DUE" if due else "NOT_DUE")
    sys.exit(0 if due else 1)
