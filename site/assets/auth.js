/* Inlogpoort, gedeeld door /opgeslagen en /beheer.
 *
 * Roept newsbotAuth.bewaak() aan en geeft een promise terug die pas oplost als
 * er een sessie is. Is die er niet, dan blijft het inlogformulier staan en lost
 * de promise nooit op — de pagina toont dan simpelweg niets van jou.
 */
window.newsbotAuth = (function () {
  'use strict';

  var db = window.newsbotDb;

  function toon(element, zichtbaar) {
    if (element) element.hidden = !zichtbaar;
  }

  function bewaak() {
    var poort = document.querySelector('.inlogpoort');
    var balk = document.querySelector('.inlogbalk');
    var inhoud = document.querySelector('.alleen-ingelogd');
    var melding = document.querySelector('.inlog-melding');

    if (!db || !db.ingesteld()) {
      toon(poort, true);
      if (melding) {
        melding.textContent = 'Supabase is nog niet ingesteld in site/config.js.';
      }
      var form = document.querySelector('.inlogform');
      if (form) form.hidden = true;
      return new Promise(function () { /* blijft open */ });
    }

    return new Promise(function (klaar) {
      function controleer() {
        db.gebruiker().then(function (wie) {
          if (wie) {
            toon(poort, false);
            toon(balk, true);
            toon(inhoud, true);
            var wieSpan = document.querySelector('.inlog-wie');
            if (wieSpan) wieSpan.textContent = 'Ingelogd als ' + (wie.email || 'jou');
            klaar(wie);
          } else {
            toon(poort, true);
            toon(balk, false);
            toon(inhoud, false);
          }
        }).catch(function () {
          toon(poort, true);
        });
      }

      var form = document.querySelector('.inlogform');
      if (form) {
        form.addEventListener('submit', function (event) {
          event.preventDefault();
          var veld = document.getElementById('inlog-email');
          var knop = form.querySelector('button');
          if (!veld || !veld.value) return;

          knop.disabled = true;
          if (melding) melding.textContent = 'Bezig met versturen…';

          db.stuurMagicLink(veld.value.trim(), location.href).then(function () {
            if (melding) {
              melding.textContent = 'Verstuurd. Open de link in je mail — ook op ' +
                'je telefoon werkt dat, mits je hem daar opent.';
            }
            form.hidden = true;
          }).catch(function (fout) {
            knop.disabled = false;
            if (melding) melding.textContent = fout.message || 'Versturen mislukt.';
          });
        });
      }

      var uit = document.querySelector('[data-actie="uitloggen"]');
      if (uit) {
        uit.addEventListener('click', function () {
          db.uitloggen().then(function () { location.reload(); });
        });
      }

      controleer();
    });
  }

  return { bewaak: bewaak };
})();
