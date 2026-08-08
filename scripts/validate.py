#!/usr/bin/env python3
"""Controleert wat `claude -p` teruggaf en bouwt daaruit de digest.

Claude Code levert tekst, geen garantie. Dit script gaat er dus vanuit dat de
uitvoer rommelig kan zijn: markdown-fences eromheen, een inleidende zin, een
afgekapt laatste object. Alles wat niet door het schema komt gaat eruit; wat
overblijft wordt samengevoegd met het oorspronkelijke item, want url,
source_name en published komen uit de collector en niet uit het model.

De run mag hier nooit op stukvallen. Een onbruikbare batch wordt overgeslagen
en gelogd; de overige batches gaan gewoon door.

Gebruik:
    python scripts/validate.py                        # alle data/enriched_*.json
    python scripts/validate.py --batch data/enriched_01.json
    python scripts/validate.py --check-only           # niets wegschrijven
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator

from collect import DATA_DIR, ROOT, flush_errors, log_error

TOPICS = [
    "modellen", "onderzoek", "beleid-en-regelgeving", "bedrijven", "tools",
    "open-source", "ethiek-en-risico", "onderwijs", "arbeidsmarkt", "bibliotheek",
    "digitale-inclusie", "digitale-geletterdheid", "cursus-of-workshop",
    "subsidie-of-financiering", "evenement",
]

ITEM_SCHEMA = {
    "type": "object",
    "required": ["id"],
    "properties": {
        "id": {"type": "string", "minLength": 8},
        "drop": {"type": "boolean"},
        "drop_reason": {"type": "string"},
        "reason": {"type": "string"},
        "title_nl": {"type": "string", "minLength": 3, "maxLength": 300},
        "summary_nl": {"type": "string", "minLength": 20, "maxLength": 1200},
        "channel": {"enum": ["ai", "bieb"]},
        "region": {"enum": ["nl", "int"]},
        "topics": {
            "type": "array", "minItems": 1, "maxItems": 3,
            "items": {"enum": TOPICS},
        },
        "importance": {"type": "integer", "minimum": 1, "maximum": 5},
        "why_relevant": {"type": "string", "minLength": 3, "maxLength": 200},
        "also_covered_by": {"type": "array", "items": {"type": "string"}},
    },
    # Een item dat blijft moet compleet zijn; een gedropt item hoeft alleen id+drop.
    "if": {"properties": {"drop": {"const": True}}, "required": ["drop"]},
    "else": {
        "required": ["title_nl", "summary_nl", "channel", "region", "topics",
                     "importance", "why_relevant"],
    },
}

validator = Draft202012Validator(ITEM_SCHEMA)


def extract_json_array(text: str) -> list | None:
    """Vist de JSON-array uit de uitvoer, ook met tekst of fences eromheen."""
    if not text or not text.strip():
        return None

    candidates = []
    stripped = text.strip()
    candidates.append(stripped)

    fenced = re.findall(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    candidates.extend(block.strip() for block in fenced)

    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end > start:
        candidates.append(text[start:end + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            for key in ("items", "results", "output"):
                if isinstance(parsed.get(key), list):
                    return parsed[key]
    return None


def load_source_items() -> dict[str, dict]:
    """De originele items, op id. Hieruit komen url, bron en datum."""
    clean_files = sorted((DATA_DIR / "clean").glob("*.json"))
    if not clean_files:
        return {}
    payload = json.loads(clean_files[-1].read_text(encoding="utf-8"))
    return {item["id"]: item for item in payload.get("items", [])}


def merge(original: dict, enriched: dict) -> dict:
    """Model levert taal en oordeel; de collector levert de feiten."""
    covered = list(dict.fromkeys(
        (original.get("also_covered_by") or []) + (enriched.get("also_covered_by") or [])
    ))
    return {
        "id": original["id"],
        "title": enriched["title_nl"].strip(),
        "summary": enriched["summary_nl"].strip(),
        "url": original["url"],
        "source_name": original["source_name"],
        "source_type": original.get("source_type", "rss"),
        "published": original.get("published"),
        "channel": enriched["channel"],
        "region": enriched["region"],
        "topics": enriched["topics"],
        "importance": int(enriched["importance"]),
        "why_relevant": enriched["why_relevant"].strip(),
        "also_covered_by": covered,
    }


def run(batch_paths: list[Path], check_only: bool) -> int:
    originals = load_source_items()
    if not originals:
        print("Geen data/clean/*.json gevonden. Draai eerst dedupe.py.", file=sys.stderr)
        return 1

    accepted: list[dict] = []
    stats = {"batches": 0, "onleesbaar": 0, "objecten": 0,
             "schema_fout": 0, "onbekend_id": 0, "gedropt": 0}

    for path in batch_paths:
        stats["batches"] += 1
        try:
            parsed = extract_json_array(path.read_text(encoding="utf-8"))
        except OSError as exc:
            log_error(path.name, "validate_read", exc)
            stats["onleesbaar"] += 1
            continue

        if parsed is None:
            log_error(path.name, "validate_parse",
                      "geen JSON-array te vinden in de uitvoer")
            stats["onleesbaar"] += 1
            continue

        for entry in parsed:
            stats["objecten"] += 1
            if not isinstance(entry, dict):
                stats["schema_fout"] += 1
                continue

            errors = sorted(validator.iter_errors(entry), key=lambda e: e.path)
            if errors:
                stats["schema_fout"] += 1
                log_error(path.name, "validate_schema",
                          f"{entry.get('id', '?')[:12]}: {errors[0].message}")
                continue

            if entry.get("drop"):
                stats["gedropt"] += 1
                continue

            original = originals.get(entry["id"])
            if original is None:
                # Het model heeft een id verzonnen of verhaspeld. Zonder origineel
                # is er geen bron-URL, en dan gaat het item eruit.
                stats["onbekend_id"] += 1
                log_error(path.name, "validate_id",
                          f"onbekend id {entry['id'][:16]}, geen bron-URL")
                continue

            accepted.append(merge(original, entry))

    # Eén artikel kan in twee batches beland zijn; het eerste oordeel wint.
    unique: dict[str, dict] = {}
    for item in accepted:
        unique.setdefault(item["id"], item)
    items = sorted(
        unique.values(),
        key=lambda i: (-i["importance"], i.get("published") or "", i["title"]),
    )

    stats["geldig"] = len(items)
    stats["ai"] = sum(1 for i in items if i["channel"] == "ai")
    stats["bieb"] = sum(1 for i in items if i["channel"] == "bieb")
    print(json.dumps(stats, ensure_ascii=False, indent=2), file=sys.stderr)

    if check_only:
        return 0 if items else 1

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = DATA_DIR / "digest" / f"{today}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({
            "date": today,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "stats": stats,
            "sources": sorted({i["source_name"] for i in items}),
            "items": items,
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"{len(items)} items -> {out_path.relative_to(ROOT)}", file=sys.stderr)

    # Een lege digest is geen crash, maar de workflow moet 'm wel herkennen:
    # geen pushmelding, en de vorige digest blijft staan.
    return 0 if items else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", action="append", type=Path,
                        help="specifiek bestand; herhaalbaar")
    parser.add_argument("--check-only", action="store_true",
                        help="alleen controleren, geen digest schrijven")
    args = parser.parse_args()

    paths = args.batch or sorted(DATA_DIR.glob("enriched_*.json"))
    if not paths:
        print("Geen enriched-bestanden gevonden.", file=sys.stderr)
        return 1

    try:
        return run(paths, args.check_only)
    finally:
        flush_errors()


if __name__ == "__main__":
    sys.exit(main())
