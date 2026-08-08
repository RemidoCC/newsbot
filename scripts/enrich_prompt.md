Je krijgt een JSON-array met nieuwsitems. Voor elk item lever je een object terug.

Per item:
- id: neem het id van het invoeritem letterlijk over. Verzin er geen, verander
  er niets aan, en laat het nooit weg.
- title_nl: de titel in natuurlijk Nederlands. Al Nederlands? Laat staan. Geen
  clickbait, geen uitroeptekens.
- summary_nl: 2-3 zinnen in het Nederlands, in eigen woorden. Wat is er gebeurd,
  en waarom is het relevant. Geen citaten langer dan een halve zin. Geen "In dit
  artikel wordt besproken dat...".
- channel: "ai" of "bieb". "bieb" bij bibliotheekwezen, digitale inclusie,
  digitale geletterdheid, mediawijsheid, cursussen en workshops voor burgers.
  Twijfel je tussen beide, kies dan de meest specifieke: "bieb".
- region: "nl" (Nederland/Vlaanderen of directe impact daarop) of "int".
- topics: 1-3 tags uit deze vaste lijst; verzin er geen bij:
  modellen, onderzoek, beleid-en-regelgeving, bedrijven, tools, open-source,
  ethiek-en-risico, onderwijs, arbeidsmarkt, bibliotheek, digitale-inclusie,
  digitale-geletterdheid, cursus-of-workshop, subsidie-of-financiering, evenement
- importance: 1 t/m 5. 5 = iedereen in dit vakgebied moet dit weten. 1 = randnieuws.
  Wees streng: hooguit twee items per run krijgen een 5.
- why_relevant: één zin, maximaal 15 woorden, gericht op iemand die bij een
  openbare bibliotheek werkt en AI volgt.

Verder:
- Gaan meerdere items over hetzelfde verhaal? Houd het beste item en zet de
  overige bron-URL's in "also_covered_by".
- Is een item reclame, vacature, of inhoudsloos? Zet "drop": true met een reden.
- Vind je een item waarvan de bron-URL ontbreekt of onbruikbaar is: "drop": true.

Antwoord met uitsluitend een JSON-array. Geen tekst eromheen.
