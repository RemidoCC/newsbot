# newsbot

Dagelijkse nieuwsdigest over twee kanalen — **AI** (internationaal en Nederlands)
en **Bibliotheek & digitale inclusie** — verzameld door GitHub Actions, samengevat
in het Nederlands door Claude Code, en gelezen in een eigen PWA.

Geen kosten per run. Geen `ANTHROPIC_API_KEY`, nergens: al het LLM-werk loopt via
`claude -p` met een OAuth-token.

## Hoe het draait

```
collect.py     bronnen ophalen en normaliseren        (geen LLM)
dedupe.py      ontdubbelen, filteren, cappen op 120   (geen LLM)
claude -p      vertalen, samenvatten, taggen, wegen   (batches van 40)
validate.py    JSON-schema check op wat Claude teruggeeft
build_site.py  JSON -> statische site in site/
send_push.py   één melding, alleen bij een gevulde digest
```

Elke stap schrijft naar `data/`. Elke bron draait in een eigen try/except en logt
naar `data/errors.json`; één kapotte feed stopt de run nooit.

## Wat je zelf moet doen

Onderstaande stappen zijn eenmalig en kunnen niet geautomatiseerd worden.
Zonder stap 1 en 2 draait er niets.

### 1. Repo publiek maken en Pages aanzetten

GitHub Pages werkt op een private repo alleen met een betaald plan. Deze repo is
daarom publiek. Wat dat betekent: je code en je dagelijkse digests zijn leesbaar
voor iedereen. Je opgeslagen artikelen niet — die staan in Supabase achter
row-level security die aan je eigen gebruiker hangt.

- Settings → General → Danger Zone → *Change visibility* → **Public**
- Settings → Pages → Source → **GitHub Actions**

### 2. Claude Code OAuth-token

Lokaal, op je eigen machine:

```bash
claude setup-token
```

Kopieer de uitvoer naar Settings → Secrets and variables → Actions → New secret:

| Secret | Waarde |
| --- | --- |
| `CLAUDE_CODE_OAUTH_TOKEN` | uitvoer van `claude setup-token` |

Dit token hangt aan je Claude-abonnement. De run gebruikt hooguit drie
`claude -p`-aanroepen per dag (120 items in batches van 40).

**Zet hier nooit een `ANTHROPIC_API_KEY` neer.** De workflow verwacht 'm niet en
gebruikt 'm niet; hij zou alleen kosten opleveren.

### 3. Bronnen verifiëren

De feed-URL's in `sources/*.yaml` zijn kandidaten totdat een echte HTTP-request
ze bevestigt. Ze staan daarom allemaal op `verified: false`. Draai eenmalig:

Actions → **Bronnen verifiëren** → *Run workflow*

Die test elke URL, probeert de `fallback_urls`, doet feed-autodiscovery op de
homepage als alles faalt, schrijft de winnende URL terug in de YAML en zet
`verified: true`. Het rapport verschijnt in de job summary en als artifact.

Draai 'm opnieuw wanneer een bron in `data/errors.json` blijft terugkomen.

### 4. Reddit

Reddit heeft de onauthenticated `.json`-endpoints in mei 2026 dichtgezet. Ze geven
nu 403, zeker vanaf datacenter-IP's zoals Actions-runners. Een eigen User-Agent
helpt daar niet tegen. De officiële API is nog wel gratis voor persoonlijk gebruik
(ongeveer 100 requests per minuut), ruim genoeg voor vijf subreddits per dag.

1. Ga naar <https://www.reddit.com/prefs/apps> → *create another app*
2. Type: **script**. Redirect URI: `http://localhost:8080` (wordt niet gebruikt).
3. Zet de twee waarden als repo-secrets:

| Secret | Waar je 'm vindt |
| --- | --- |
| `REDDIT_CLIENT_ID` | de tekenreeks onder de app-naam |
| `REDDIT_CLIENT_SECRET` | het veld *secret* |

Ontbreken ze, dan slaat `collect.py` de subreddits over en logt dat. De rest van
de run gaat gewoon door.

### 5. Nieuwsbrieven zonder RSS (TLDR AI, The Rundown AI)

