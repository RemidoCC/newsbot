/* /opgeslagen — mappen beheren en bewaarde artikelen bekijken. */
(function () {
  'use strict';

  var db = window.newsbotDb;
  var mappen = [];
  var actieveMap = null;

  var mapkeuze = document.querySelector('.mapkeuze');
  var itemsVak = document.querySelector('.items');
  var melding = document.querySelector('.melding');
  var acties = document.querySelector('.mapacties');

  function zeg(tekst) { if (melding) melding.textContent = tekst || ''; }

  function datum(waarde) {
    if (!waarde) return '';
    try {
      return new Date(waarde).toLocaleDateString('nl-NL',
        { day: 'numeric', month: 'long', year: 'numeric' });
    } catch (e) { return ''; }
  }

  function tekenMappen() {
    mapkeuze.innerHTML = '';
    if (!mappen.length) {
      mapkeuze.innerHTML = '<p class="leeg-klein">Nog geen mappen. Maak er hiernaast een aan.</p>';
      acties.hidden = true;
      return;
    }
    mappen.forEach(function (map) {
      var knop = document.createElement('button');
      knop.type = 'button';
      knop.className = 'mapknop';
      knop.textContent = map.name;
      knop.setAttribute('aria-pressed', String(map.id === actieveMap));
      knop.addEventListener('click', function () {
        actieveMap = map.id;
        tekenMappen();
        laadItems();
      });
      mapkeuze.appendChild(knop);
    });
    acties.hidden = !actieveMap;
  }

  function tekenItems(items) {
    itemsVak.innerHTML = '';
    if (!items.length) {
      itemsVak.innerHTML = '<p class="leeg">Nog niets bewaard in deze map.</p>';
      return;
    }

    items.forEach(function (item) {
      var kaart = document.createElement('article');
      kaart.className = 'item';

      var kop = document.createElement('h3');
      kop.className = 'item-title';
      var link = document.createElement('a');
      link.href = item.url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = item.title;
      kop.appendChild(link);
      kaart.appendChild(kop);

      if (item.summary) {
        var samenvatting = document.createElement('p');
        samenvatting.className = 'item-summary';
        samenvatting.textContent = item.summary;
        kaart.appendChild(samenvatting);
      }

      var meta = document.createElement('p');
      meta.className = 'item-meta';
      var tekst = document.createElement('span');
      tekst.className = 'meta-tekst';
      tekst.textContent = item.source_name;
      if (item.published) {
        tekst.appendChild(scheiding());
        tekst.appendChild(document.createTextNode(datum(item.published)));
      }
      meta.appendChild(tekst);
      kaart.appendChild(meta);

      var rij = document.createElement('p');
      rij.className = 'item-acties';

      var verplaats = document.createElement('select');
      verplaats.className = 'verplaats';
      verplaats.setAttribute('aria-label', 'Verplaats naar een andere map');
      mappen.forEach(function (map) {
        var optie = document.createElement('option');
        optie.value = map.id;
        optie.textContent = map.name;
        optie.selected = map.id === item.folder_id;
        verplaats.appendChild(optie);
      });
      verplaats.addEventListener('change', function () {
        db.verplaatsItem(item.id, verplaats.value)
          .then(function () { zeg('Verplaatst.'); laadItems(); })
          .catch(function (f) { zeg(f.message); });
      });
      rij.appendChild(verplaats);

      var weg = document.createElement('button');
      weg.type = 'button';
      weg.className = 'knop-tekst knop-gevaar';
      weg.textContent = 'Verwijderen';
      weg.addEventListener('click', function () {
        db.verwijderItem(item.id)
          .then(function () { zeg('Verwijderd.'); laadItems(); })
          .catch(function (f) { zeg(f.message); });
      });
      rij.appendChild(weg);

      kaart.appendChild(rij);
      itemsVak.appendChild(kaart);
    });
  }

  function scheiding() {
    var punt = document.createElement('span');
    punt.className = 'dot';
    punt.textContent = '·';
    return punt;
  }

  function laadItems() {
    if (!actieveMap) { itemsVak.innerHTML = ''; return; }
    db.items(actieveMap).then(tekenItems).catch(function (f) { zeg(f.message); });
  }

  function laadMappen() {
    return db.mappen().then(function (rijen) {
      mappen = rijen || [];
      if (!actieveMap && mappen.length) actieveMap = mappen[0].id;
      if (actieveMap && !mappen.some(function (m) { return m.id === actieveMap; })) {
        actieveMap = mappen.length ? mappen[0].id : null;
      }
      tekenMappen();
      laadItems();
    }).catch(function (f) { zeg(f.message); });
  }

  window.newsbotAuth.bewaak().then(function () {
    laadMappen();

    document.querySelector('.nieuwe-map').addEventListener('submit', function (event) {
      event.preventDefault();
      var veld = document.getElementById('nieuwe-map-naam');
      var naam = veld.value.trim();
      if (!naam) return;
      db.maakMap(naam).then(function (map) {
        veld.value = '';
        actieveMap = map.id;
        zeg('Map "' + naam + '" aangemaakt.');
        return laadMappen();
      }).catch(function (f) {
        zeg(f.message.indexOf('duplicate') !== -1
          ? 'Je hebt al een map met die naam.' : f.message);
      });
    });

    acties.addEventListener('click', function (event) {
      var knop = event.target.closest('[data-actie]');
      if (!knop || !actieveMap) return;
      var map = mappen.find(function (m) { return m.id === actieveMap; });
      if (!map) return;

      if (knop.dataset.actie === 'hernoemen') {
        var nieuw = prompt('Nieuwe naam voor "' + map.name + '"', map.name);
        if (!nieuw || !nieuw.trim()) return;
        db.hernoemMap(map.id, nieuw.trim())
          .then(function () { zeg('Hernoemd.'); return laadMappen(); })
          .catch(function (f) { zeg(f.message); });
      }

      if (knop.dataset.actie === 'verwijderen') {
        if (!confirm('"' + map.name + '" verwijderen? De bewaarde artikelen ' +
                     'in deze map gaan mee.')) return;
        db.verwijderMap(map.id).then(function () {
          actieveMap = null;
          zeg('Map verwijderd.');
          return laadMappen();
        }).catch(function (f) { zeg(f.message); });
      }
    });
  });
})();
