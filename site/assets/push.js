/* Pushmeldingen aanzetten. Toestemming wordt pas gevraagd ná een klik.
 *
 * Nooit bij het eerste bezoek: een browser die ongevraagd om toestemming vraagt
 * krijgt bijna altijd "nee", en dan is de weg terug omslachtig.
 */
(function () {
  'use strict';

  var db = window.newsbotDb;
  var cfg = window.NEWSBOT_CONFIG || {};

  var knop = document.querySelector('[data-actie="meldingen-aan"]');
  var melding = document.querySelector('.push-melding');
  if (!knop) return;

  function zeg(tekst) { if (melding) melding.textContent = tekst; }

  // Op iOS bestaat de Push API alleen als de PWA op het beginscherm staat.
  function opIos() {
    return /iPad|iPhone|iPod/.test(navigator.userAgent) ||
      (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  }
  function alsAppGeinstalleerd() {
    return window.matchMedia('(display-mode: standalone)').matches ||
      window.navigator.standalone === true;
  }

  function sleutelNaarBytes(base64) {
    var opvulling = '='.repeat((4 - base64.length % 4) % 4);
    var net = (base64 + opvulling).replace(/-/g, '+').replace(/_/g, '/');
    var ruw = atob(net);
    var bytes = new Uint8Array(ruw.length);
    for (var i = 0; i < ruw.length; i++) bytes[i] = ruw.charCodeAt(i);
    return bytes;
  }

  function bewaarAbonnement(abonnement) {
    var json = abonnement.toJSON();
    return db.rest('POST', 'push_subscriptions?on_conflict=endpoint', {
      endpoint: json.endpoint,
      p256dh: json.keys.p256dh,
      auth: json.keys.auth
    }, { Prefer: 'return=representation,resolution=merge-duplicates' });
  }

  function toonStand() {
    if (!('Notification' in window) || !('PushManager' in window)) {
      knop.disabled = true;
      if (opIos() && !alsAppGeinstalleerd()) {
        zeg('Op iPhone en iPad werkt dit pas als de app op je beginscherm ' +
            'staat. Deel-knop → Zet op beginscherm, open hem daarvandaan, en ' +
            'kom hier terug.');
      } else {
        zeg('Deze browser ondersteunt geen pushmeldingen.');
      }
      return;
    }
    if (Notification.permission === 'denied') {
      knop.disabled = true;
      zeg('Meldingen staan geblokkeerd voor deze site. Dat kun je alleen in ' +
          'de instellingen van je browser terugdraaien.');
      return;
    }
    if (Notification.permission === 'granted') {
      navigator.serviceWorker.ready.then(function (reg) {
        return reg.pushManager.getSubscription();
      }).then(function (abonnement) {
        if (abonnement) {
          knop.textContent = 'Meldingen staan aan';
          knop.disabled = true;
          zeg('Je krijgt een melding zodra er een nieuwe digest klaarstaat.');
        }
      });
    }
  }

  knop.addEventListener('click', function () {
    if (!cfg.vapidPublicKey) {
      zeg('De VAPID-sleutel ontbreekt nog in site/config.js (fase 7, stap 1).');
      return;
    }

    knop.disabled = true;
    zeg('Toestemming vragen…');

    Notification.requestPermission().then(function (antwoord) {
      if (antwoord !== 'granted') {
        knop.disabled = false;
        zeg('Geen toestemming gegeven. Je kunt het later opnieuw proberen.');
        return;
      }
      return navigator.serviceWorker.ready.then(function (reg) {
        return reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: sleutelNaarBytes(cfg.vapidPublicKey)
        });
      }).then(bewaarAbonnement).then(function () {
        knop.textContent = 'Meldingen staan aan';
        zeg('Gelukt. Je krijgt één melding per dag, alleen als er iets is.');
      });
    }).catch(function (fout) {
      knop.disabled = false;
      zeg(fout.message || 'Aanzetten mislukt.');
    });
  });

  toonStand();
})();
