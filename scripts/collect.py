#!/usr/bin/env python3
"""Haalt alle bronnen op en normaliseert ze naar één raw-bestand per dag.

Geen LLM in deze stap. Puur ophalen, normaliseren, en fouten overleven:
elke bron draait in een eigen try/except, elke fout gaat naar data/errors.json,
en de run loopt altijd door. Eén kapotte feed mag de digest nooit slopen.

Gebruik:
    python scripts/collect.py                      # -> data/raw/YYYY-MM-DD.json
    python scripts/collect.py --verify             # bronnen testen, niets ophalen
    python scripts/collect.py --verify --apply     # + werkende URL terugschrijven
    python scripts/collect.py --only Tweakers      # losse bron, voor debuggen
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import feedparser
import httpx
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = ROOT / "sources"
DATA_DIR = ROOT / "data"
ERRORS_PATH = DATA_DIR / "errors.json"

SOURCE_FILES = ["ai_int.yaml", "ai_nl.yaml", "bieb_nl.yaml", "bieb_int.yaml"]

USER_AGENT = (
    "newsbot/0.1 (persoonlijke nieuwsdigest; +https://github.com/RemidoCC/newsbot)"
)
FEED_ACCEPT = (
    "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.9, */*;q=0.8"
)
MAX_RAW_TEXT = 1500
ERROR_RETENTION_DAYS = 14

# Query-parameters die niets over de inhoud zeggen en dus uit de dedupe-hash moeten.
TRACKING_PARAM = re.compile(
    r"^(utm_.*|ref|ref_src|referrer|fbclid|gclid|mc_cid|mc_eid|igshid|"
    r"source|cmpid|campaign|s_cid|at_medium|at_campaign|__twitter_impression)$",
    re.IGNORECASE,
)

# Grove taaldetectie. Genoeg om NL van EN te scheiden; geen extra dependency waard.
DUTCH_MARKERS = (
    " de ", " het ", " een ", " van ", " voor ", " met ", " niet ", " ook ",
    " zijn ", " wordt ", " bij ", " naar ", " deze ", " maar ", " over ",
)

yaml_rt = YAML(typ="rt")
yaml_rt.preserve_quotes = True
yaml_rt.width = 4096

_errors: list[dict] = []
_reddit_token: str | None = None


# --------------------------------------------------------------------------
# Fouten
# --------------------------------------------------------------------------

def log_error(source: str, stage: str, exc: BaseException | str, **extra) -> None:
    """Onthoudt een fout. Wordt aan het eind weggeschreven naar errors.json."""
    detail = exc if isinstance(exc, str) else f"{type(exc).__name__}: {exc}"
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "stage": stage,
        "error": detail[:500],
    }
    entry.update(extra)
    _errors.append(entry)
    print(f"  ! {source}: {detail[:200]}", file=sys.stderr)


def flush_errors() -> None:
    """Voegt de fouten van deze run toe aan errors.json en snoeit oude weg."""
    if not _errors:
        return
    try:
        existing = json.loads(ERRORS_PATH.read_text(encoding="utf-8"))
        if not isinstance(existing, list):
            existing = []
    except (OSError, json.JSONDecodeError):
        existing = []

    cutoff = datetime.now(timezone.utc) - timedelta(days=ERROR_RETENTION_DAYS)
    kept = []
    for item in existing:
        try:
            if dateparser.isoparse(item["ts"]) >= cutoff:
                kept.append(item)
        except (KeyError, ValueError, TypeError):
            continue

    ERRORS_PATH.parent.mkdir(parents=True, exist_ok=True)
    ERRORS_PATH.write_text(
        json.dumps(kept + _errors, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


# --------------------------------------------------------------------------
# URL's en tekst
# --------------------------------------------------------------------------

def normalize_url(url: str) -> str:
    """Kale vorm van een URL, alleen voor de dedupe-hash — niet om mee te fetchen.

    Strips tracking-parameters, fragment, trailing slash en het www-voorvoegsel,
    zodat dezelfde pagina onder twee URL's toch één id oplevert.
    """
    if not url:
        return ""
    parts = urlsplit(url.strip())
    scheme = "https" if parts.scheme.lower() in ("", "http", "https") else parts.scheme.lower()
    netloc = parts.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    query = urlencode(
        [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
         if not TRACKING_PARAM.match(k)]
    )
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((scheme, netloc, path, query, ""))


def item_id(url: str) -> str:
    return hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()


def html_to_text(html: str) -> str:
    if not html:
        return ""
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def guess_language(text: str, default: str) -> str:
    if not text:
        return default
    haystack = f" {text.lower()} "
    if sum(1 for marker in DUTCH_MARKERS if marker in haystack) >= 3:
        return "nl"
    return default


def matches_keywords(source: dict, *fields: str) -> bool:
    """True als de bron geen filter heeft, of als een van de woorden voorkomt.

    Matcht op woordgrens, zodat "ai" wel "AI-verordening" raakt maar niet "detail".
    """
    keywords = source.get("include_keywords")
    if not keywords:
        return True
    haystack = " ".join(f for f in fields if f).lower()
    return any(
        re.search(rf"(?<!\w){re.escape(str(k).lower())}(?!\w)", haystack) for k in keywords
    )


def entry_datetime(entry) -> str | None:
    """ISO 8601 met tijdzone, of None als de feed geen bruikbare datum geeft."""
    for key in ("published", "updated", "created"):
        raw = entry.get(key)
        if raw:
            try:
                parsed = dateparser.parse(raw)
                if parsed is not None:
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    return parsed.isoformat(timespec="seconds")
            except (ValueError, TypeError, OverflowError):
                pass
    for key in ("published_parsed", "updated_parsed"):
        struct = entry.get(key)
        if struct:
            try:
                return datetime(*struct[:6], tzinfo=timezone.utc).isoformat(timespec="seconds")
            except (ValueError, TypeError):
                pass
    return None


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

def make_client() -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(25.0, connect=10.0),
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )


def fetch(client: httpx.Client, url: str, *, attempts: int = 3, **kwargs) -> httpx.Response:
    """GET met exponentiële backoff op tijdelijke fouten (2s, 4s, 8s)."""
    delay = 2.0
    last: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = client.get(url, **kwargs)
            if response.status_code in (408, 429, 500, 502, 503, 504) and attempt < attempts:
                time.sleep(delay)
                delay *= 2
                continue
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            # De statuscodes die het wel waard zijn hierboven al afgevangen.
            # Wat hier komt is permanent (404, 403, 410): niet nog eens proberen.
            last = exc
            break
        except (httpx.HTTPError, httpx.InvalidURL, httpx.UnsupportedProtocol) as exc:
            last = exc
            if attempt == attempts:
                break
            time.sleep(delay)
            delay *= 2
    raise last if last else RuntimeError(f"kon {url} niet ophalen")


# --------------------------------------------------------------------------
# Bronbestanden
# --------------------------------------------------------------------------

def load_source_files() -> list[tuple[Path, dict]]:
    """Leest de YAML-bestanden. Een kapot bestand slaat de rest niet plat."""
    loaded = []
    for filename in SOURCE_FILES:
        path = SOURCES_DIR / filename
        try:
            with path.open(encoding="utf-8") as handle:
                loaded.append((path, yaml_rt.load(handle)))
        except Exception as exc:  # noqa: BLE001 - bewust breed, run moet doorgaan
            log_error(filename, "load_sources", exc)
    return loaded


def build_item(
    *, url: str, title: str, raw_text: str, published: str | None,
    source: dict, config: dict, source_type: str,
) -> dict | None:
    """Normaliseert naar het itemschema. Geen bruikbare URL of titel = weggooien."""
    url = (url or "").strip()
    title = (title or "").strip()
    if not url or not title:
        return None
    if not urlsplit(url).scheme.startswith("http"):
        return None
    text = (raw_text or "")[:MAX_RAW_TEXT]
    return {
        "id": item_id(url),
        "title": title,
        "url": url,
        "source_name": source["name"],
        "source_type": source_type,
        "channel_hint": config.get("channel", "ai"),
        "region_hint": config.get("region", "int"),
        "published": published,
        "raw_text": text,
        "language": guess_language(f"{title} {text}", config.get("language", "en")),
        "priority": int(source.get("priority", 3)),
    }


# --------------------------------------------------------------------------
# Collectors
# --------------------------------------------------------------------------

def collect_rss(client: httpx.Client, source: dict, config: dict) -> list[dict]:
    url = (source.get("url") or "").strip()
    if not url:
        raise ValueError("geen url ingesteld (zie README)")

    response = fetch(client, url, headers={"Accept": FEED_ACCEPT})
    feed = feedparser.parse(response.content)
    if not feed.entries:
        raise ValueError(
            f"HTTP {response.status_code} maar 0 items "
            f"(content-type: {response.headers.get('content-type', '?')})"
        )

    source_type = source.get("type", "rss")
    items = []
    for entry in feed.entries[: int(source.get("max_items", 30))]:
        title = html_to_text(entry.get("title") or "")
        body = ""
        if entry.get("content"):
            body = entry["content"][0].get("value") or ""
        raw_text = html_to_text(body or entry.get("summary") or "")
        if not matches_keywords(source, title, raw_text):
            continue
        item = build_item(
            url=entry.get("link") or "",
            title=title,
            raw_text=raw_text,
            published=entry_datetime(entry),
            source=source,
            config=config,
            source_type=source_type,
        )
        if item:
            items.append(item)
    return items


def reddit_token(client: httpx.Client) -> str:
    """Client-credentials token. Eén keer per run, gedeeld door alle subreddits."""
    global _reddit_token
    if _reddit_token:
        return _reddit_token

    client_id = os.environ.get("REDDIT_CLIENT_ID", "").strip()
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "").strip()
    if not (client_id and client_secret):
        raise RuntimeError(
            "REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET ontbreken. Reddit's "
            "onauthenticated .json is sinds mei 2026 dicht; zie README stap 4."
        )

    response = client.post(
        "https://www.reddit.com/api/v1/access_token",
        data={"grant_type": "client_credentials"},
        auth=(client_id, client_secret),
    )
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("Reddit gaf geen access_token terug")
    _reddit_token = token
    return token


def collect_reddit(client: httpx.Client, source: dict, config: dict) -> list[dict]:
    subreddit = source["subreddit"]
    token = reddit_token(client)
    response = fetch(
        client,
        f"https://oauth.reddit.com/r/{subreddit}/{source.get('listing', 'top')}",
        headers={"Authorization": f"bearer {token}"},
        params={
            "t": source.get("timeframe", "day"),
            "limit": int(source.get("max_items", 25)),
            "raw_json": 1,
        },
    )

    min_score = int(source.get("min_score", 0))
    items = []
    for child in response.json().get("data", {}).get("children", []):
        post = child.get("data", {})
        if post.get("stickied") or post.get("score", 0) < min_score:
            continue
        permalink = f"https://www.reddit.com{post.get('permalink', '')}"
        # Bij een linkpost is de externe URL de echte bron; bij een selfpost de thread.
        url = permalink if post.get("is_self") else (post.get("url") or permalink)
        title = post.get("title") or ""
        raw_text = html_to_text(post.get("selftext") or "")
        if not matches_keywords(source, title, raw_text):
            continue
        published = None
        if post.get("created_utc"):
            published = datetime.fromtimestamp(
                post["created_utc"], tz=timezone.utc
            ).isoformat(timespec="seconds")
        item = build_item(
            url=url, title=title, raw_text=raw_text, published=published,
            source=source, config=config, source_type="reddit",
        )
        if item:
            items.append(item)
    return items


def collect_hn(client: httpx.Client, source: dict, config: dict) -> list[dict]:
    min_points = int(source.get("min_points", 50))
    response = fetch(
        client,
        source.get("url") or "https://hn.algolia.com/api/v1/search_by_date",
        params={
            "tags": "story",
            "query": source.get("query", "AI"),
            "numericFilters": f"points>={min_points}",
            "hitsPerPage": int(source.get("max_items", 30)),
        },
    )

    items = []
    for hit in response.json().get("hits", []):
        object_id = hit.get("objectID")
        url = hit.get("url") or (
            f"https://news.ycombinator.com/item?id={object_id}" if object_id else ""
        )
        title = hit.get("title") or hit.get("story_title") or ""
        raw_text = html_to_text(hit.get("story_text") or "")
        if not matches_keywords(source, title, raw_text):
            continue
        item = build_item(
            url=url, title=title, raw_text=raw_text, published=hit.get("created_at"),
            source=source, config=config, source_type="hn",
        )
        if item:
            items.append(item)
    return items


COLLECTORS = {
    "rss": collect_rss,
    "newsletter": collect_rss,
    "reddit": collect_reddit,
    "hn": collect_hn,
}


# --------------------------------------------------------------------------
# Verify
# --------------------------------------------------------------------------

def probe_feed(client: httpx.Client, url: str) -> dict:
    """Test één feed-URL echt. Gooit op alles wat geen bruikbare feed is."""
    response = fetch(client, url, attempts=2, headers={"Accept": FEED_ACCEPT})
    feed = feedparser.parse(response.content)
    entries = feed.entries or []
    content_type = response.headers.get("content-type", "?").split(";")[0]
    if not entries:
        raise ValueError(f"HTTP {response.status_code}, content-type {content_type}, 0 items")

    # Sorteren op de geparste datum, niet op de string: verschillende offsets
    # zetten anders de verkeerde bovenaan.
    dates = []
    for entry in entries:
        iso = entry_datetime(entry)
        if iso:
            try:
                dates.append((dateparser.isoparse(iso), iso))
            except ValueError:
                pass
    return {
        "http_status": response.status_code,
        "final_url": str(response.url),
        "content_type": content_type,
        "feed_title": (feed.feed.get("title") or "").strip()[:80],
        "entries": len(entries),
        "newest": max(dates)[1] if dates else None,
        "dated_entries": len(dates),
    }


def discover_feeds(client: httpx.Client, homepage: str) -> list[str]:
    """Zoekt <link rel=alternate type=...xml> op de homepage. Verzint niets."""
    response = fetch(client, homepage, attempts=2)
    soup = BeautifulSoup(response.text, "html.parser")
    found = []
    for tag in soup.find_all("link"):
        rel = " ".join(tag.get("rel") or []).lower()
        type_ = (tag.get("type") or "").lower()
        href = tag.get("href")
        if "alternate" in rel and href and any(x in type_ for x in ("rss", "atom", "xml")):
            absolute = urljoin(str(response.url), href)
            if absolute not in found:
                found.append(absolute)
    return found[:5]


def verify_source(client: httpx.Client, source: dict, filename: str) -> dict:
    """Probeert url, dan fallback_urls, dan autodiscovery. Rapporteert wat won."""
    result = {
        "name": source.get("name", "?"),
        "file": filename,
        "type": source.get("type", "rss"),
        "enabled": bool(source.get("enabled", False)),
        "configured_url": source.get("url") or "",
        "ok": False,
        "winning_url": None,
        "via": None,
        "detail": None,
        "attempts": [],
    }

    if not result["enabled"]:
        result["detail"] = "staat uit"
        return result

    source_type = result["type"]

    if source_type == "reddit":
        try:
            token = reddit_token(client)
            response = fetch(
                client,
                f"https://oauth.reddit.com/r/{source['subreddit']}/{source.get('listing', 'top')}",
                attempts=2,
                headers={"Authorization": f"bearer {token}"},
                params={"t": source.get("timeframe", "day"), "limit": 5, "raw_json": 1},
            )
            count = len(response.json().get("data", {}).get("children", []))
            result.update(ok=count > 0, via="oauth", winning_url=f"r/{source['subreddit']}",
                          detail=f"OAuth ok, {count} posts")
        except Exception as exc:  # noqa: BLE001
            result["detail"] = f"{type(exc).__name__}: {exc}"[:300]
        return result

    if source_type == "hn":
        try:
            response = fetch(client, source["url"], attempts=2, params={
                "tags": "story", "query": source.get("query", "AI"),
                "numericFilters": f"points>={source.get('min_points', 50)}", "hitsPerPage": 5,
            })
            hits = len(response.json().get("hits", []))
            result.update(ok=hits > 0, via="algolia", winning_url=source["url"],
                          detail=f"{hits} hits boven {source.get('min_points', 50)} punten")
        except Exception as exc:  # noqa: BLE001
            result["detail"] = f"{type(exc).__name__}: {exc}"[:300]
        return result

    candidates = [(source.get("url") or "", "url")]
    candidates += [(u, "fallback") for u in (source.get("fallback_urls") or [])]
    candidates = [(u, via) for u, via in candidates if u]

    if not candidates and not source.get("homepage"):
        result["detail"] = "geen url en geen homepage ingesteld"
        return result

    for url, via in candidates:
        try:
            probe = probe_feed(client, url)
            result["attempts"].append({"url": url, "ok": True, **probe})
            result.update(ok=True, winning_url=probe["final_url"], via=via,
                          detail=f"{probe['entries']} items, nieuwste {probe['newest']}")
            return result
        except Exception as exc:  # noqa: BLE001
            result["attempts"].append(
                {"url": url, "ok": False, "error": f"{type(exc).__name__}: {exc}"[:200]}
            )

    homepage = source.get("homepage")
    if homepage:
        try:
            for url in discover_feeds(client, homepage):
                if any(a["url"] == url for a in result["attempts"]):
                    continue
                try:
                    probe = probe_feed(client, url)
                    result["attempts"].append({"url": url, "ok": True, **probe})
                    result.update(ok=True, winning_url=probe["final_url"], via="autodiscovery",
                                  detail=f"gevonden via {homepage}: {probe['entries']} items")
                    return result
                except Exception as exc:  # noqa: BLE001
                    result["attempts"].append(
                        {"url": url, "ok": False, "error": f"{type(exc).__name__}: {exc}"[:200]}
                    )
        except Exception as exc:  # noqa: BLE001
            result["attempts"].append(
                {"url": homepage, "ok": False, "error": f"autodiscovery: {exc}"[:200]}
            )

    result["detail"] = "geen enkele kandidaat leverde een feed op"
    return result


def render_report(results: list[dict]) -> str:
    ok = [r for r in results if r["ok"]]
    off = [r for r in results if not r["enabled"]]
    broken = [r for r in results if r["enabled"] and not r["ok"]]

    lines = [
        "# Bronverificatie",
        "",
        f"Gedraaid op {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}.",
        "",
        f"**{len(ok)} werkend** · **{len(broken)} kapot** · {len(off)} uitgezet "
        f"· {len(results)} totaal",
        "",
        "| Bron | Bestand | Status | Via | Details |",
        "| --- | --- | --- | --- | --- |",
    ]
    for result in sorted(results, key=lambda r: (r["ok"], not r["enabled"], r["name"])):
        if not result["enabled"]:
            status = "uit"
        else:
            status = "ok" if result["ok"] else "KAPOT"
        detail = (result.get("detail") or "").replace("|", "\\|")[:120]
        lines.append(
            f"| {result['name']} | {result['file']} | {status} | "
            f"{result.get('via') or '-'} | {detail} |"
        )

    changed = [r for r in ok if r["via"] in ("fallback", "autodiscovery")]
    if changed:
        lines += ["", "## URL's die zijn bijgesteld", ""]
        for result in changed:
            lines.append(
                f"- **{result['name']}**: `{result['configured_url'] or '(leeg)'}` "
                f"-> `{result['winning_url']}` (via {result['via']})"
            )

    if broken:
        lines += ["", "## Kapotte bronnen", ""]
        for result in broken:
            lines.append(f"- **{result['name']}** — {result.get('detail')}")
            for attempt in result["attempts"]:
                if not attempt.get("ok"):
                    lines.append(f"  - `{attempt['url']}` — {attempt.get('error')}")
    return "\n".join(lines) + "\n"


def run_verify(apply_fixes: bool, only: str | None) -> int:
    files = load_source_files()
    results: list[dict] = []
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    with make_client() as client:
        for path, config in files:
            if not config or "sources" not in config:
                log_error(path.name, "verify", "geen 'sources' in dit bestand")
                continue
            for source in config["sources"]:
                if only and only.lower() not in str(source.get("name", "")).lower():
                    continue
                print(f"-> {source.get('name')}", file=sys.stderr)
                try:
                    result = verify_source(client, source, path.name)
                except Exception as exc:  # noqa: BLE001 - verify mag nooit klappen
                    result = {
                        "name": source.get("name", "?"), "file": path.name,
                        "type": source.get("type", "rss"), "enabled": True, "ok": False,
                        "configured_url": source.get("url", ""), "winning_url": None,
                        "via": None, "detail": f"{type(exc).__name__}: {exc}"[:300],
                        "attempts": [],
                    }
                results.append(result)

                if apply_fixes and result["enabled"]:
                    source["verified"] = bool(result["ok"])
                    source["verified_at"] = now
                    if result["ok"] and result["via"] in ("fallback", "autodiscovery"):
                        source["url"] = result["winning_url"]

    if apply_fixes:
        for path, config in files:
            try:
                with path.open("w", encoding="utf-8") as handle:
                    yaml_rt.dump(config, handle)
            except Exception as exc:  # noqa: BLE001
                log_error(path.name, "verify_write", exc)

    report = render_report(results)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "source_report.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (DATA_DIR / "source_report.md").write_text(report, encoding="utf-8")
    print(report)

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(report)

    # Bewust altijd 0: een kapotte bron is informatie, geen reden om te falen.
    return 0


# --------------------------------------------------------------------------
# Normale run
# --------------------------------------------------------------------------

def run_collect(only: str | None) -> int:
    items: list[dict] = []
    per_source: dict[str, int] = {}

    with make_client() as client:
        for path, config in load_source_files():
            if not config or "sources" not in config:
                log_error(path.name, "collect", "geen 'sources' in dit bestand")
                continue
            for source in config["sources"]:
                name = str(source.get("name", "?"))
                if only and only.lower() not in name.lower():
                    continue
                if not source.get("enabled", False):
                    continue
                collector = COLLECTORS.get(source.get("type", "rss"))
                if collector is None:
                    log_error(name, "collect", f"onbekend brontype {source.get('type')!r}")
                    continue
                try:
                    found = collector(client, source, config)
                except Exception as exc:  # noqa: BLE001 - één bron mag de run niet slopen
                    log_error(name, "collect", exc, url=source.get("url"))
                    continue
                per_source[name] = len(found)
                items.extend(found)
                print(f"  {name}: {len(found)}", file=sys.stderr)

    # X draait als losse module en mag onder geen beding de run tegenhouden.
    try:
        # collect.py draait als __main__. Zonder deze alias importeert collect_x
        # een tweede kopie van deze module, met een eigen _errors-lijst die
        # flush_errors() nooit te zien krijgt.
        sys.modules.setdefault("collect", sys.modules["__main__"])
        from collect_x import collect_x  # noqa: PLC0415 - optioneel, bewust laat geladen

        x_items = collect_x()
        if x_items:
            per_source["X"] = len(x_items)
            items.extend(x_items)
    except Exception as exc:  # noqa: BLE001
        log_error("X", "collect_x", exc)

    # Binnen één run kan hetzelfde artikel via twee feeds binnenkomen.
    unique: dict[str, dict] = {}
    for item in items:
        unique.setdefault(item["id"], item)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = DATA_DIR / "raw" / f"{today}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "counts": {
            "raw": len(items),
            "unique": len(unique),
            "sources_ok": len(per_source),
            "sources_failed": len({e["source"] for e in _errors}),
        },
        "per_source": per_source,
        "items": list(unique.values()),
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"\n{len(unique)} unieke items uit {len(per_source)} bronnen "
        f"-> {out_path.relative_to(ROOT)}",
        file=sys.stderr,
    )
    if _errors:
        print(f"{len(_errors)} bronnen gaven een fout, zie data/errors.json", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true",
                        help="test elke bron-URL echt, haal niets op")
    parser.add_argument("--apply", action="store_true",
                        help="met --verify: schrijf werkende URL's terug in de YAML")
    parser.add_argument("--only", metavar="NAAM",
                        help="beperk tot bronnen waarvan de naam dit bevat")
    args = parser.parse_args()

    try:
        if args.verify:
            return run_verify(apply_fixes=args.apply, only=args.only)
        if args.apply:
            parser.error("--apply werkt alleen samen met --verify")
        return run_collect(only=args.only)
    finally:
        flush_errors()


if __name__ == "__main__":
    sys.exit(main())
