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

#### Bronnen die uitstaan

Acht bronnen staan op `enabled: false` omdat ze bewezen kapot zijn. De reden
staat boven elke bron in de YAML. Kort: The Batch, BNR en Library Journal geven
403 (Cloudflare weigert de runner), AG Connect en Stichting Lezen en Schrijven
geven 404 op elk pad, `feeds.rijksoverheid.nl` resolvet niet, EBLIDA loopt in
een timeout en Public Libraries 2030 serveert HTML in plaats van XML.

Weer aanzetten kan via `/beheer` of door `enabled: true` te zetten. Draai daarna
de verify-workflow om te zien of de bron intussen weer werkt.

### 5. Nieuwsbrieven zonder RSS (TLDR AI, The Rundown AI)

Deze twee hebben geen publieke feed. Route loopt via
[Kill-the-Newsletter](https://kill-the-newsletter.com):

1. Maak daar een inbox aan. Je krijgt een mailadres plus een Atom-feed-URL.
2. Meld je met dat mailadres aan voor de nieuwsbrief.
3. Zet de feed-URL in `sources/ai_int.yaml` bij de betreffende bron en
   zet `enabled: true`.

Herhaal per nieuwsbrief. Ze staan nu uit met een lege `url`.

### 6. Supabase

Nodig voor het bewaren van artikelen in mappen en voor het beheerscherm.

1. Draai `supabase/schema.sql` in de SQL-editor van je project. Het script is
   idempotent, dus opnieuw draaien kan geen kwaad.
2. Authentication → Providers → **Email** aan (magic link).
3. Authentication → URL Configuration → Redirect URLs:
   `https://remidocc.github.io/newsbot/**`. Zonder dit stuurt de inloglink je
   naar localhost. Dit is de stap die het vaakst wordt vergeten.
4. `site/config.js` bevat de project-URL en de publishable key. Die horen
   publiek te zijn; wat je gegevens beschermt is row-level security.
5. Authentication → Users → **Add user** → *Send invitation* met je eigen
   e-mailadres. Zonder deze stap kun je niet inloggen; zie hieronder.

**Zet nooit de service-role key in `site/config.js`** — die omzeilt RLS.

#### Waarom je accounts met de hand aanmaakt

Aanmelden staat uit in dit project, en dat hoort zo. De project-URL en de
publishable key staan publiek in `site/config.js` — dat moet, anders kan de
browser er niet bij — dus met aanmelden aan kan iedereen die de site vindt een
account in jouw project maken. RLS houdt ze weliswaar bij jouw mappen vandaan,
maar het blijft jouw gratis tier die ze opsouperen.

`stuurMagicLink` stuurt daarom `create_user: false`. Een adres zonder account
krijgt geen link. Wil je er iemand bij, dan maak je die aan in Supabase onder
Authentication → Users.

Vraagt de app om een link en krijg je *"Signups not allowed for this
instance"*, dan bestaat het account nog niet. Sinds die melding wordt vertaald
staat er "Dit e-mailadres heeft geen toegang tot deze app".

#### Waarom `sources` publiek leesbaar is

Vier tabellen staan achter RLS die aan `auth.uid()` hangt. Eén uitzondering:
iedereen mag `sources` lezen. `collect.py` draait in GitHub Actions en heeft
daar geen ingelogde gebruiker. De alternatieven waren een service-role key als
repo-secret — een veel te machtige sleutel om feed-URL's mee op te halen — of
een edge function. Feed-URL's zijn niet geheim en de repo is toch al publiek.
Schrijven blijft wel aan jou voorbehouden.

**Let op:** projecten op het gratis plan pauzeren na zeven dagen zonder verkeer.
De dagelijkse workflow doet daarom een pingetje naar Supabase, zodat dat nooit
gebeurt — ook niet als je twee weken weg bent.

### 6b. Bronnen beheren vanuit de app

`/beheer` is de plek waar je zelf nieuwsbronnen toevoegt. De YAML-bestanden in
`sources/` zijn de startset; wat je in Supabase zet komt daar bovenop.
`collect.py` leest beide en voegt ze samen. Valt Supabase weg, dan draait de run
gewoon door op de startset.

De pagina toont ook het laatste verificatierapport van de repo-bronnen: per bron
levend, bevroren, geen datums of kapot. Dat komt uit `data/source_report.json`,
dat `build_site.py` meekopieert naar de site — geen Supabase aan te pas.

### 7. Pushmeldingen

Genereer eenmalig een VAPID-sleutelpaar:

```bash
.venv/bin/python scripts/gen_vapid.py
```

Het script drukt af wat waar hoort. Kort:

| Waar | Wat |
| --- | --- |
| repo-secret `VAPID_PRIVATE_KEY` | de privésleutel (één regel base64url, geen PEM) |
| repo-secret `VAPID_CLAIM_EMAIL` | `mailto:jouw@adres.nl` |
| repo-secret `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Settings → API → `service_role` |
| `site/config.js` → `vapidPublicKey` | de publieke sleutel |

Heb je geen Python bij de hand, dan geeft `npx web-push generate-vapid-keys`
exact hetzelfde formaat. Beide routes leveren base64url op, en dat is wat
pywebpush kan lezen — een PEM níet, daar struikelt `Vapid.from_string()` over.

Draai dit maar één keer. Een nieuw paar maakt alle bestaande
abonnementen ongeldig en dan moet je op elk apparaat opnieuw op "Meldingen aan"
klikken.

**De service-role key omzeilt row-level security volledig.** Hij hoort alleen in
dat ene GitHub-secret: niet in `config.js`, niet in een commit. `send_push.py`
heeft hem nodig omdat de tabel met pushabonnementen niet publiek leesbaar kan
zijn — met een endpoint plus sleutels kan iedereen jou meldingen sturen.

Aanzetten doe je op `/beheer`. De app vraagt pas toestemming ná die klik, nooit
bij het eerste bezoek: een browser die ongevraagd om toestemming vraagt krijgt
bijna altijd "nee", en dat is daarna omslachtig terug te draaien.

**iOS staat push alleen toe nadat de PWA op het beginscherm staat.** Open de site
in Safari, deel-knop → *Zet op beginscherm*, open 'm daarvandaan, en zet dan pas
meldingen aan. In Safari zelf bestaat de Push API niet eens; de knop zegt dat
dan ook.

### 8. De dagelijkse run

`.github/workflows/digest.yml` draait om 05:00 UTC en is ook met de hand te
starten via Actions → *Dagelijkse digest* → Run workflow.

Wat er gebeurt: ophalen → ontdubbelen → verrijken met `claude -p` → valideren →
site bouwen → naar Pages → melding → `data/` terugcommitten.

Alles ná het ontdubbelen staat op `continue-on-error`. Valt het verrijken om,
dan pakt `build_site.py` gewoon de nieuwste digest die er ís — die van gisteren
— en publiceert die opnieuw. Er gaat dan geen melding uit. Een dag zonder
nieuwe digest is vervelend; een kapotte site is erger.

De melding wordt pas verstuurd nadat Pages klaar is met deployen, zodat je niet
op een melding klikt voor een digest die nog niet online staat.

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
