#!/usr/bin/env python3
"""X / Twitter — losse, uitschakelbare module. Standaard uit.

Dit is de fragielste schakel in het hele project en dat is geen implementatiefout:
er bestaat geen gratis officiële leesroute meer voor X. Deze module leunt op een
RSS-bridge van derden. Publieke Nitter-instances zijn vrijwel allemaal verdwenen
en rss.app laat op het gratis plan maar een handvol feeds toe.

Daarom gedraagt deze module zich als een bijvangst en niet als een bron: elke
fout wordt gelogd en teruggegeven als een lege lijst. collect.py vangt hem
bovendien nog een keer af. De dagelijkse run mag hier nooit op stuklopen.

Losse test:
    python scripts/collect_x.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import feedparser

from collect import (
    FEED_ACCEPT,
    build_item,
    entry_datetime,
    fetch,
    html_to_text,
    log_error,
    make_client,
    yaml_rt,
)

CONFIG_PATH = Path(__file__).resolve().parent.parent / "sources" / "x.yaml"


def _feed_url(config: dict, account: dict) -> str:
    """Eigen feed_url wint; anders het bridge-sjabloon met {handle} ingevuld."""
    explicit = (account.get("feed_url") or "").strip()
    if explicit:
        return explicit
    template = (config.get("bridge_url_template") or "").strip()
    if not template:
        return ""
    return template.replace("{handle}", str(account.get("handle", "")).lstrip("@"))


def collect_x() -> list[dict]:
    """Haalt maximaal `max_accounts` accounts op. Faalt altijd stil."""
    try:
        with CONFIG_PATH.open(encoding="utf-8") as handle:
            config = yaml_rt.load(handle)
    except Exception as exc:  # noqa: BLE001
        log_error("X", "collect_x_config", exc)
        return []

    if not config or not config.get("enabled", False):
        return []

    accounts = list(config.get("accounts") or [])[: int(config.get("max_accounts", 10))]
    if not accounts:
        return []

    items: list[dict] = []
    with make_client() as client:
        for account in accounts:
            handle = str(account.get("handle", "?")).lstrip("@")
            url = _feed_url(config, account)
            if not url:
                log_error(f"X/@{handle}", "collect_x", "geen feed_url en geen bridge-sjabloon")
                continue

            source = {
                "name": f"X/@{handle}",
                "priority": int(account.get("priority", 4)),
                "max_items": int(account.get("max_items", 10)),
            }
            try:
                response = fetch(client, url, attempts=2, headers={"Accept": FEED_ACCEPT})
                feed = feedparser.parse(response.content)
                if not feed.entries:
                    raise ValueError(f"HTTP {response.status_code} maar 0 items")

                for entry in feed.entries[: source["max_items"]]:
                    text = html_to_text(entry.get("summary") or entry.get("title") or "")
                    if not text:
                        continue
                    item = build_item(
                        url=entry.get("link") or "",
                        # Bridges geven zelden een echte titel; de eerste zin is genoeg.
                        title=text[:140],
                        raw_text=text,
                        published=entry_datetime(entry),
                        source=source,
                        config=config,
                        source_type="x",
                    )
                    if item:
                        items.append(item)
            except Exception as exc:  # noqa: BLE001 - bridge mag altijd omvallen
                log_error(f"X/@{handle}", "collect_x", exc, url=url)
                continue

    return items


if __name__ == "__main__":
    collected = collect_x()
    print(json.dumps(collected, ensure_ascii=False, indent=2))
    print(f"\n{len(collected)} items", file=sys.stderr)
