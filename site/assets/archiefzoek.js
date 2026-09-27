/* Zoeken door het hele archief, in de browser.
 *
 * Geen zoekserver en geen Supabase: build_site.py schrijft alle gearchiveerde
 * items naar assets/archief-index.json en dat bestand doorzoeken we hier. Dat
 * is een paar honderd kilobyte, dus het wordt pas opgehaald zodra je echt gaat
 * typen — wie alleen de lijst met dagen komt bekijken betaalt er niets voor.
 * Daarna blijft het in de cache van de service worker staan.
 */
(function () {
  'use strict';

  var veld = document.getElementById('archiefzoek');
  var uitslag = document.querySelector('.zoek-uitslag');
  var bak = document.querySelector('.zoekresultaten');
  var filters = Array.prototype.slice.call(document.querySelectorAll('.filterknop'));
  if (!veld || !bak) return;

  var MAX_TONEN = 80;
  var index = null;
  var bezig = null;
  var kanaal = '';

  /* --- De index ophalen -------------------------------------------------- */

  function haalIndex() {
    if (index) return Promise.resolve(index);
    if (bezig) return bezig;

    melden('Archief laden…');
    bezig = fetch('assets/archief-index.json').then(function (r) {
      if (!r.ok) throw new Error('Archief niet gevonden (' + r.status + ').');
      return r.json();
    }).then(function (data) {
      // Elke rij één keer voorbereiden in plaats van bij elke toetsaanslag
      // opnieuw: bij ruim duizend items scheelt dat merkbaar tikken.
      index = [];
      (data.dagen || []).forEach(function (dag) {
        var datum = dag[0];
        dag[1].forEach(function (r) {
          index.push({
            titel: r[0], samenvatting: r[1], url: r[2],
            bron: r[3], kanaal: r[4], onderwerpen: r[5] || [],
            datum: datum,
            hooi: (r[0] + ' ' + r[1] + ' ' + r[3] + ' ' +
                   (r[5] || []).join(' ')).toLowerCase()
          });
        });
      });
      bezig = null;
      return index;
    }).catch(function (fout) {
      bezig = null;
      throw fout;
    });
    return bezig;
  }

  /* --- Zoeken ------------------------------------------------------------ */

  // Alle woorden moeten voorkomen, in welke volgorde dan ook. "kb subsidie"
  // vindt dus ook een kop waarin die twee ver uit elkaar staan.
  function zoek(term) {
    var woorden = term.toLowerCase().split(/\s+/).filter(Boolean);
    return index.filter(function (rij) {
      if (kanaal && rij.kanaal !== kanaal) return false;
      for (var i = 0; i < woorden.length; i++) {
        if (rij.hooi.indexOf(woorden[i]) === -1) return false;
      }
      return true;
    });
  }

  var MAANDEN = ['januari', 'februari', 'maart', 'april', 'mei', 'juni', 'juli',
                 'augustus', 'september', 'oktober', 'november', 'december'];

  function nederlandseDatum(iso) {
    var d = iso.split('-');
    if (d.length !== 3) return iso;
    return parseInt(d[2], 10) + ' ' + MAANDEN[parseInt(d[1], 10) - 1] + ' ' + d[0];
  }

  /* --- Tonen ------------------------------------------------------------- */

  function melden(tekst) {
    if (uitslag) uitslag.textContent = tekst;
  }

  // textContent in plaats van innerHTML: koppen en samenvattingen komen uit een
  // taalmodel dat nieuwsartikelen verwerkt, dus daar kan van alles in staan.
  function maakEl(tag, klasse, tekst) {
    var el = document.createElement(tag);
    if (klasse) el.className = klasse;
    if (tekst !== undefined) el.textContent = tekst;
    return el;
  }

  function toonResultaten(rijen, term) {
    bak.textContent = '';

    if (!rijen.length) {
      bak.hidden = true;
      melden('Niets gevonden voor "' + term + '"' +
             (kanaal ? ' in dit kanaal.' : '.'));
      return;
    }

    var lijst = maakEl('ol', 'treffers');
    rijen.slice(0, MAX_TONEN).forEach(function (rij) {
      var li = document.createElement('li');
      li.className = 'treffer';

      var kop = maakEl('h3', 'item-title');
      var a = maakEl('a', null, rij.titel);
      a.href = rij.url;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      kop.appendChild(a);
      li.appendChild(kop);

      if (rij.samenvatting) {
        li.appendChild(maakEl('p', 'item-summary', rij.samenvatting));
      }

      var meta = maakEl('p', 'item-meta');
      meta.appendChild(maakEl('span', 'item-source', rij.bron));
      meta.appendChild(maakEl('span', 'dot', '·'));
      // Naar de dag waarop dit stond, zodat je het in zijn context terugziet.
      var dag = maakEl('a', 'treffer-datum', nederlandseDatum(rij.datum));
      dag.href = 'archief/' + rij.datum + '.html';
      meta.appendChild(dag);
      li.appendChild(meta);

      lijst.appendChild(li);
    });

    bak.appendChild(lijst);
    bak.hidden = false;

    var n = rijen.length;
    melden(n === 1 ? '1 artikel gevonden.'
                   : n + ' artikelen gevonden' +
                     (n > MAX_TONEN ? '; de eerste ' + MAX_TONEN + ' staan hieronder.' : '.'));
  }

  function leeg() {
    bak.textContent = '';
    bak.hidden = true;
    melden('');
  }

  /* --- Aansturing -------------------------------------------------------- */

  function voerUit() {
    var term = veld.value.trim();
    if (!term) { leeg(); return; }

    haalIndex().then(function () {
      // Tussen het ophalen en nu kan het veld alweer leeg zijn.
      var nu = veld.value.trim();
      if (!nu) { leeg(); return; }
      toonResultaten(zoek(nu), nu);
    }).catch(function (fout) {
      bak.hidden = true;
      melden(fout.message || 'Kon het archief niet laden.');
    });
  }

  // Wachten tot het typen even stilvalt. Zonder dit draait de filter bij elke
  // aanslag over duizend items heen.
  var wacht = null;
  veld.addEventListener('input', function () {
    clearTimeout(wacht);
    wacht = setTimeout(voerUit, 150);
  });
  veld.addEventListener('search', voerUit);

  filters.forEach(function (knop) {
    knop.addEventListener('click', function () {
      kanaal = knop.dataset.kanaal || '';
      filters.forEach(function (k) {
        k.setAttribute('aria-pressed', String(k === knop));
      });
      voerUit();
    });
  });

  // Kom je hier vanaf een digestpagina die niets vond, dan staat de zoekterm
  // in de URL. Meteen uitvoeren, anders moet je hem opnieuw intikken.
  var vooraf = new URLSearchParams(location.search).get('q');
  if (vooraf) {
    veld.value = vooraf;
    voerUit();
  }
})();
