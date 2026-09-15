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
      var codeForm = document.querySelector('.inlogcode');
      var adres = '';

      if (form) {
        form.addEventListener('submit', function (event) {
          event.preventDefault();
          var veld = document.getElementById('inlog-email');
          var knop = form.querySelector('button');
          if (!veld || !veld.value) return;

          adres = veld.value.trim();
          knop.disabled = true;
          if (melding) melding.textContent = 'Bezig met versturen…';

          db.stuurMagicLink(adres, location.href).then(function () {
            if (melding) {
              melding.textContent = 'Verstuurd. Tik de code uit de mail hier in. ' +
                'De link in diezelfde mail werkt ook, maar alleen als hij opent ' +
                'in deze browser — op een telefoon meestal niet.';
            }
            form.hidden = true;
            toon(codeForm, true);
            var codeVeld = document.getElementById('inlog-code');
            if (codeVeld) codeVeld.focus();
          }).catch(function (fout) {
            knop.disabled = false;
            if (melding) melding.textContent = fout.message || 'Versturen mislukt.';
          });
        });
      }

      if (codeForm) {
        codeForm.addEventListener('submit', function (event) {
          event.preventDefault();
          var veld = document.getElementById('inlog-code');
          var knop = codeForm.querySelector('button');
          // Mensen plakken de code met een spatie erin, of met het streepje dat
          // sommige mailclients eromheen zetten. Dat is geen invoerfout.
          var code = veld ? veld.value.replace(/\D/g, '') : '';
          if (!code) return;

          knop.disabled = true;
          if (melding) melding.textContent = 'Bezig met inloggen…';

          db.verifieerCode(adres, code).then(function () {
            toon(codeForm, false);
            if (melding) melding.textContent = '';
            controleer();
          }).catch(function (fout) {
            knop.disabled = false;
            if (veld) { veld.value = ''; veld.focus(); }
            if (melding) melding.textContent = fout.message || 'Inloggen mislukt.';
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
