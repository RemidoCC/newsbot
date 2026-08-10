/* Service worker: de laatst geladen digest moet offline te lezen zijn.
 *
 * Strategie per soort verzoek:
 * - navigatie (een pagina): eerst netwerk, bij falen de cache. Zo zie je online
 *   altijd de verse digest en offline de laatste die je had.
 * - assets (css, js, iconen): eerst cache, dan netwerk. Die veranderen zelden
 *   en het scheelt wachten.
 *
 * De versie in CACHE hieronder wordt door build_site.py niet aangepast; hij
 * hoeft alleen te wijzigen als de assets veranderen.
 */
var CACHE = 'newsbot-v1';
var KERN = [
  './',
  './index.html',
  './archief.html',
  './assets/app.css',
  './assets/app.js',
  './assets/icon.svg',
  './manifest.webmanifest'
];

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(CACHE).then(function (cache) {
      // addAll faalt in zijn geheel als één bestand mist; per stuk is robuuster.
      return Promise.all(KERN.map(function (url) {
        return cache.add(url).catch(function () { return null; });
      }));
    }).then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (namen) {
      return Promise.all(namen.map(function (naam) {
        return naam === CACHE ? null : caches.delete(naam);
      }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (event) {
  var verzoek = event.request;
  if (verzoek.method !== 'GET') return;

  var url = new URL(verzoek.url);
  if (url.origin !== self.location.origin) return;

  if (verzoek.mode === 'navigate') {
    event.respondWith(
      fetch(verzoek).then(function (antwoord) {
        var kopie = antwoord.clone();
        caches.open(CACHE).then(function (cache) { cache.put(verzoek, kopie); });
        return antwoord;
      }).catch(function () {
        return caches.match(verzoek).then(function (gevonden) {
          return gevonden || caches.match('./index.html');
        });
      })
    );
    return;
  }

  event.respondWith(
    caches.match(verzoek).then(function (gevonden) {
      return gevonden || fetch(verzoek).then(function (antwoord) {
        var kopie = antwoord.clone();
        caches.open(CACHE).then(function (cache) { cache.put(verzoek, kopie); });
        return antwoord;
      });
    })
  );
});

/* --- Pushmeldingen (fase 7) ------------------------------------------- */

self.addEventListener('push', function (event) {
  var data = { title: 'Nieuwe digest', body: '' };
  try {
    if (event.data) data = Object.assign(data, event.data.json());
  } catch (e) { /* platte tekst is ook goed */ }

  event.waitUntil(self.registration.showNotification(data.title, {
    body: data.body,
    icon: './assets/icon-180.png',
    badge: './assets/icon-180.png',
    tag: 'newsbot-digest'
  }));
});

self.addEventListener('notificationclick', function (event) {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (lijst) {
      for (var i = 0; i < lijst.length; i++) {
        if ('focus' in lijst[i]) return lijst[i].focus();
      }
      return self.clients.openWindow('./index.html');
    })
  );
});
