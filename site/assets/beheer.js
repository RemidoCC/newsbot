/* /beheer — eigen nieuwsbronnen beheren, plus de status van de repo-bronnen. */
(function () {
  'use strict';

  var db = window.newsbotDb;
  var lijst = document.querySelector('.bronlijst');
  var melding = document.querySelector('.melding');

  var STATUSLABEL = {
    ok: 'levend',
    verouderd: 'bevroren',
    'geen-datums': 'geen datums',
    kapot: 'kapot'
  };

  function zeg(tekst) { if (melding) melding.textContent = tekst || ''; }

  function statusVlag(status, detail) {
    var span = document.createElement('span');
    span.className = 'status status-' + (status || 'onbekend');
    span.textContent = STATUSLABEL[status] || 'nog niet getest';
    if (detail) span.title = detail;
    return span;
  }

  function tekenBronnen(bronnen) {
    lijst.innerHTML = '';
    if (!bronnen.length) {
      lijst.innerHTML = '<p class="leeg">Je hebt zelf nog geen bronnen toegevoegd. ' +
        'De bronnen uit de repo draaien gewoon door.</p>';
      return;
    }

    bronnen.forEach(function (bron) {
      var rij = document.createElement('div');
      rij.className = 'bronrij' + (bron.enabled ? '' : ' bronrij-uit');

      var kop = document.createElement('div');
      kop.className = 'bronrij-kop';

      var naam = document.createElement('span');
      naam.className = 'bronrij-naam';
      naam.textContent = bron.name;
      kop.appendChild(naam);
      kop.appendChild(statusVlag(bron.verify_status, bron.verify_detail));
      rij.appendChild(kop);

      var meta = document.createElement('p');
      meta.className = 'item-meta';
      var tekst = document.createElement('span');
      tekst.className = 'meta-tekst';
      tekst.textContent = bron.channel === 'bieb' ? 'Bibliotheek' : 'AI';
      var punt = document.createElement('span');
      punt.className = 'dot'; punt.textContent = '·';
      tekst.appendChild(punt);
      tekst.appendChild(document.createTextNode(
        bron.region === 'nl' ? '🇳🇱' : '🌍'));
      var punt2 = document.createElement('span');
      punt2.className = 'dot'; punt2.textContent = '·';
      tekst.appendChild(punt2);
      tekst.appendChild(document.createTextNode('prioriteit ' + bron.priority));
      meta.appendChild(tekst);
      rij.appendChild(meta);

      var url = document.createElement('a');
      url.className = 'bronrij-url';
      url.href = bron.url;
      url.target = '_blank';
      url.rel = 'noopener noreferrer';
      url.textContent = bron.url;
      rij.appendChild(url);

      var acties = document.createElement('p');
      acties.className = 'item-acties';

      var schakel = document.createElement('button');
      schakel.type = 'button';
      schakel.className = 'knop-tekst';
      schakel.textContent = bron.enabled ? 'Uitzetten' : 'Aanzetten';
      schakel.addEventListener('click', function () {
        db.wijzigBron(bron.id, { enabled: !bron.enabled })
          .then(function () { zeg(bron.name + (bron.enabled ? ' uitgezet.' : ' aangezet.')); laad(); })
          .catch(function (f) { zeg(f.message); });
      });
      acties.appendChild(schakel);

      var weg = document.createElement('button');
      weg.type = 'button';
      weg.className = 'knop-tekst knop-gevaar';
      weg.textContent = 'Verwijderen';
      weg.addEventListener('click', function () {
        if (!confirm('"' + bron.name + '" verwijderen?')) return;
        db.verwijderBron(bron.id)
          .then(function () { zeg('Verwijderd.'); laad(); })
          .catch(function (f) { zeg(f.message); });
      });
      acties.appendChild(weg);

      rij.appendChild(acties);
      lijst.appendChild(rij);
    });
  }

  function laad() {
    return db.bronnen().then(tekenBronnen).catch(function (f) { zeg(f.message); });
  }

  /* Het rapport van de repo-bronnen is een statisch bestand dat build_site.py
     meekopieert uit de laatste verify-run. Geen Supabase nodig. */
  function laadRapport() {
    var vak = document.querySelector('.bronrapport');
    fetch('assets/source_report.json').then(function (r) {
      if (!r.ok) throw new Error('geen rapport');
      return r.json();
    }).then(function (rijen) {
      vak.innerHTML = '';
      var volgorde = { kapot: 0, verouderd: 1, 'geen-datums': 1, ok: 2 };
      rijen.sort(function (a, b) {
        return (volgorde[a.status] ?? 0) - (volgorde[b.status] ?? 0);
      }).forEach(function (bron) {
        var rij = document.createElement('div');
        rij.className = 'bronrij bronrij-compact' + (bron.enabled ? '' : ' bronrij-uit');
        var kop = document.createElement('div');
        kop.className = 'bronrij-kop';
        var naam = document.createElement('span');
        naam.className = 'bronrij-naam';
        naam.textContent = bron.name;
        kop.appendChild(naam);
        kop.appendChild(statusVlag(bron.enabled ? bron.status : null,
                                   bron.enabled ? bron.detail : 'staat uit'));
        rij.appendChild(kop);
        if (bron.detail) {
          var d = document.createElement('p');
          d.className = 'bronrij-detail';
          d.textContent = bron.detail;
          rij.appendChild(d);
        }
        vak.appendChild(rij);
      });
    }).catch(function () {
      vak.innerHTML = '<p class="leeg-klein">Nog geen rapport. Draai de ' +
        'workflow "Bronnen verifiëren" in Actions.</p>';
    });
  }

  laadRapport();

  window.newsbotAuth.bewaak().then(function () {
    laad();

    document.querySelector('.bronform').addEventListener('submit', function (event) {
      event.preventDefault();
      var woorden = document.getElementById('bron-woorden').value
        .split(',').map(function (w) { return w.trim(); }).filter(Boolean);

      var bron = {
        name: document.getElementById('bron-naam').value.trim(),
        url: document.getElementById('bron-url').value.trim(),
        homepage: document.getElementById('bron-homepage').value.trim() || null,
        channel: document.getElementById('bron-kanaal').value,
        region: document.getElementById('bron-regio').value,
        priority: parseInt(document.getElementById('bron-prioriteit').value, 10),
        include_keywords: woorden.length ? woorden : null,
        type: 'rss',
        enabled: true
      };

      db.maakBron(bron).then(function () {
        event.target.reset();
        zeg(bron.name + ' toegevoegd. Hij doet mee vanaf de volgende run.');
        laad();
      }).catch(function (f) {
        zeg(f.message.indexOf('duplicate') !== -1
          ? 'Die URL staat er al bij.' : f.message);
      });
    });
  });
})();
