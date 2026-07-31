#!/usr/bin/env python3
"""Picks ONE unused asset from content/agente_stories_manifest.json (any
category -- salgada/doce naturally rotate in proportion to how many of each
exist in the pool) and marks it used.

If the pool runs out of unused assets, it auto-resets (all marked unused
again) so the rotation never stalls -- this folder doesn't grow daily like
a client's real photo library does.

Usage: select_story.py
Prints one line: category<TAB>type<TAB>absolute_path
"""
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
    data = load()
    assets = data["assets"]
    pool = [a for a in assets if not a["used"]]
    if not pool:
        for a in assets:
            a["used"] = False
            a["used_at"] = None
        pool = assets
    entry = random.choice(pool)
    entry["used"] = True
    import datetime
    entry["used_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    save(data)
    path = os.path.join(ASSETS_DIR, entry["file"])
    print(f"{entry['category']}\t{entry['type']}\t{path}")


if __name__ == "__main__":
    main()
