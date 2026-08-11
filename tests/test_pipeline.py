"""Tests voor de keten van collect tot build_site.

Dit zijn de controles die tijdens het bouwen los in een shell zijn gedraaid en
daarna verdwenen. Ze staan hier zodat een volgende wijziging niet stilletjes
iets sloopt.

    .venv/bin/python -m pytest tests/ -q

Geen netwerk. Alles wat een HTTP-verzoek zou doen wordt hier niet aangeraakt;
de bronverificatie is per definitie een integratietest en draait in Actions.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_site  # noqa: E402
import check_contrast  # noqa: E402
import collect  # noqa: E402
import dedupe  # noqa: E402
import validate  # noqa: E402

NU = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# collect: URL's, filters, taal
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("links, rechts", [
    # Tracking-parameters mogen het id niet beïnvloeden.
    ("https://nos.nl/artikel/1?utm_source=x", "https://nos.nl/artikel/1"),
    ("https://nos.nl/artikel/1?ref=nieuwsbrief", "https://nos.nl/artikel/1"),
    ("https://nos.nl/artikel/1#kop", "https://nos.nl/artikel/1"),
    # www en trailing slash evenmin.
    ("https://www.nos.nl/artikel/1/", "https://nos.nl/artikel/1"),
    # http en https zijn dezelfde pagina.
    ("http://nos.nl/artikel/1", "https://nos.nl/artikel/1"),
])
def test_zelfde_pagina_geeft_zelfde_id(links, rechts):
    assert collect.item_id(links) == collect.item_id(rechts)


def test_echt_andere_url_geeft_ander_id():
    assert collect.item_id("https://nos.nl/a/1") != collect.item_id("https://nos.nl/a/2")


def test_inhoudelijke_queryparameter_blijft_staan():
    # ?page=2 is een andere pagina; die mag niet wegvallen.
    assert collect.normalize_url("https://x.nl/a?page=2").endswith("?page=2")


@pytest.mark.parametrize("tekst, raak", [
    ("Nieuwe AI-verordening aangenomen", True),     # koppelteken telt als grens
    ("AI is overal", True),
    ("Meer detail over het onderwerp", False),      # 'ai' in 'detail'
    ("Stuur een email naar de redactie", False),    # 'ai' in 'email'
    ("De zaak Said tegen de staat", False),         # 'ai' in 'Said'
])
def test_trefwoordfilter_matcht_op_woordgrens(tekst, raak):
    bron = {"include_keywords": ["ai"]}
    assert collect.matches_keywords(bron, tekst) is raak


def test_bron_zonder_filter_laat_alles_door():
    assert collect.matches_keywords({}, "wat dan ook") is True


def test_item_zonder_url_of_titel_wordt_geweigerd():
    basis = dict(raw_text="", published=None, source={"name": "X", "priority": 1},
                 config={"channel": "ai", "region": "int", "language": "nl"},
                 source_type="rss")
    assert collect.build_item(url="", title="Titel", **basis) is None
    assert collect.build_item(url="https://x.nl/a", title="", **basis) is None
    # javascript: en andere niet-http schema's horen er ook uit.
    assert collect.build_item(url="javascript:alert(1)", title="Titel", **basis) is None
    assert collect.build_item(url="https://x.nl/a", title="Titel", **basis) is not None


def test_nederlandse_tekst_wordt_herkend():
    assert collect.guess_language("De cursus is voor het publiek van de bibliotheek", "en") == "nl"
    assert collect.guess_language("A short English sentence about models", "en") == "en"


# ---------------------------------------------------------------------------
# dedupe: zeven
# ---------------------------------------------------------------------------

def _item(n, *, uren=1, kanaal="ai", prioriteit=3, titel=None, url=None):
    url = url or f"https://voorbeeld.nl/{n}"
    return {
        "id": hashlib.sha256(url.encode()).hexdigest(),
        "title": titel or f"Kop nummer {n} over modellen en beleid",
        "url": url, "source_name": "Bron", "source_type": "rss",
        "channel_hint": kanaal, "region_hint": "nl",
        "published": None if uren is None else (NU - timedelta(hours=uren)).isoformat(),
        "raw_text": "", "language": "nl", "priority": prioriteit,
    }


def _draai(tmp_path, monkeypatch, items, seen=None):
    monkeypatch.setattr(dedupe, "DATA_DIR", tmp_path)
    monkeypatch.setattr(dedupe, "SEEN_PATH", tmp_path / "seen.json")
    (tmp_path / "raw").mkdir(parents=True, exist_ok=True)
    (tmp_path / "raw" / "2099-01-01.json").write_text(
        json.dumps({"items": items}), encoding="utf-8")
    (tmp_path / "seen.json").write_text(json.dumps(seen or {}), encoding="utf-8")
    assert dedupe.run("2099-01-01", dry_run=False) == 0
    return json.loads((tmp_path / "clean" / "2099-01-01.json").read_text(encoding="utf-8"))


def test_ai_venster_is_48_uur(tmp_path, monkeypatch):
    uit = _draai(tmp_path, monkeypatch, [_item(1, uren=47), _item(2, uren=49)])
    assert [i["url"] for i in uit["items"]] == ["https://voorbeeld.nl/1"]


def test_bieb_venster_is_zeven_dagen(tmp_path, monkeypatch):
    # Precies het verschil waar de bibliotheek-tab op leeg zou lopen.
    uit = _draai(tmp_path, monkeypatch,
                 [_item(1, uren=120, kanaal="bieb"), _item(2, uren=200, kanaal="bieb")])
    assert [i["url"] for i in uit["items"]] == ["https://voorbeeld.nl/1"]


def test_item_zonder_datum_blijft(tmp_path, monkeypatch):
    # De KB-feed levert items zonder publicatiedatum. Die mogen niet wegvallen.
    uit = _draai(tmp_path, monkeypatch, [_item(1, uren=None)])
    assert len(uit["items"]) == 1


def test_al_gezien_valt_af(tmp_path, monkeypatch):
    item = _item(1)
    uit = _draai(tmp_path, monkeypatch, [item, _item(2)],
                 seen={item["id"]: NU.isoformat()})
    assert [i["url"] for i in uit["items"]] == ["https://voorbeeld.nl/2"]


def test_bijna_gelijke_kop_wordt_samengevoegd(tmp_path, monkeypatch):
    uit = _draai(tmp_path, monkeypatch, [
        _item(1, prioriteit=4, titel="OpenAI kondigt GPT-6 aan tijdens DevDay"),
        _item(2, prioriteit=1, titel="OpenAI kondigt GPT-6 aan"),
    ])
    assert len(uit["items"]) == 1
    winnaar = uit["items"][0]
    assert winnaar["priority"] == 1, "de bron met de hoogste prioriteit hoort te winnen"
    assert len(winnaar["also_covered_by"]) == 1


def test_korte_koppen_worden_niet_samengevoegd(tmp_path, monkeypatch):
    # Onder de drie betekenisdragende woorden is de overlap-score te grillig.
    uit = _draai(tmp_path, monkeypatch, [
        _item(1, titel="AI wet"), _item(2, titel="AI wet", url="https://ander.nl/x"),
    ])
    assert len(uit["items"]) == 2


def test_cap_en_batchgrootte(tmp_path, monkeypatch):
    uit = _draai(tmp_path, monkeypatch, [_item(n) for n in range(130)])
    assert len(uit["items"]) == dedupe.MAX_ITEMS
    batches = sorted((tmp_path / "batches").glob("batch_*.json"))
    assert len(batches) == 3
    assert len(json.loads(batches[0].read_text(encoding="utf-8"))) == dedupe.BATCH_SIZE


def test_seen_wordt_bijgewerkt(tmp_path, monkeypatch):
    _draai(tmp_path, monkeypatch, [_item(1), _item(2)])
    assert len(json.loads((tmp_path / "seen.json").read_text(encoding="utf-8"))) == 2


# ---------------------------------------------------------------------------
# validate: rommelige modeluitvoer overleven
# ---------------------------------------------------------------------------

def test_json_uit_markdown_fences():
    assert validate.extract_json_array('```json\n[{"id": "x"}]\n```') == [{"id": "x"}]


def test_json_met_inleidende_zin():
    assert validate.extract_json_array(
        'Hier is de JSON:\n\n[{"id": "x"}]') == [{"id": "x"}]


def test_json_als_object_met_items():
    assert validate.extract_json_array('{"items": [{"id": "x"}]}') == [{"id": "x"}]


def test_onzin_geeft_none():
    assert validate.extract_json_array("sorry, dat lukt niet") is None
    assert validate.extract_json_array("") is None


def _geldig(**kw):
    d = {"id": "a" * 64, "title_nl": "Een titel",
         "summary_nl": "Een samenvatting van ruim twintig tekens in het Nederlands.",
         "channel": "ai", "region": "int", "topics": ["modellen"],
         "importance": 3, "why_relevant": "Relevant voor bibliotheken."}
    d.update(kw)
    return d


def _fouten(entry):
    return list(validate.validator.iter_errors(entry))


def test_volledig_item_komt_door_het_schema():
    assert _fouten(_geldig()) == []


@pytest.mark.parametrize("aanpassing", [
    {"topics": ["verzonnen-tag"]},          # niet in de vaste lijst
    {"importance": 9},                      # buiten 1 t/m 5
    {"importance": 0},
    {"channel": "sport"},                   # geen geldig kanaal
    {"region": "be"},
    {"topics": []},                         # minstens één tag
    {"topics": ["modellen", "tools", "onderzoek", "beleid-en-regelgeving"]},  # hooguit drie
])
def test_schema_weigert_ongeldige_waarden(aanpassing):
    assert _fouten(_geldig(**aanpassing)), f"{aanpassing} had geweigerd moeten worden"


def test_item_zonder_samenvatting_wordt_geweigerd():
    kaal = _geldig()
    del kaal["summary_nl"]
    assert _fouten(kaal)


def test_gedropt_item_hoeft_alleen_id_en_drop():
    assert _fouten({"id": "a" * 64, "drop": True, "reason": "vacature"}) == []


def test_merge_neemt_de_feiten_uit_het_origineel():
    # Het model levert taal en oordeel; url, bron en datum komen uit de collector.
    origineel = {"id": "a" * 64, "url": "https://echt.nl/artikel",
                 "source_name": "Echte Bron", "published": "2026-08-01T10:00:00+00:00",
                 "source_type": "rss"}
    verrijkt = _geldig(title_nl="Nederlandse titel")
    samen = validate.merge(origineel, verrijkt)
    assert samen["url"] == "https://echt.nl/artikel"
    assert samen["source_name"] == "Echte Bron"
    assert samen["published"] == "2026-08-01T10:00:00+00:00"
    assert samen["title"] == "Nederlandse titel"


# ---------------------------------------------------------------------------
# build_site
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("uren, verwacht", [
    (1, "1 uur geleden"),
    (5, "5 uur geleden"),
    (24, "gisteren"),
    (72, "3 dagen geleden"),
])
def test_relatieve_tijd(uren, verwacht):
    moment = (NU - timedelta(hours=uren)).isoformat()
    assert build_site.relative_time(moment) == verwacht


def test_relatieve_tijd_zonder_datum_is_leeg():
    assert build_site.relative_time(None) == ""
    assert build_site.relative_time("geen datum") == ""


def test_nederlandse_datum():
    assert build_site.dutch_date("2026-08-11") == "11 augustus 2026"


def test_domein_uit_url():
    assert build_site.domain("https://www.nos.nl/artikel/1") == "nos.nl"


def test_belangrijke_items_komen_apart():
    items = [
        {"channel": "ai", "importance": 5, "topics": ["modellen"], "source_name": "A"},
        {"channel": "ai", "importance": 2, "topics": ["tools"], "source_name": "B"},
        {"channel": "bieb", "importance": 1, "topics": ["bibliotheek"], "source_name": "C"},
    ]
    groepen = build_site.group_items(items)
    assert len(groepen["ai"]["important"]) == 1
    assert groepen["ai"]["count"] == 2
    assert groepen["bieb"]["count"] == 1
    # De sectiesleutel heet "rijen", niet "items": in Jinja pakt `sectie.items`
    # anders de dict-methode. Deze test bewaakt die val.
    assert "rijen" in groepen["ai"]["sections"][0]


# ---------------------------------------------------------------------------
# Vormgeving
# ---------------------------------------------------------------------------

def test_kleurenpalet_haalt_wcag_aa():
    assert check_contrast.main() == 0


# ---------------------------------------------------------------------------
# Herhaling over dagen heen, en opruimen
# ---------------------------------------------------------------------------

def test_zelfde_verhaal_andere_url_valt_af(tmp_path, monkeypatch):
    # Gisteren bij bron A, vandaag bij bron B. Andere URL, dus seen.json op id
    # vangt het niet — de kop moet het doen.
    gisteren = (NU - timedelta(days=1)).isoformat()
    seen = {"oud-id": {"ts": gisteren,
                       "kop": sorted(dedupe.title_tokens(
                           "Toezichthouder publiceert leidraad voor AI bij de overheid"))}}
    uit = _draai(tmp_path, monkeypatch, [
        _item(1, titel="Toezichthouder publiceert leidraad voor AI bij de overheid"),
        _item(2, titel="Heel ander onderwerp over bibliotheken en cursussen"),
    ], seen=seen)
    assert [i["title"] for i in uit["items"]] == [
        "Heel ander onderwerp over bibliotheken en cursussen"]
    assert uit["stats"]["herhaling"] == 1


def test_herhaling_buiten_het_venster_telt_niet(tmp_path, monkeypatch):
    lang_geleden = (NU - timedelta(days=dedupe.HERHALING_VENSTER_DAGEN + 3)).isoformat()
    seen = {"oud-id": {"ts": lang_geleden,
                       "kop": sorted(dedupe.title_tokens("Kop nummer 1 over modellen en beleid"))}}
    uit = _draai(tmp_path, monkeypatch, [_item(1)], seen=seen)
    assert len(uit["items"]) == 1, "na het venster is het weer nieuws"


def test_oud_seen_formaat_blijft_leesbaar(tmp_path, monkeypatch):
    # Vroeger was de waarde een kale tijdstempel in plaats van een object.
    item = _item(1)
    uit = _draai(tmp_path, monkeypatch, [item, _item(2)],
                 seen={item["id"]: NU.isoformat()})
    assert len(uit["items"]) == 1


def test_seen_bewaart_de_kop(tmp_path, monkeypatch):
    _draai(tmp_path, monkeypatch, [_item(1)])
    seen = json.loads((tmp_path / "seen.json").read_text(encoding="utf-8"))
    regel = next(iter(seen.values()))
    assert isinstance(regel, dict) and regel["kop"], "kop hoort mee te gaan"


def test_oude_databestanden_worden_opgeruimd(tmp_path, monkeypatch):
    monkeypatch.setattr(dedupe, "DATA_DIR", tmp_path)
    monkeypatch.setattr(dedupe, "BEWAAR", {"raw": 2, "clean": 2, "digest": 3})
    for map_naam, aantal in (("raw", 5), ("clean", 5), ("digest", 6)):
        (tmp_path / map_naam).mkdir(parents=True, exist_ok=True)
        for n in range(aantal):
            (tmp_path / map_naam / f"2026-01-{n + 1:02d}.json").write_text("{}")

    assert dedupe.ruim_op() == (5 - 2) + (5 - 2) + (6 - 3)
    assert len(list((tmp_path / "raw").glob("*.json"))) == 2
    assert len(list((tmp_path / "digest").glob("*.json"))) == 3
    # De nieuwste moeten blijven staan, niet de oudste.
    assert (tmp_path / "raw" / "2026-01-05.json").exists()
    assert not (tmp_path / "raw" / "2026-01-01.json").exists()


# ---------------------------------------------------------------------------
# Importance normaliseren
# ---------------------------------------------------------------------------

def _vijf(n, prioriteit=3):
    return {"id": f"id{n}", "importance": 5, "title": f"Titel {n}",
            "published": (NU - timedelta(hours=n)).isoformat()}, \
           {"id": f"id{n}", "priority": prioriteit}


def test_hoogstens_twee_vijven_per_run():
    items, originals = [], {}
    for n in range(6):
        item, origineel = _vijf(n, prioriteit=1 if n < 2 else 4)
        items.append(item)
        originals[origineel["id"]] = origineel

    validate.normaliseer_importance(items, originals)
    vijven = [i for i in items if i["importance"] == 5]
    assert len(vijven) == 2
    # De bronnen met prioriteit 1 horen de vijf te houden.
    assert {i["id"] for i in vijven} == {"id0", "id1"}
    assert all(i["importance"] == 4 for i in items if i["id"] not in {"id0", "id1"})


def test_twee_of_minder_vijven_blijft_ongemoeid():
    items = [{"id": "a", "importance": 5, "published": NU.isoformat()},
             {"id": "b", "importance": 3, "published": NU.isoformat()}]
    validate.normaliseer_importance(items, {})
    assert [i["importance"] for i in items] == [5, 3]
