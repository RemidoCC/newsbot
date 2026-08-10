/* De bewaarknop op de digest: een uitklapper met de mapkeuze.
 *
 * Bewust geen modal — de opdracht was "geen modals waar een uitklapper
 * volstaat", en dat klopt hier: je kiest een map en je bent klaar.
 */
(function () {
  'use strict';

  var db = window.newsbotDb;
  var open = null;

  function sluit() {
    if (!open) return;
    open.paneel.remove();
    open.knop.setAttribute('aria-expanded', 'false');
    open = null;
  }

  function melding(paneel, tekst) {
    var p = paneel.querySelector('.bewaar-melding');
    if (p) p.textContent = tekst;
  }

  function itemUitKnop(knop, mapId) {
    return {
      folder_id: mapId,
      title: knop.dataset.title,
      summary: knop.dataset.summary || null,
      url: knop.dataset.url,
      source_name: knop.dataset.source,
      published: knop.dataset.published || null,
      channel: knop.dataset.channel || null,
      topics: knop.dataset.topics ? knop.dataset.topics.split(',') : null
    };
  }

  function bewaarIn(knop, paneel, mapId, mapNaam) {
    melding(paneel, 'Bezig…');
    db.bewaarItem(itemUitKnop(knop, mapId)).then(function () {
      knop.setAttribute('aria-pressed', 'true');
      sluit();
      var status = document.querySelector('.zoek-uitslag');
      if (status) status.textContent = 'Bewaard in "' + mapNaam + '".';
    }).catch(function (fout) {
      melding(paneel, fout.message || 'Bewaren mislukt.');
    });
  }

  function bouwPaneel(knop, mappen) {
    var paneel = document.createElement('div');
    paneel.className = 'bewaar-paneel';

    var titel = document.createElement('p');
    titel.className = 'bewaar-titel';
    titel.textContent = 'Bewaren in';
    paneel.appendChild(titel);

    if (mappen.length) {
      var rij = document.createElement('div');
      rij.className = 'bewaar-mappen';
      mappen.forEach(function (map) {
        var k = document.createElement('button');
        k.type = 'button';
        k.className = 'mapknop';
        k.textContent = map.name;
        k.addEventListener('click', function () {
          bewaarIn(knop, paneel, map.id, map.name);
        });
        rij.appendChild(k);
      });
      paneel.appendChild(rij);
    }

    var form = document.createElement('form');
    form.className = 'bewaar-nieuw';
    var veld = document.createElement('input');
    veld.type = 'text';
    veld.placeholder = mappen.length ? 'Of een nieuwe map' : 'Naam van je eerste map';
    veld.maxLength = 60;
    veld.setAttribute('aria-label', 'Naam van een nieuwe map');
    var knopNieuw = document.createElement('button');
    knopNieuw.type = 'submit';
    knopNieuw.className = 'knop';
    knopNieuw.textContent = 'Aanmaken en bewaren';
    form.appendChild(veld);
    form.appendChild(knopNieuw);
    form.addEventListener('submit', function (event) {
      event.preventDefault();
      var naam = veld.value.trim();
      if (!naam) return;
      melding(paneel, 'Bezig…');
      db.maakMap(naam).then(function (map) {
        bewaarIn(knop, paneel, map.id, map.name);
      }).catch(function (fout) {
        melding(paneel, fout.message.indexOf('duplicate') !== -1
          ? 'Je hebt al een map met die naam.' : fout.message);
      });
    });
    paneel.appendChild(form);

    var m = document.createElement('p');
    m.className = 'bewaar-melding';
    m.setAttribute('role', 'status');
    paneel.appendChild(m);

    return paneel;
  }

  window.newsbotBewaren = function (knop) {
    if (open && open.knop === knop) { sluit(); return; }
    sluit();

    if (!db || !db.ingesteld()) {
      var status = document.querySelector('.zoek-uitslag');
      if (status) status.textContent = 'Supabase is nog niet ingesteld in site/config.js.';
      return;
    }

    var paneel = document.createElement('div');
    paneel.className = 'bewaar-paneel';
    paneel.innerHTML = '<p class="bewaar-melding">Mappen ophalen…</p>';
    knop.closest('.item').appendChild(paneel);
    knop.setAttribute('aria-expanded', 'true');
    open = { knop: knop, paneel: paneel };

    db.sessie().then(function (s) {
      if (!s) {
        paneel.innerHTML = '<p class="bewaar-melding">Log eerst in via ' +
          '<a href="opgeslagen.html">Opgeslagen</a> om te kunnen bewaren.</p>';
        return;
      }
      return db.mappen().then(function (mappen) {
        var nieuw = bouwPaneel(knop, mappen || []);
        paneel.replaceWith(nieuw);
        open.paneel = nieuw;
        var veld = nieuw.querySelector('input');
        if (veld && !(mappen || []).length) veld.focus();
      });
    }).catch(function (fout) {
      paneel.innerHTML = '';
      var m = document.createElement('p');
      m.className = 'bewaar-melding';
      m.textContent = fout.message || 'Kon de mappen niet ophalen.';
      paneel.appendChild(m);
    });
  };

  document.addEventListener('click', function (event) {
    if (!open) return;
    if (open.paneel.contains(event.target) || open.knop.contains(event.target)) return;
    sluit();
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && open) { open.knop.focus(); sluit(); }
  });
})();
