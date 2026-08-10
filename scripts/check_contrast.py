#!/usr/bin/env python3
"""Rekent de contrastverhoudingen van het kleurenpalet door (WCAG 2.1).

De cijfers onderaan site/assets/app.css komen hiervandaan. Draai dit opnieuw
zodra je een kleur wijzigt; een palet dat er warm en rustig uitziet kan zomaar
onder de 4.5:1 zakken en dat zie je met het blote oog niet betrouwbaar.

    python scripts/check_contrast.py

Exitcode 1 als een combinatie zakt, zodat het in een workflow kan meelopen.
"""

from __future__ import annotations

import sys

EIS_TEKST = 4.5      # normale tekst, WCAG AA
EIS_GROOT = 3.0      # tekst vanaf 24px of 19px vet

LICHT = {
    "papier": "#fcfaf6", "papier-diep": "#f3ede2", "inkt": "#1f1a14",
    "inkt-zacht": "#4a4038", "inkt-gedempt": "#6b5f52", "accent": "#a35418",
}
DONKER = {
    "papier": "#17130f", "papier-diep": "#211c15", "inkt": "#ece5d9",
    "inkt-zacht": "#cabfae", "inkt-gedempt": "#a2937f", "accent": "#e0a45c",
}


def luminantie(hexkleur: str) -> float:
    rauw = hexkleur.lstrip("#")
    kanalen = [int(rauw[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lineair = [k / 12.92 if k <= 0.03928 else ((k + 0.055) / 1.055) ** 2.4
               for k in kanalen]
    return 0.2126 * lineair[0] + 0.7152 * lineair[1] + 0.0722 * lineair[2]


def verhouding(voor: str, achter: str) -> float:
    a, b = luminantie(voor), luminantie(achter)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def main() -> int:
    combinaties = [
        ("inkt", "papier", EIS_TEKST),
        ("inkt-zacht", "papier", EIS_TEKST),
        ("inkt-gedempt", "papier", EIS_TEKST),
        ("accent", "papier", EIS_TEKST),
        ("inkt-gedempt", "papier-diep", EIS_TEKST),
        ("inkt", "papier-diep", EIS_TEKST),
    ]

    gezakt = 0
    for naam, palet in (("licht", LICHT), ("donker", DONKER)):
        print(f"\n{naam}")
        for voor, achter, eis in combinaties:
            r = verhouding(palet[voor], palet[achter])
            goed = r >= eis
            gezakt += 0 if goed else 1
            print(f"  {voor:14s} op {achter:12s} {r:5.2f}:1  "
                  f"{'ok' if goed else 'TE LAAG'} (eis {eis})")

    print()
    if gezakt:
        print(f"{gezakt} combinatie(s) halen de eis niet.", file=sys.stderr)
        return 1
    print("Alle combinaties halen WCAG AA.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
