#!/usr/bin/env python3
"""Checks whether now matches a scheduled TopTop Pizzaria story slot and, if
so, picks one unused asset from content/agente_stories_manifest.json and
posts it (Facebook + Instagram Stories). Meant to be invoked frequently
(every ~15min) by a GitHub Actions cron during the relevant windows.

No week-plan/approval step like Bernardino: TopTop only posts stories (no
feed), one item at a time, straight from the categorized manifest pool.

Schedule:
  Mon-Thu 20:00 -> 1 story
  Fri-Sun 19:30 and 21:30 -> 2 stories

Catch-up, not a narrow window: fires as soon as "now" is at or past a
scheduled time (same day), and keeps trying on every later tick until that
slot is marked posted for today -- GitHub's own cron schedule has proven
unreliable about landing near its configured time (see Bernardino's
memory/bernardino-restaurante-automation.md), so a narrow match window can
cause entire days to silently post nothing.

Defaults to --dry-run (prints what it would do, does NOT call Facebook).
Pass --live to actually publish.
"""
import datetime
import json
import os
import subprocess
import sys

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(PROJECT_DIR, "content", "posted_log.json")

# weekday(): Monday=0 ... Sunday=6
SCHEDULE = [
    {"slot": "story", "weekdays": {0, 1, 2, 3}, "hour": 20, "minute": 0},
    {"slot": "story_1", "weekdays": {4, 5, 6}, "hour": 19, "minute": 30},
    {"slot": "story_2", "weekdays": {4, 5, 6}, "hour": 21, "minute": 30},
]

DRY_RUN = "--live" not in sys.argv[1:]


def _arg_value(name):
    args = sys.argv[1:]
    if name in args:
        idx = args.index(name)
        if idx + 1 < len(args):
            return args[idx + 1]
    return None


FORCE_SLOT = _arg_value("--force-slot")


def run(cmd):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env)
    if result.returncode != 0:
        print(f"ERRO rodando {cmd}:\n{result.stderr}", file=sys.stderr)
        raise SystemExit(1)
    return result.stdout.strip()


def bash(script_rel, *args):
    return run(["bash", os.path.join(SCRIPTS_DIR, script_rel), *args])


def python(script_rel, *args):
    return run([sys.executable, os.path.join(SCRIPTS_DIR, script_rel), *args])


PATH_ANCHORS = [
    ("AGENTE - STORIES", lambda: os.environ.get("AGENTE_STORIES_DIR", "")),
]


def _find_by_normalized_name(dir_path, target_name):
    import unicodedata
    target_norm = unicodedata.normalize("NFC", target_name)
    try:
        entries = os.listdir(dir_path)
    except OSError:
        return None
    for entry in entries:
        if unicodedata.normalize("NFC", entry) == target_norm:
            return os.path.join(dir_path, entry)
    return None


def resolve_path(path):
    if os.path.exists(path):
        return path
    normalized = path.replace("\\", "/")
    for anchor, get_base in PATH_ANCHORS:
        idx = normalized.find(anchor)
        if idx == -1:
            continue
        base = get_base()
        if not base:
            continue
        remainder = normalized[idx + len(anchor):].lstrip("/")
        candidate = os.path.join(base, remainder)
        if os.path.exists(candidate):
            return candidate
        found = _find_by_normalized_name(os.path.dirname(candidate), os.path.basename(candidate))
        if found:
            return found
    return path


def notify_once(marker, body):
    """Best-effort GitHub Issue notification -- never raises."""
    try:
        title = f"[poller] {marker}"
        check = subprocess.run(
            ["gh", "issue", "list", "--search", f'"{title}" in:title', "--state", "open", "--json", "number"],
            capture_output=True, text=True,
        )
        if check.returncode == 0 and check.stdout.strip() and check.stdout.strip() != "[]":
            return
        subprocess.run(["gh", "issue", "create", "--title", title, "--body", body], capture_output=True, text=True)
    except Exception as e:
        print(f"AVISO: notify_once falhou (nao critico): {e}", file=sys.stderr)


