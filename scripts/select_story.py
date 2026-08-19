#!/usr/bin/env python3
"""Picks ONE unused asset from content/agente_stories_manifest.json (any
category -- salgada/doce naturally rotate in proportion to how many of each
exist in the pool) and marks it used.

Some assets talk about a specific day in the video/caption itself (e.g. a
weekend promo) -- those carry an "allowed_weekdays" list (0=Monday ...
6=Sunday) in the manifest and are only eligible on those days, AND get
picked ahead of the generic (no "allowed_weekdays") pool on a day they
match -- otherwise a handful of day-specific videos would rarely surface
at all next to ~10x as many generic ones. Everything without the key
stays fair game any day, same as before.
Added 2026-08-19 after 96.mp4 (a weekend-themed video) posted on a Tuesday.

If the pool of eligible-and-unused assets runs out, it auto-resets (marks
just the eligible-for-today ones unused again) so the rotation never
stalls -- this folder doesn't grow daily like a client's real photo
library does.

Usage: select_story.py
Prints one line: category<TAB>type<TAB>absolute_path
"""
import datetime
import json
import os
import random

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST_PATH = os.path.join(PROJECT_DIR, "content", "agente_stories_manifest.json")
# Windows default kept for local runs; GitHub Actions sets AGENTE_STORIES_DIR
# to the rclone-mounted path instead (no G:\ drive there).
ASSETS_DIR = os.environ.get(
    "AGENTE_STORIES_DIR",
    r"G:\Meu Drive\Agência BEEF MTK\Clientes\TopTop Pizzaria\Storie\AGENTE - STORIES",
)


def load():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save(data):
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    today_weekday = datetime.datetime.now().weekday()
    data = load()
    assets = data["assets"]
    eligible = [a for a in assets if today_weekday in a.get("allowed_weekdays", range(7))]

    # Day-specific assets (allowed_weekdays present) get first pick over
    # generic ones on their day -- otherwise they're eligible but easily
    # drowned out by the ~10x larger generic pool and could go months
    # without actually being picked. Falls back to the full eligible pool
    # (day-specific + generic) once today's day-specific items are all used.
    day_specific = [a for a in eligible if "allowed_weekdays" in a]
    day_specific_unused = [a for a in day_specific if not a["used"]]
    pool = day_specific_unused if day_specific_unused else [a for a in eligible if not a["used"]]
    if not pool:
        for a in eligible:
            a["used"] = False
            a["used_at"] = None
        pool = eligible
    entry = random.choice(pool)
    entry["used"] = True
    entry["used_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    save(data)
    path = os.path.join(ASSETS_DIR, entry["file"])
    print(f"{entry['category']}\t{entry['type']}\t{path}")


if __name__ == "__main__":
    main()
