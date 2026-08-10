#!/usr/bin/env python3
"""Genereert een VAPID-sleutelpaar voor de pushmeldingen.

VAPID is hoe een pushdienst (die van Google, Apple, Mozilla) weet dat een
melding echt van jouw server komt. Je maakt het paar één keer aan: de publieke
sleutel gaat in de frontend, de privésleutel in een repo-secret.

    python scripts/gen_vapid.py

Draai dit maar één keer. Genereer je later een nieuw paar, dan zijn alle
bestaande abonnementen ongeldig en moet je op elk apparaat opnieuw
"Meldingen aan" klikken.
"""

from __future__ import annotations

import base64
import sys

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid01


def publieke_sleutel(vapid: Vapid01) -> str:
    """De publieke sleutel als base64url, de vorm die de browser verwacht.

    py_vapid geeft alleen PEM terug. De Push API wil het ongecomprimeerde
    X9.62-punt (65 bytes) in base64url zonder opvulling — dat is wat je aan
    pushManager.subscribe meegeeft als applicationServerKey.
    """
    ruw = vapid.public_key.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    return base64.urlsafe_b64encode(ruw).decode("ascii").rstrip("=")


def main() -> int:
    vapid = Vapid01()
    vapid.generate_keys()

    prive = vapid.private_pem().decode("utf-8").strip()
    publiek = publieke_sleutel(vapid)

    print()
    print("=" * 72)
    print("1. Repo-secret  VAPID_PRIVATE_KEY")
    print("   GitHub -> Settings -> Secrets and variables -> Actions")
    print("   Plak hieronder alles, inclusief de BEGIN- en END-regels:")
    print("=" * 72)
    print(prive)
    print()
    print("=" * 72)
    print("2. Repo-secret  VAPID_CLAIM_EMAIL")
    print("   Waarde: mailto:jouw@adres.nl")
    print("=" * 72)
    print()
    print("=" * 72)
    print("3. site/config.js  ->  vapidPublicKey")
    print("=" * 72)
    print(publiek)
    print()
    print("Bewaar de privésleutel nergens anders. Hij hoort niet in de repo,")
    print("niet in config.js, en niet in een chatvenster.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