def handle_partial_failure(slot_label, exc, now):
    """A handler crashed mid-posting (e.g. the Facebook leg of a video story
    succeeded but the Instagram leg errored). There's no way to tell from
    here which legs actually went out for real. Marking the slot posted
    anyway is the safer failure mode: it stops the next tick from blindly
    re-running the whole handler and re-posting whatever already went out
    for real (this exact bug caused a real duplicate post on Bernardino's
    automation on 2026-08-05 -- see that repo's poller.py for the original
    writeup; applied here too since TopTop's handle_story() has the same
    multi-step-without-partial-tracking shape)."""
    print(f"##[error] Falha ao publicar '{slot_label}': {exc}", file=sys.stderr)
    notify_once(
        f"post-falhou-{now.date().isoformat()}-{slot_label}",
        f"O poller tentou publicar '{slot_label}' ({now.date().isoformat()}) e um erro interrompeu a publicacao "
        "no meio (ex: Facebook saiu mas Instagram falhou, ou vice-versa -- nao da pra saber automaticamente qual "
        "etapa completou). Para nao arriscar duplicar o que ja saiu, esse slot foi marcado como publicado -- ele "
        "NAO sera tentado de novo automaticamente. Confira manualmente no Facebook/Instagram da TopTop o que "
        f"realmente foi publicado, e publique manualmente qualquer item que estiver faltando.\n\nErro original: {exc}"
    )


def load_log():
    if not os.path.exists(LOG_PATH):
        return {}
    with open(LOG_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_log(log):
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def handle_story():
    line = python("select_story.py")
    category, type_, path = line.split("\t")
    path = resolve_path(path)
    print(f"Selecionado ({category}, {type_}): {path}")
    if DRY_RUN:
        print(f"[DRY-RUN] postaria {type_}: {path}")
        return {"category": category, "type": type_, "path": path}

    if type_ == "image":
        print(bash("post_story_all.sh", path))
    else:
        print(bash("post_story_video_fb.sh", path))
        fname = os.path.basename(path)
        video_url = python("resolve_drive_url.py", fname)
        print(bash("post_story_video_instagram.sh", video_url))
    return {"category": category, "type": type_, "path": path}


def check_missed_days(now, log, lookback_days=7):
    """Alerts (once per day) for any of the last `lookback_days` whose
    schedule wasn't fully posted -- catches the case where GitHub's cron
    never fired at all inside that day's window (or the poller itself didn't
    run for a while), which the same-day-only catch-up above can't recover
    from on its own."""
    for days_ago in range(1, lookback_days + 1):
        day = now.date() - datetime.timedelta(days=days_ago)
        day_key = day.isoformat()
        missed = [
            entry["slot"] for entry in SCHEDULE
            if day.weekday() in entry["weekdays"]
            and f"{day_key}_{entry['slot']}" not in log
        ]
        if missed:
            notify_once(
                f"stories perdidos em {day_key}",
                f"O agendamento de {day_key} nao rodou (ou rodou incompleto): "
                f"slot(s) {', '.join(missed)} nunca foram postados nesse dia e o "
                f"catch-up so cobre o mesmo dia, entao ficaram perdidos. "
                f"Causa provavel: o cron do GitHub Actions nao disparou nenhuma vez "
                f"dentro da janela do dia (ver comentario em poller.yml)."
            )


def main():
    now = datetime.datetime.now()
    today_key = now.date().isoformat()
    log = load_log()

    if not DRY_RUN:
        check_missed_days(now, log)

    if FORCE_SLOT:
        print(f"Forcando slot '{FORCE_SLOT}' ({'DRY-RUN' if DRY_RUN else 'LIVE'})...")
        key = f"{today_key}_{FORCE_SLOT}"
        try:
            result = handle_story()
        except Exception as exc:
            if not DRY_RUN:
                handle_partial_failure(FORCE_SLOT, exc, now)
                log[key] = {"posted_at": now.isoformat(timespec="seconds"), "posting_error": str(exc)}
                save_log(log)
            raise
        if not DRY_RUN:
            log[key] = {"posted_at": now.isoformat(timespec="seconds"), **result}
            save_log(log)
        return

    for entry in SCHEDULE:
        if now.weekday() not in entry["weekdays"]:
            continue
        scheduled = now.replace(hour=entry["hour"], minute=entry["minute"], second=0, microsecond=0)
        if now < scheduled:
            continue
        key = f"{today_key}_{entry['slot']}"
        if key in log:
            continue
        print(f"Disparando slot '{entry['slot']}' ({'DRY-RUN' if DRY_RUN else 'LIVE'})...")
        try:
            result = handle_story()
        except Exception as exc:
            if not DRY_RUN:
                handle_partial_failure(entry["slot"], exc, now)
                log[key] = {"posted_at": now.isoformat(timespec="seconds"), "posting_error": str(exc)}
                save_log(log)
            raise
        if not DRY_RUN:
            log[key] = {"posted_at": now.isoformat(timespec="seconds"), **result}
            save_log(log)
        return

    print("Nenhum slot devido agora.")


if __name__ == "__main__":
    main()
