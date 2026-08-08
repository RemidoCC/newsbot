#!/usr/bin/env python3
"""Ontdubbelt en filtert de ruwe oogst, en snijdt hem in batches voor `claude -p`.

Nog steeds geen LLM. Vier zeven, in deze volgorde:

    1. al eerder getoond   -> weg (seen.json, 30 dagen geheugen)
    2. te oud              -> weg (48 uur voor ai, 7 dagen voor bieb)
    3. bijna dezelfde kop  -> samengevoegd, beste bron wint
    4. meer dan 120 over   -> cap op bronprioriteit en recentheid

Over seen.json: dit script werkt het meteen bij, maar de workflow commit `data/`
pas aan het eind. Klapt de run halverwege, dan blijft de versie in git staan en
zijn de items morgen gewoon weer kandidaat. Git is hier de transactiegrens.

Gebruik:
    python scripts/dedupe.py                     # laatste raw-bestand
    python scripts/dedupe.py --date 2026-08-07   # een specifieke dag
    python scripts/dedupe.py --dry-run           # niets wegschrijven
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dateutil import parser as dateparser

from collect import DATA_DIR, ROOT, flush_errors, log_error, normalize_url

SEEN_PATH = DATA_DIR / "seen.json"
SEEN_RETENTION_DAYS = 30
MAX_ITEMS = 120
BATCH_SIZE = 40
TITLE_OVERLAP = 0.85

# Bibliotheekbronnen publiceren een paar keer per maand, geen paar keer per dag.
# Met 48 uur zou die tab bijna altijd leeg zijn.
MAX_AGE_HOURS = {"ai": 48, "bieb": 24 * 7}

# Woorden die in koppen niets onderscheiden en de overlap-score zouden opblazen.
STOPWORDS = {
    "de", "het", "een", "van", "voor", "met", "op", "in", "en", "is", "aan", "bij",
    "naar", "door", "over", "als", "dat", "die", "te", "om", "zijn", "wordt", "worden",
    "the", "a", "an", "of", "for", "with", "on", "in", "and", "is", "to", "at", "by",
    "from", "as", "that", "this", "it", "its", "are", "be", "new", "now",
}


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        if path.exists():
            log_error(path.name, "dedupe_load", exc)
        return default


def parse_when(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = dateparser.isoparse(value)
    except (ValueError, TypeError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def title_tokens(title: str) -> set[str]:
    return {t for t in re.findall(r"\w+", (title or "").lower()) if t not in STOPWORDS}


def near_duplicate(left: set[str], right: set[str]) -> bool:
    """Deelt het grootste deel van de betekenisdragende woorden.

    Gedeeld door de kortste van de twee, niet door de unie: "OpenAI kondigt GPT-6
    aan" en "OpenAI kondigt GPT-6 aan tijdens DevDay" horen bij elkaar. Onder de
    drie woorden is de score te grillig, dan houden we ze uit elkaar.
    """
    if len(left) < 3 or len(right) < 3:
        return False
    return len(left & right) / min(len(left), len(right)) >= TITLE_OVERLAP


def prune_seen(seen: dict) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=SEEN_RETENTION_DAYS)
    kept = {}
    for key, value in seen.items():
        when = parse_when(value)
        if when is None or when >= cutoff:
            kept[key] = value
    return kept


def sort_key(item: dict):
    """Bronprioriteit eerst, dan recentheid. Datumloos telt als oudst."""
    published = parse_when(item.get("published"))
    return (
        int(item.get("priority", 3)),
        -(published.timestamp() if published else 0),
    )


def run(date: str | None, dry_run: bool) -> int:
    raw_files = sorted((DATA_DIR / "raw").glob("*.json"))
    if date:
        path = DATA_DIR / "raw" / f"{date}.json"
    elif raw_files:
        path = raw_files[-1]
    else:
        print("Geen raw-bestand gevonden. Draai eerst collect.py.", file=sys.stderr)
        return 1

    payload = load_json(path, None)
    if not payload or "items" not in payload:
        print(f"{path} is leeg of onbruikbaar.", file=sys.stderr)
        return 1

    items = payload["items"]
    now = datetime.now(timezone.utc)
    seen = prune_seen(load_json(SEEN_PATH, {}) or {})
    stats = {"binnen": len(items), "al_gezien": 0, "te_oud": 0, "dubbel": 0, "gecapt": 0}

    # 1 + 2: eerder getoond, en te oud voor het kanaal.
    fresh = []
    for item in items:
        key = item.get("id") or normalize_url(item.get("url", ""))
        if not key:
            continue
        if key in seen:
            stats["al_gezien"] += 1
            continue

        published = parse_when(item.get("published"))
        if published is not None:
            window = MAX_AGE_HOURS.get(item.get("channel_hint", "ai"), 48)
            if now - published > timedelta(hours=window):
                stats["te_oud"] += 1
                continue
        # Geen datum (de KB-feed doet dit): niet weggooien, want ongezien is hier
        # het enige bruikbare signaal dat het nieuw is. seen.json voorkomt herhaling.
        fresh.append(item)

    fresh.sort(key=sort_key)

    # 3: bijna dezelfde kop. De eerste in de sortering wint, dus de bron met de
    # hoogste prioriteit; de rest komt als also_covered_by mee voor Claude.
    kept: list[dict] = []
    kept_tokens: list[set[str]] = []
    for item in fresh:
        tokens = title_tokens(item.get("title", ""))
        for index, existing in enumerate(kept_tokens):
            if near_duplicate(tokens, existing):
                kept[index].setdefault("also_covered_by", []).append(item["url"])
                stats["dubbel"] += 1
                break
        else:
            kept.append(item)
            kept_tokens.append(tokens)

    # 4: cap.
    if len(kept) > MAX_ITEMS:
        stats["gecapt"] = len(kept) - MAX_ITEMS
        kept = kept[:MAX_ITEMS]

    stats["over"] = len(kept)
    print(json.dumps(stats, ensure_ascii=False, indent=2), file=sys.stderr)

    if dry_run:
        print("(dry-run: niets weggeschreven)", file=sys.stderr)
        return 0

    stamp = path.stem
    clean_dir = DATA_DIR / "clean"
    clean_dir.mkdir(parents=True, exist_ok=True)
    (clean_dir / f"{stamp}.json").write_text(
        json.dumps({"generated_at": now.isoformat(timespec="seconds"),
                    "stats": stats, "items": kept}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # Oude batches weg, anders verwerkt de workflow morgen die van vandaag nog eens.
    batch_dir = DATA_DIR / "batches"
    batch_dir.mkdir(parents=True, exist_ok=True)
    for old in batch_dir.glob("batch_*.json"):
        old.unlink()

    batches = [kept[i:i + BATCH_SIZE] for i in range(0, len(kept), BATCH_SIZE)]
    for number, batch in enumerate(batches, start=1):
        (batch_dir / f"batch_{number:02d}.json").write_text(
            json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    for item in kept:
        seen[item["id"]] = now.isoformat(timespec="seconds")
    SEEN_PATH.write_text(
        json.dumps(seen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(
        f"{len(kept)} items over, {len(batches)} batches "
        f"-> {batch_dir.relative_to(ROOT)}/",
        file=sys.stderr,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", metavar="YYYY-MM-DD", help="welk raw-bestand")
    parser.add_argument("--dry-run", action="store_true", help="alleen tellen")
    args = parser.parse_args()
    try:
        return run(args.date, args.dry_run)
    finally:
        flush_errors()


if __name__ == "__main__":
    sys.exit(main())
