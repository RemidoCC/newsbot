#!/usr/bin/env python3
"""Stuurt één pushmelding na een geslaagde run.

Draait als laatste stap in de workflow. Leest de abonnementen uit Supabase met
de service-role key: die tabel kan niet publiek leesbaar zijn, want met een
endpoint plus sleutels kan iedereen jou meldingen sturen.

Geen digest of een lege digest betekent geen melding. Stilte is hier het goede
gedrag — een melding "0 items" is precies het soort ruis waar deze bot niet
over hoort te gaan.

Gebruik:
    python scripts/send_push.py                 # nieuwste digest
    python scripts/send_push.py --dry-run       # tonen wat er verstuurd zou worden
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx
from pywebpush import WebPushException, webpush

from collect import DATA_DIR, supabase_config

TTL = 24 * 3600


def nieuwste_digest() -> dict | None:
    bestanden = sorted((DATA_DIR / "digest").glob("*.json"))
    if not bestanden:
        return None
    try:
        return json.loads(bestanden[-1].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def bericht(digest: dict) -> tuple[str, str] | None:
    items = digest.get("items", [])
    if not items:
        return None
    ai = sum(1 for i in items if i.get("channel") == "ai")
    bieb = sum(1 for i in items if i.get("channel") == "bieb")

    delen = []
    if ai:
        delen.append(f"{ai} AI-{'item' if ai == 1 else 'items'}")
    if bieb:
        delen.append(f"{bieb} over bibliotheken")
    return "Nieuwe digest", ", ".join(delen)


def abonnementen(url: str, service_key: str) -> list[dict]:
    response = httpx.get(
        f"{url}/rest/v1/push_subscriptions",
        params={"select": "id,endpoint,p256dh,auth"},
        headers={"apikey": service_key, "Authorization": f"Bearer {service_key}"},
        timeout=20.0,
    )
    response.raise_for_status()
    return response.json()


def verwijder_abonnement(url: str, service_key: str, abonnement_id: str) -> None:
    """Een endpoint dat 404 of 410 geeft is voorgoed weg (app verwijderd,
    browserdata gewist). Opruimen, anders blijft de lijst groeien."""
    try:
        httpx.delete(
            f"{url}/rest/v1/push_subscriptions",
            params={"id": f"eq.{abonnement_id}"},
            headers={"apikey": service_key, "Authorization": f"Bearer {service_key}"},
            timeout=20.0,
        )
    except httpx.HTTPError as exc:
        print(f"  ! opruimen mislukt: {exc}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    digest = nieuwste_digest()
    if digest is None:
        print("Geen digest gevonden, geen melding.", file=sys.stderr)
        return 0

    inhoud = bericht(digest)
    if inhoud is None:
        print("Lege digest, geen melding.", file=sys.stderr)
        return 0

    titel, tekst = inhoud
    print(f'Melding: "{titel}" — "{tekst}"', file=sys.stderr)
    if args.dry_run:
        return 0

    url, _ = supabase_config()
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    prive = os.environ.get("VAPID_PRIVATE_KEY", "").strip()
    claim = os.environ.get("VAPID_CLAIM_EMAIL", "").strip()

    ontbreekt = [naam for naam, waarde in [
        ("SUPABASE_URL of site/config.js", url),
        ("SUPABASE_SERVICE_ROLE_KEY", service_key),
        ("VAPID_PRIVATE_KEY", prive),
        ("VAPID_CLAIM_EMAIL", claim),
    ] if not waarde]
    if ontbreekt:
        # Geen fout: zolang push niet is ingericht hoort de run gewoon te slagen.
        print(f"Push overgeslagen, ontbreekt: {', '.join(ontbreekt)}", file=sys.stderr)
        return 0

    try:
        lijst = abonnementen(url, service_key)
    except httpx.HTTPError as exc:
        print(f"Kon abonnementen niet ophalen: {exc}", file=sys.stderr)
        return 0

    if not lijst:
        print("Nog geen abonnementen.", file=sys.stderr)
        return 0

    lading = json.dumps({"title": titel, "body": tekst}, ensure_ascii=False)
    gelukt = 0
    for abonnement in lijst:
        try:
            webpush(
                subscription_info={
                    "endpoint": abonnement["endpoint"],
                    "keys": {"p256dh": abonnement["p256dh"], "auth": abonnement["auth"]},
                },
                data=lading,
                vapid_private_key=prive,
                vapid_claims={"sub": claim},
                ttl=TTL,
            )
            gelukt += 1
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None)
            print(f"  ! {abonnement['endpoint'][:60]}… gaf {status or exc}", file=sys.stderr)
            if status in (404, 410):
                verwijder_abonnement(url, service_key, abonnement["id"])

    print(f"{gelukt} van {len(lijst)} meldingen verstuurd.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
