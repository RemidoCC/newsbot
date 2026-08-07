# design-refs

Werkmap voor fase 5a: de design-tokens van [ai.nl](https://www.ai.nl) ophalen
zodat `site/tokens.css` echte, herleidbare waarden bevat in plaats van geraden
hexcodes.

De omgeving waarin de bot gebouwd wordt kan ai.nl niet bereiken — de egress-proxy
blokkeert het domein. Daarom komt de bron hier handmatig binnen.

## Wat hier hoort

```bash
curl -s https://www.ai.nl > design-refs/ainl.html

# zoek in die HTML de gecompileerde stylesheet onder /assets/
grep -o '/assets/[^"]*\.css' design-refs/ainl.html | sort -u

# en haal die op
curl -s https://www.ai.nl/assets/<bestandsnaam>.css > design-refs/ainl.css
```

Beide bestanden mogen hier blijven staan als bronvermelding. Waar het om gaat:

- de CSS custom properties (kleuren, spacing, radii, schaduwen)
- de `font-family`-stacks
- de `@font-face`- of Google-Fonts-imports
- de type-schaal voor h1 t/m h4, body en small

Die gaan naar `site/tokens.css`, met bovenaan in commentaar de datum en de URL
waar ze vandaan komen.

## Als de site client-side rendert

Dan levert de HTML weinig op. In dat geval volstaan twee screenshots van ai.nl,
desktop en mobiel, waaruit kleuren en typografie afgelezen worden. Dat geeft
benaderde waarden; dat wordt dan zo genoteerd in `site/tokens.css`.
