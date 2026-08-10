#!/usr/bin/env python3
"""Genereert een voorbeelddigest, puur om het ontwerp te kunnen beoordelen.

Alles hierin is verzonnen. De bronnen bestaan niet en de URL's wijzen naar
example.com, het domein dat daarvoor gereserveerd is. Dat is met opzet: een
verzonnen kop onder de naam van een echte krant is een vervalst bericht, ook
als het maar een ontwerpvoorbeeld is. De gegenereerde pagina zet er bovendien
een banner boven.

Wat wel echt moet zijn, is de vórm: koppen van uiteenlopende lengte,
samenvattingen van twee tot drie zinnen, en een realistische verdeling over
kanalen, regio's en onderwerpen. Daar beoordeel je typografie op.

Gebruik:
    python scripts/sample_data.py && python scripts/build_site.py --sample
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collect import DATA_DIR

NOW = datetime.now(timezone.utc)

RUWE_ITEMS = [
    # (uren geleden, bron, kanaal, regio, belang, topics, kop, samenvatting, waarom)
    (2, "Techjournaal", "ai", "int", 5, ["modellen", "bedrijven"],
     "Nieuw taalmodel werkt met aanzienlijk langer geheugen",
     "Een groot onderzoekslab heeft een model aangekondigd dat veel langere teksten "
     "in één keer kan verwerken dan zijn voorganger. Volgens de begeleidende "
     "documentatie gaat het om ongeveer een verviervoudiging. Wat dat in de praktijk "
     "betekent voor kosten en snelheid is nog niet onafhankelijk getoetst.",
     "Langere context maakt hele dossiers doorzoekbaar."),

    (4, "Beleidsbrief Digitaal", "ai", "nl", 5, ["beleid-en-regelgeving", "ethiek-en-risico"],
     "Toezichthouder publiceert leidraad voor AI in publieke dienstverlening",
     "De leidraad beschrijft wanneer een overheidsorganisatie een risicobeoordeling "
     "moet uitvoeren voordat zij een AI-systeem inzet richting burgers. Er staat een "
     "overgangstermijn van een jaar in. Voor kleine organisaties komt er een verkorte "
     "variant.",
     "Bibliotheken vallen onder publieke dienstverlening."),

    (5, "Techjournaal", "ai", "int", 3, ["open-source", "modellen"],
     "Open gewichten vrijgegeven voor een middelgroot model",
     "Een consortium van universiteiten heeft de gewichten van een middelgroot "
     "taalmodel onder een permissieve licentie gepubliceerd. Het model draait naar "
     "verluidt op consumentenhardware. De trainingsdata zijn deels beschreven maar "
     "niet volledig openbaar.",
     None),

    (7, "De Ochtendkrant", "ai", "nl", 3, ["arbeidsmarkt", "onderzoek"],
     "Onderzoek: werknemers gebruiken AI vaker dan hun werkgever denkt",
     "Uit een enquête onder ruim tweeduizend werknemers blijkt een flink verschil "
     "tussen gerapporteerd en werkelijk gebruik van AI-hulpmiddelen. De onderzoekers "
     "wijzen op onduidelijke interne richtlijnen als voornaamste oorzaak.",
     None),

    (9, "Techjournaal", "ai", "int", 2, ["tools"],
     "Editor krijgt ingebouwde ondersteuning voor lokale modellen",
     "Een veelgebruikte teksteditor ondersteunt voortaan modellen die op de eigen "
     "machine draaien, zonder dat er data naar buiten gaat. De functie zit nog in een "
     "testkanaal.",
     None),

    (11, "Instituut voor Informatierecht", "ai", "nl", 4, ["beleid-en-regelgeving"],
     "Vragen over auteursrecht bij trainingsdata blijven onbeantwoord",
     "Een juridische analyse stelt dat de huidige uitzonderingen voor tekst- en "
     "datamining onvoldoende houvast bieden voor generatieve modellen. De auteurs "
     "pleiten voor verduidelijking in plaats van nieuwe wetgeving.",
     "Raakt hoe bibliotheken hun collecties beschikbaar stellen."),

    (14, "Rekenkracht Vandaag", "ai", "int", 2, ["bedrijven"],
     "Chipfabrikant meldt langere levertijden voor rekenclusters",
     "De wachttijd voor nieuwe rekenclusters is opgelopen naar meerdere kwartalen. "
     "Kleinere afnemers voelen dat het eerst.",
     None),

    (19, "De Ochtendkrant", "ai", "nl", 3, ["onderwijs", "ethiek-en-risico"],
     "Scholen zoeken een lijn in het beoordelen van werk met AI",
     "Een rondgang langs middelbare scholen laat sterk uiteenlopende afspraken zien "
     "over wat leerlingen wel en niet met AI mogen doen. Sommige scholen kiezen voor "
     "toetsen op papier, andere voor gesprekken over het proces.",
     None),

    (23, "Techjournaal", "ai", "int", 2, ["onderzoek"],
     "Nieuwe evaluatiemethode meet hoe vaak een model zijn eigen fouten opmerkt",
     "De methode legt modellen opgaven voor waarvan de opsteller weet dat ze niet "
     "kloppen. Bestaande modellen scoren daar volgens de eerste resultaten matig op.",
     None),

    (30, "Rekenkracht Vandaag", "ai", "int", 1, ["tools", "open-source"],
     "Klein hulpprogramma maakt modelvergelijking reproduceerbaar",
     "Het programma legt vast welke versie, instellingen en willekeurige startwaarde "
     "bij een resultaat horen. Het is beschikbaar onder een open licentie.",
     None),

    # --- Bibliotheek en digitale inclusie ---------------------------------
    (6, "Bibliotheekkrant", "bieb", "nl", 5, ["digitale-inclusie", "cursus-of-workshop"],
     "Bibliotheken breiden spreekuren over digitale overheid uit",
     "Een groeiend aantal vestigingen houdt wekelijks een inloopspreekuur waar "
     "bezoekers hulp krijgen bij het regelen van zaken met de overheid. De vraag komt "
     "vooral van mensen die geen hulp in hun directe omgeving hebben.",
     "Direct toepasbaar in je eigen vestiging."),

    (28, "Bibliotheekkrant", "bieb", "nl", 3, ["subsidie-of-financiering"],
     "Nieuwe regeling voor basisvaardigheden opent in het najaar",
     "De regeling richt zich op samenwerkingsverbanden van bibliotheken, gemeenten en "
     "welzijnsorganisaties. Aanvragen kan vanaf september; het plafond is nog niet "
     "bekendgemaakt.",
     None),

    (52, "Vakblad Mediawijs", "bieb", "nl", 4, ["digitale-geletterdheid", "onderwijs"],
     "Lesmateriaal over herkennen van gegenereerde beelden herzien",
     "De herziene versie besteedt meer aandacht aan geluid en video, omdat "
     "beeldherkenning alleen niet meer volstaat. Het materiaal is gratis te gebruiken "
     "en gericht op groep zeven en acht.",
     "Bruikbaar voor workshops mediawijsheid."),

    (74, "European Library Review", "bieb", "int", 2, ["bibliotheek", "beleid-en-regelgeving"],
     "Europese koepel vraagt aandacht voor bibliotheken in digitale wetgeving",
     "In een position paper stelt de koepelorganisatie dat bibliotheken bij de "
     "uitvoering van digitale wetgeving stelselmatig over het hoofd worden gezien. "
     "Er wordt om een structurele consultatiepositie gevraagd.",
     None),

    (96, "European Library Review", "bieb", "int", 2, ["evenement", "bibliotheek"],
     "Jaarlijkse conferentie over publieke bibliotheken kondigt programma aan",
     "Het programma bevat dit jaar een apart spoor over kunstmatige intelligentie in "
     "de dienstverlening. Inschrijving opent volgende maand.",
     None),

    (120, "Bibliotheekkrant", "bieb", "nl", 3, ["cursus-of-workshop", "digitale-inclusie"],
     "Vrijwilligers krijgen kortere training voor digitale ondersteuning",
     "De training is teruggebracht van vier naar twee dagdelen, met meer nadruk op "
     "doorverwijzen. Aanleiding is dat vrijwilligers afhaakten bij het oude programma.",
     None),
]


def bouw() -> dict:
    items = []
    for index, (uren, bron, kanaal, regio, belang, topics, kop, samenvatting, waarom) in enumerate(RUWE_ITEMS):
        url = f"https://example.com/voorbeeld/{index + 1}"
        items.append({
            "id": hashlib.sha256(url.encode()).hexdigest(),
            "title": kop,
            "summary": samenvatting,
            "url": url,
            "source_name": bron,
            "source_type": "rss",
            "published": (NOW - timedelta(hours=uren)).isoformat(timespec="seconds"),
            "channel": kanaal,
            "region": regio,
            "topics": topics,
            "importance": belang,
            "why_relevant": waarom or "",
            "also_covered_by": (
                ["https://example.org/elders/1", "https://example.net/elders/2"]
                if index == 0 else []
            ),
        })

    items.sort(key=lambda i: (-i["importance"], i["published"]), reverse=False)
    return {
        "date": NOW.strftime("%Y-%m-%d"),
        "generated_at": NOW.isoformat(timespec="seconds"),
        "is_sample": True,
        "stats": {
            "geldig": len(items),
            "ai": sum(1 for i in items if i["channel"] == "ai"),
            "bieb": sum(1 for i in items if i["channel"] == "bieb"),
        },
        "sources": sorted({i["source_name"] for i in items}),
        "items": items,
    }


def main() -> int:
    out = DATA_DIR / "sample" / "preview.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = bouw()
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(payload['items'])} voorbeelditems -> {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
