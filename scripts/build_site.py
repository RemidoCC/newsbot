#!/usr/bin/env python3
"""Bouwt de statische site uit de digest-JSON. Geen framework, geen buildstap.

Uitvoer:
    site/index.html              de nieuwste digest
    site/archief.html            datumlijst van de laatste 30 digests
    site/archief/<datum>.html    elke digest als eigen pagina
    site/assets/digest.json      de nieuwste digest als data (service worker)

De digest staat inline in de HTML, niet achter een fetch. Daardoor rendert de
pagina meteen, werkt hij offline zodra de service worker hem heeft, en is er
geen laadspinner nodig — precies wat de opdracht vroeg.

Gebruik:
    python scripts/build_site.py                      # nieuwste digest
    python scripts/build_site.py --digest pad.json    # een specifieke
    python scripts/build_site.py --sample             # voorbeelddata, voor ontwerp
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from dateutil import parser as dateparser
from jinja2 import Environment, FileSystemLoader, select_autoescape

from collect import DATA_DIR, ROOT

SITE_DIR = ROOT / "site"
TEMPLATE_DIR = ROOT / "scripts" / "templates"
ARCHIVE_LIMIT = 30

CHANNELS = [
    {"key": "ai", "label": "AI"},
    {"key": "bieb", "label": "Bibliotheek"},
]

# Volgorde waarin onderwerpsecties verschijnen. Wat niet in deze lijst staat
# komt achteraan onder "Overig".
TOPIC_ORDER = [
    "modellen", "onderzoek", "beleid-en-regelgeving", "bedrijven", "tools",
    "open-source", "ethiek-en-risico", "onderwijs", "arbeidsmarkt",
    "bibliotheek", "digitale-inclusie", "digitale-geletterdheid",
    "cursus-of-workshop", "subsidie-of-financiering", "evenement",
]
TOPIC_LABEL = {
    "modellen": "Modellen",
    "onderzoek": "Onderzoek",
    "beleid-en-regelgeving": "Beleid en regelgeving",
    "bedrijven": "Bedrijven",
    "tools": "Tools",
    "open-source": "Open source",
    "ethiek-en-risico": "Ethiek en risico",
    "onderwijs": "Onderwijs",
    "arbeidsmarkt": "Arbeidsmarkt",
    "bibliotheek": "Bibliotheek",
    "digitale-inclusie": "Digitale inclusie",
    "digitale-geletterdheid": "Digitale geletterdheid",
    "cursus-of-workshop": "Cursus of workshop",
    "subsidie-of-financiering": "Subsidie en financiering",
    "evenement": "Evenementen",
}


def relative_time(value: str | None) -> str:
    """"2 uur geleden", "gisteren", "3 dagen geleden". Leeg bij geen datum."""
    if not value:
        return ""
    try:
        when = dateparser.isoparse(value)
    except (ValueError, TypeError):
        return ""
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)

    seconds = (datetime.now(timezone.utc) - when).total_seconds()
    if seconds < 0:
        return "zojuist"
    minutes = int(seconds // 60)
    if minutes < 60:
        return "zojuist" if minutes < 2 else f"{minutes} minuten geleden"
    hours = minutes // 60
    if hours < 24:
        return "1 uur geleden" if hours == 1 else f"{hours} uur geleden"
    days = hours // 24
    if days == 1:
        return "gisteren"
    if days < 14:
        return f"{days} dagen geleden"
    weeks = days // 7
    return "vorige week" if weeks == 1 else f"{weeks} weken geleden"


def dutch_date(value: str) -> str:
    months = ["januari", "februari", "maart", "april", "mei", "juni", "juli",
              "augustus", "september", "oktober", "november", "december"]
    try:
        when = dateparser.isoparse(value)
    except (ValueError, TypeError):
        return value
    return f"{when.day} {months[when.month - 1]} {when.year}"


def group_items(items: list[dict]) -> dict:
    """Splitst per kanaal in 'belangrijk' en secties per onderwerp."""
    grouped = {}
    for channel in CHANNELS:
        key = channel["key"]
        in_channel = [i for i in items if i.get("channel") == key]
        important = [i for i in in_channel if i.get("importance", 0) >= 4]
        rest = [i for i in in_channel if i.get("importance", 0) < 4]

        buckets: dict[str, list] = {}
        for item in rest:
            topic = next((t for t in item.get("topics", []) if t in TOPIC_ORDER), None)
            buckets.setdefault(topic or "overig", []).append(item)

        # Let op: de sleutel heet bewust "rijen" en niet "items". In Jinja pakt
        # `sectie.items` de dict-methode in plaats van de sleutel, en dat faalt
        # pas bij het renderen.
        sections = []
        for topic in TOPIC_ORDER:
            if buckets.get(topic):
                sections.append({"topic": topic, "label": TOPIC_LABEL[topic],
                                 "rijen": buckets[topic]})
        if buckets.get("overig"):
            sections.append({"topic": "overig", "label": "Overig",
                             "rijen": buckets["overig"]})

        grouped[key] = {
            "important": important,
            "sections": sections,
            "count": len(in_channel),
            "sources": len({i["source_name"] for i in in_channel}),
        }
    return grouped


def prepare(items: list[dict]) -> list[dict]:
    """Voegt de afgeleide velden toe die de template nodig heeft."""
    for item in items:
        item["relative"] = relative_time(item.get("published"))
        item["flag"] = "🇳🇱" if item.get("region") == "nl" else "🌍"
        item["topic_labels"] = [TOPIC_LABEL.get(t, t) for t in item.get("topics", [])]
        # Voor het zoekveld: alles waarop client-side gefilterd mag worden.
        item["haystack"] = " ".join([
            item.get("title", ""), item.get("summary", ""),
            item.get("source_name", ""), " ".join(item.get("topic_labels", [])),
        ]).lower()
    return items


def domain(url: str) -> str:
    """nos.nl uit https://www.nos.nl/artikel/123 — voor de 'ook bij'-regel."""
    match = re.match(r"https?://(?:www\.)?([^/:?#]+)", url or "")
    return match.group(1) if match else (url or "")


def environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["dutch_date"] = dutch_date
    env.filters["domain"] = domain
    return env


def archive_entries() -> list[dict]:
    entries = []
    for path in sorted((DATA_DIR / "digest").glob("*.json"), reverse=True)[:ARCHIVE_LIMIT]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        items = payload.get("items", [])
        entries.append({
            "date": payload.get("date", path.stem),
            "count": len(items),
            "ai": sum(1 for i in items if i.get("channel") == "ai"),
            "bieb": sum(1 for i in items if i.get("channel") == "bieb"),
        })
    return entries


def render_digest(env, payload: dict, *, is_latest: bool, archive: list[dict]) -> str:
    items = prepare(payload.get("items", []))
    return env.get_template("digest.html.j2").render(
        date=payload.get("date", ""),
        generated_at=payload.get("generated_at", ""),
        grouped=group_items(items),
        channels=CHANNELS,
        total=len(items),
        source_count=len({i["source_name"] for i in items}),
        is_sample=bool(payload.get("is_sample")),
        is_empty=bool(payload.get("is_empty")),
        is_latest=is_latest,
        archive=archive,
        base="" if is_latest else "../",
        digest_json=json.dumps(payload, ensure_ascii=False),
    )


def run(digest_path: Path | None, use_sample: bool) -> int:
    if use_sample:
        digest_path = DATA_DIR / "sample" / "preview.json"
        if not digest_path.exists():
            print("Geen voorbeelddata. Draai eerst scripts/sample_data.py.", file=sys.stderr)
            return 1

    if digest_path is None:
        available = sorted((DATA_DIR / "digest").glob("*.json"))
        digest_path = available[-1] if available else None

    if digest_path is None:
        # Eerste run, of het verrijken is nooit gelukt. Een lege pagina is beter
        # dan een gefaalde deploy: de site staat dan tenminste live en vertelt
        # wat eraan schort. Het vangnet "publiceer de vorige digest" heeft
        # namelijk geen vorige om op terug te vallen.
        print("Nog geen digest; lege site gebouwd.", file=sys.stderr)
        payload = {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "is_empty": True,
            "items": [],
        }
    else:
        payload = json.loads(digest_path.read_text(encoding="utf-8"))
    env = environment()
    archive = archive_entries()

    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "assets").mkdir(exist_ok=True)

    (SITE_DIR / "index.html").write_text(
        render_digest(env, payload, is_latest=True, archive=archive), encoding="utf-8"
    )
    (SITE_DIR / "assets" / "digest.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )

    (SITE_DIR / "archief.html").write_text(
        env.get_template("archief.html.j2").render(
            archive=archive, base="", channels=CHANNELS,
        ),
        encoding="utf-8",
    )

    for bestand in ("opgeslagen.html", "beheer.html"):
        (SITE_DIR / bestand).write_text(
            env.get_template(bestand + ".j2").render(base=""), encoding="utf-8"
        )

    # Het bronrapport van de laatste verify-run gaat mee naar de site, zodat
    # /beheer de status van de repo-bronnen kan tonen zonder Supabase.
    rapport = DATA_DIR / "source_report.json"
    if rapport.exists():
        shutil.copyfile(rapport, SITE_DIR / "assets" / "source_report.json")

    # Elke digest ook als eigen pagina, zodat het archief zonder JS werkt.
    archive_dir = SITE_DIR / "archief"
    archive_dir.mkdir(exist_ok=True)
    for entry in archive:
        source = DATA_DIR / "digest" / f"{entry['date']}.json"
        if not source.exists():
            continue
        old = json.loads(source.read_text(encoding="utf-8"))
        (archive_dir / f"{entry['date']}.html").write_text(
            render_digest(env, old, is_latest=False, archive=archive), encoding="utf-8"
        )

    print(f"site/ gebouwd: {len(payload.get('items', []))} items, "
          f"{len(archive)} in het archief", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--digest", type=Path, help="specifiek digest-bestand")
    parser.add_argument("--sample", action="store_true",
                        help="bouw met voorbeelddata om het ontwerp te beoordelen")
    args = parser.parse_args()
    return run(args.digest, args.sample)


if __name__ == "__main__":
    sys.exit(main())
