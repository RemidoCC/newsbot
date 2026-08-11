# Bronverificatie

Gedraaid op 2026-08-11 19:31 UTC.

**21 levend** · **3 bevroren** · **5 kapot** · 11 uitgezet · 40 totaal

Bevroren = de feed parseert prima, maar het nieuwste item is ouder dan 90 dagen. Die telt niet als werkende bron.

| Bron | Bestand | Status | Via | Details |
| --- | --- | --- | --- | --- |
| r/LocalLLaMA | ai_int.yaml | KAPOT | - | RuntimeError: REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET ontbreken. Reddit's onauthenticated .json is sinds mei 2026 dicht; |
| r/MachineLearning | ai_int.yaml | KAPOT | - | RuntimeError: REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET ontbreken. Reddit's onauthenticated .json is sinds mei 2026 dicht; |
| r/artificial | ai_int.yaml | KAPOT | - | RuntimeError: REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET ontbreken. Reddit's onauthenticated .json is sinds mei 2026 dicht; |
| r/libraries | bieb_int.yaml | KAPOT | - | RuntimeError: REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET ontbreken. Reddit's onauthenticated .json is sinds mei 2026 dicht; |
| r/singularity | ai_int.yaml | KAPOT | - | RuntimeError: REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET ontbreken. Reddit's onauthenticated .json is sinds mei 2026 dicht; |
| AG Connect | ai_nl.yaml | uit | - | staat uit |
| Anthropic | ai_int.yaml | uit | - | staat uit |
| BNR | ai_nl.yaml | uit | - | staat uit |
| EBLIDA | bieb_int.yaml | uit | - | staat uit |
| Library Journal | bieb_int.yaml | uit | - | staat uit |
| Public Libraries 2030 | bieb_int.yaml | uit | - | staat uit |
| Rijksoverheid | ai_nl.yaml | uit | - | staat uit |
| Stichting Lezen en Schrijven | bieb_nl.yaml | uit | - | staat uit |
| TLDR AI | ai_int.yaml | uit | - | staat uit |
| The Batch (DeepLearning.AI) | ai_int.yaml | uit | - | staat uit |
| The Rundown AI | ai_int.yaml | uit | - | staat uit |
| Alliantie Digitaal Samenleven | bieb_nl.yaml | BEVROREN | url | 1 items, nieuwste 1790 dagen oud — BEVROREN |
| Koninklijke Bibliotheek | bieb_nl.yaml | GEEN DATUMS | url | 10 items, maar geen enkele publicatiedatum |
| VOB (debibliotheken.nl) | bieb_nl.yaml | BEVROREN | url | 1 items, nieuwste 1860 dagen oud — BEVROREN |
| American Libraries | bieb_int.yaml | ok | url | 10 items, nieuwste 28 dagen oud |
| Ars Technica AI | ai_int.yaml | ok | fallback | 20 items, nieuwste 0 dagen oud |
| Bibliotheekblad | bieb_nl.yaml | ok | url | 10 items, nieuwste 8 dagen oud |
| Bits of Freedom | ai_nl.yaml | ok | url | 30 items, nieuwste 8 dagen oud |
| Computable | ai_nl.yaml | ok | fallback | 10 items, nieuwste 0 dagen oud |
| Digisterker | bieb_nl.yaml | ok | url | 10 items, nieuwste 12 dagen oud |
| Emerce | ai_nl.yaml | ok | url | 10 items, nieuwste 0 dagen oud |
| Google DeepMind | ai_int.yaml | ok | url | 100 items, nieuwste 5 dagen oud |
| Hacker News | ai_int.yaml | ok | algolia | 5 hits boven 50 punten |
| IFLA | bieb_int.yaml | ok | fallback | 10 items, nieuwste 0 dagen oud |
| Import AI | ai_int.yaml | ok | fallback | 10 items, nieuwste 1 dagen oud |
| MIT Technology Review — AI | ai_int.yaml | ok | fallback | 10 items, nieuwste 0 dagen oud |
| NOS Tech | ai_nl.yaml | ok | url | 20 items, nieuwste 6 dagen oud |
| Nederlandse AI Coalitie | ai_nl.yaml | ok | autodiscovery | 10 items, nieuwste 19 dagen oud |
| Netwerk Mediawijsheid | bieb_nl.yaml | ok | url | 10 items, nieuwste 28 dagen oud |
| OpenAI | ai_int.yaml | ok | url | 1123 items, nieuwste 0 dagen oud |
| Princh Library Blog | bieb_int.yaml | ok | fallback | 3 items, nieuwste 5 dagen oud |
| SPN (Stichting Samenwerkende POI's Nederland) | bieb_nl.yaml | ok | url | 9 items, nieuwste 7 dagen oud |
| Simon Willison | ai_int.yaml | ok | url | 30 items, nieuwste 0 dagen oud |
| Tweakers | ai_nl.yaml | ok | url | 40 items, nieuwste 0 dagen oud |
| VentureBeat AI | ai_int.yaml | ok | fallback | 7 items, nieuwste 0 dagen oud |

## Bevroren feeds — nakijken of de bron verhuisd is

- **Koninklijke Bibliotheek** — 10 items, maar geen enkele publicatiedatum (`https://www.kb.nl/rss.xml`)
- **VOB (debibliotheken.nl)** — 1 items, nieuwste 1860 dagen oud — BEVROREN (`https://www.debibliotheken.nl/feed/`)
- **Alliantie Digitaal Samenleven** — 1 items, nieuwste 1790 dagen oud — BEVROREN (`https://digitaalsamenleven.nl/feed/`)

## URL's die zijn bijgesteld

- **Import AI**: `https://importai.substack.com/feed` -> `https://jack-clark.net/feed/` (via fallback)
- **Ars Technica AI**: `https://arstechnica.com/ai/feed/` -> `https://feeds.arstechnica.com/arstechnica/index` (via fallback)
- **MIT Technology Review — AI**: `https://www.technologyreview.com/topic/artificial-intelligence/feed/` -> `https://www.technologyreview.com/feed/` (via fallback)
- **VentureBeat AI**: `https://venturebeat.com/category/ai/feed/` -> `https://feeds.feedburner.com/venturebeat/SZYF` (via fallback)
- **Computable**: `https://www.computable.nl/rss.xml` -> `https://www.computable.nl/feed/` (via fallback)
- **Nederlandse AI Coalitie**: `https://nlaic.com/feed/` -> `https://aic4nl.nl/feed/` (via autodiscovery)
- **IFLA**: `https://www.ifla.org/feed/` -> `https://www.ifla.org/news/feed/` (via fallback)
- **Princh Library Blog**: `https://princh.com/blog/feed/` -> `https://princh.com/feed/` (via fallback)

## Kapotte bronnen

- **r/MachineLearning** — RuntimeError: REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET ontbreken. Reddit's onauthenticated .json is sinds mei 2026 dicht; zie README stap 4.
- **r/LocalLLaMA** — RuntimeError: REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET ontbreken. Reddit's onauthenticated .json is sinds mei 2026 dicht; zie README stap 4.
- **r/artificial** — RuntimeError: REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET ontbreken. Reddit's onauthenticated .json is sinds mei 2026 dicht; zie README stap 4.
- **r/singularity** — RuntimeError: REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET ontbreken. Reddit's onauthenticated .json is sinds mei 2026 dicht; zie README stap 4.
- **r/libraries** — RuntimeError: REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET ontbreken. Reddit's onauthenticated .json is sinds mei 2026 dicht; zie README stap 4.
