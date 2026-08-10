/* newsbot — vanilla JS, geen framework, geen build.
 * Drie dingen: tabs wisselen, client-side zoeken, en de bewaarknop.
 */
(function () {
  'use strict';

  /* --- Tabs ------------------------------------------------------------ */

  var tabs = Array.prototype.slice.call(document.querySelectorAll('.tab'));
  var panelen = Array.prototype.slice.call(document.querySelectorAll('.paneel'));
  var BEWAARD_KANAAL = 'newsbot:kanaal';

  function toon(kanaal) {
    tabs.forEach(function (tab) {
      tab.setAttribute('aria-selected', String(tab.dataset.kanaal === kanaal));
    });
    panelen.forEach(function (paneel) {
      paneel.hidden = paneel.id !== 'paneel-' + kanaal;
    });
    try { localStorage.setItem(BEWAARD_KANAAL, kanaal); } catch (e) { /* privémodus */ }
    filter();
  }

  tabs.forEach(function (tab) {
    tab.addEventListener('click', function () { toon(tab.dataset.kanaal); });
    tab.addEventListener('keydown', function (event) {
      if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
      event.preventDefault();
      var richting = event.key === 'ArrowRight' ? 1 : -1;
      var volgende = tabs[(tabs.indexOf(tab) + richting + tabs.length) % tabs.length];
      volgende.focus();
      toon(volgende.dataset.kanaal);
    });
  });

  if (tabs.length) {
    var opgeslagen = null;
    try { opgeslagen = localStorage.getItem(BEWAARD_KANAAL); } catch (e) { /* idem */ }
    var geldig = tabs.some(function (t) { return t.dataset.kanaal === opgeslagen; });
    toon(geldig ? opgeslagen : tabs[0].dataset.kanaal);
  }

  /* --- Zoeken ---------------------------------------------------------- */

  var zoekveld = document.getElementById('zoekveld');
  var uitslag = document.querySelector('.zoek-uitslag');

  function actiefPaneel() {
    return panelen.find(function (p) { return !p.hidden; });
  }

  function filter() {
    var paneel = actiefPaneel();
    if (!paneel) return;

    var term = (zoekveld ? zoekveld.value : '').trim().toLowerCase();
    var zichtbaar = 0;

    Array.prototype.forEach.call(paneel.querySelectorAll('.item'), function (item) {
      var raak = !term || (item.dataset.zoek || '').indexOf(term) !== -1;
      item.hidden = !raak;
      if (raak) zichtbaar++;
    });

    // Een sectiekop zonder items eronder is ruis.
    Array.prototype.forEach.call(paneel.querySelectorAll('[data-blok]'), function (blok) {
      var over = blok.querySelectorAll('.item:not([hidden])').length;
      blok.hidden = over === 0;
    });

    if (!uitslag) return;
    if (!term) {
      uitslag.textContent = '';
    } else if (zichtbaar === 0) {
      uitslag.textContent = 'Niets gevonden voor "' + term + '" in dit kanaal.';
    } else {
      uitslag.textContent = zichtbaar + (zichtbaar === 1 ? ' item' : ' items') + ' gevonden.';
    }
  }

  if (zoekveld) {
    zoekveld.addEventListener('input', filter);
    zoekveld.addEventListener('search', filter);
  }

  /* --- Bewaren --------------------------------------------------------- */

  // De mapkiezer komt uit opslag.js, die alleen wordt geladen als Supabase
  // is ingesteld. Zolang dat niet zo is zegt de knop eerlijk wat eraan mankeert
  // in plaats van stil te falen.
  document.addEventListener('click', function (event) {
    var knop = event.target.closest && event.target.closest('.save');
    if (!knop) return;
    if (window.newsbotBewaren) {
      window.newsbotBewaren(knop);
      return;
    }
    var melding = document.querySelector('.zoek-uitslag');
    if (melding) {
      melding.textContent = 'Bewaren werkt zodra Supabase is ingesteld (fase 6).';
    }
  });

  /* --- Offline --------------------------------------------------------- */

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      var pad = document.querySelector('link[rel="manifest"]');
      var wortel = pad && pad.getAttribute('href').indexOf('../') === 0 ? '../' : './';
      navigator.serviceWorker.register(wortel + 'sw.js').catch(function () {
        // Geen service worker is jammer, geen reden om iets te melden.
      });
    });
  }
})();