Deze twee hebben geen publieke feed. Route loopt via
[Kill-the-Newsletter](https://kill-the-newsletter.com):

1. Maak daar een inbox aan. Je krijgt een mailadres plus een Atom-feed-URL.
2. Meld je met dat mailadres aan voor de nieuwsbrief.
3. Zet de feed-URL in `sources/ai_int.yaml` bij de betreffende bron en
   zet `enabled: true`.

Herhaal per nieuwsbrief. Ze staan nu uit met een lege `url`.

### 6. Supabase (fase 6)

Nodig voor het bewaren van artikelen in eigen mappen.

1. Maak een gratis project op <https://supabase.com>.
2. Draai `supabase/schema.sql` in de SQL-editor.
3. Zet de project-URL en de anon key in `site/config.js`.

De anon key hoort publiek te zijn — dat is waar hij voor gemaakt is. Wat je data
beschermt is row-level security, niet geheimhouding van die key.

**Let op:** projecten op het gratis plan pauzeren na zeven dagen zonder verkeer.
De dagelijkse workflow doet daarom een pingetje naar Supabase, zodat dat nooit
gebeurt — ook niet als je twee weken weg bent.

### 7. Pushmeldingen (fase 7)

Genereer VAPID-sleutels:

```bash
python -c "from py_vapid import Vapid01; v=Vapid01(); v.generate_keys(); print(v.private_pem().decode()); print(v.public_key_urlsafe_base64())"
```

| Waar | Wat |
| --- | --- |
| repo-secret `VAPID_PRIVATE_KEY` | de private key |
| repo-secret `VAPID_CLAIM_EMAIL` | `mailto:jouw@adres.nl` |
| `site/config.js` | de public key |

De app vraagt pas toestemming ná een klik op "Meldingen aan", nooit bij het eerste
bezoek.

**iOS staat push alleen toe nadat de PWA op het beginscherm staat.** Open de site
in Safari, deel-knop → *Zet op beginscherm*, open 'm daarvandaan, en zet dan pas
meldingen aan. In Safari zelf werkt het niet en krijg je geen foutmelding.

## Bronnen beheren

Alles staat in `sources/*.yaml` en is los aan en uit te zetten met `enabled`.

```yaml
- name: Tweakers
  enabled: true
  type: rss            # rss | newsletter | reddit | hn | x
  priority: 2          # 1 = hoogste; bepaalt wie de cap van 120 items haalt
  url: https://…
  fallback_urls: […]   # geprobeerd door --verify als url faalt
  homepage: https://…  # voor feed-autodiscovery als ook die falen
  max_items: 40
  include_keywords: […]  # optioneel filter, matcht op hele woorden
```

`include_keywords` is er voor brede techfeeds zoals Tweakers en NOS, die geen
losse AI-feed hebben. Het filter matcht op woordgrens, dus `ai` raakt wel
"AI-verordening" maar niet "detail" of "email".

## X / Twitter

`sources/x.yaml` staat uit en dat is een bewuste keuze, geen omissie.

Er is geen gratis officiële leesroute meer voor X. `collect_x.py` leunt op een
RSS-bridge van derden — een Nitter-instance of de gratis tier van rss.app. De
publieke Nitter-instances zijn inmiddels vrijwel allemaal verdwenen en rss.app
laat op het gratis plan maar een handvol feeds toe.

**Dit is de fragielste schakel in het project.** Reken er niet op. De module logt
elke fout en geeft een lege lijst terug; de run merkt er verder niets van. Zet
`enabled: true` pas als je een bridge hebt die het echt doet.

## Vormgeving

De vormtaal is afgeleid van [ai.nl](https://www.ai.nl): strak, veel witruimte,
korte stellige koppen. `site/tokens.css` bevat de kleuren, spacing en type-schaal
met bovenaan de datum en de bron waar ze vandaan komen.

Overgenomen is de *vorm*, niet het merk: geen logo, geen woordmerk, geen
afbeeldingen van hun site. Vereist hun font een betaalde licentie, dan staat hier
welke vrije variant ervoor in de plaats is gekomen.

## Lokaal draaien

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt

.venv/bin/python scripts/collect.py --verify          # bronnen testen
.venv/bin/python scripts/collect.py --only Tweakers   # één bron ophalen
.venv/bin/python scripts/collect.py                   # alles ophalen
```

`--verify --apply` schrijft werkende URL's terug in de YAML.

## Afwijkingen van de oorspronkelijke opzet

- **`ruamel.yaml` en `jsonschema`** zitten in `requirements.txt` naast de zes
  gevraagde pakketten. De eerste omdat `--verify --apply` de YAML moet
  terugschrijven zonder de commentaarregels op te eten; de tweede voor
  `validate.py`.
- **De batch gaat via stdin naar `claude -p`**, niet via `"$(cat batch.json)"`.
  Veertig items van 1500 tekens is ruim 60 KB aan argumenten, en dat loopt stuk op
  shell-quoting en argv-limieten.
- **Reddit loopt via OAuth**, niet via de publieke `.json`-endpoints. Zie stap 4.
- **Het leeftijdsvenster verschilt per kanaal:** 48 uur voor `ai`, 7 dagen voor
  `bieb`. IFLA, EBLIDA en Digisterker publiceren een paar keer per maand; met 48
  uur zou de bibliotheek-tab bijna altijd leeg zijn.
- **De cron staat op 05:00 UTC.** Dat is 07:00 in de zomer en 06:00 in de winter.
