/* Minimale Supabase-client: inloggen met magic link en lezen/schrijven via REST.
 *
 * Bewust geen supabase-js. Die is ongeveer honderd kilobyte, zou van een CDN
 * moeten komen (en dan werkt de app niet meer offline) of gevendord moeten
 * worden zonder buildstap. Wat we ervan nodig hebben is een handvol
 * fetch-aanroepen; dat past hieronder.
 */
window.newsbotDb = (function () {
  'use strict';

  var cfg = window.NEWSBOT_CONFIG || {};
  var SLEUTEL = 'newsbot:sessie';

  function ingesteld() {
    return Boolean(cfg.supabaseUrl && cfg.supabaseKey);
  }

  /* --- Sessie ---------------------------------------------------------- */

  function laadSessie() {
    try {
      return JSON.parse(localStorage.getItem(SLEUTEL) || 'null');
    } catch (e) { return null; }
  }

  function bewaarSessie(sessie) {
    try {
      if (sessie) localStorage.setItem(SLEUTEL, JSON.stringify(sessie));
      else localStorage.removeItem(SLEUTEL);
    } catch (e) { /* privémodus: dan blijft het bij deze pagina */ }
  }

  // Supabase stuurt de tokens terug in de URL-hash. Die halen we er meteen uit
  // en wissen we, zodat het token niet in de adresbalk of in de history blijft.
  function vangTokensUitUrl() {
    if (!location.hash || location.hash.indexOf('access_token') === -1) return null;
    var velden = new URLSearchParams(location.hash.slice(1));
    var access = velden.get('access_token');
    if (!access) return null;

    var sessie = {
      access_token: access,
      refresh_token: velden.get('refresh_token'),
      verloopt: Date.now() + (parseInt(velden.get('expires_in'), 10) || 3600) * 1000
    };
    bewaarSessie(sessie);
    history.replaceState(null, '', location.pathname + location.search);
    return sessie;
  }

  function verversen(sessie) {
    return fetch(cfg.supabaseUrl + '/auth/v1/token?grant_type=refresh_token', {
      method: 'POST',
      headers: { apikey: cfg.supabaseKey, 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: sessie.refresh_token })
    }).then(function (r) {
      if (!r.ok) throw new Error('sessie verlopen');
      return r.json();
    }).then(function (data) {
      var nieuw = {
        access_token: data.access_token,
        refresh_token: data.refresh_token,
        verloopt: Date.now() + (data.expires_in || 3600) * 1000
      };
      bewaarSessie(nieuw);
      return nieuw;
    }).catch(function (fout) {
      bewaarSessie(null);
      throw fout;
    });
  }

  // Ververst een minuut voor het verloopt, zodat een trage verbinding niet
  // midden in een verzoek alsnog een 401 oplevert.
  function sessie() {
    var huidig = vangTokensUitUrl() || laadSessie();
    if (!huidig) return Promise.resolve(null);
    if (Date.now() < huidig.verloopt - 60000) return Promise.resolve(huidig);
    if (!huidig.refresh_token) { bewaarSessie(null); return Promise.resolve(null); }
    return verversen(huidig).catch(function () { return null; });
  }

  function stuurMagicLink(email, terugNaar) {
    return fetch(cfg.supabaseUrl + '/auth/v1/otp', {
      method: 'POST',
      headers: { apikey: cfg.supabaseKey, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: email,
        // Bewust false. De supabaseUrl en de publishable key staan publiek in
        // config.js, dus met aanmelden aan kan iedereen die de site vindt een
        // account in dit project maken. RLS houdt ze bij elkaars gegevens weg,
        // maar het is jouw gratis tier. Accounts maak je met de hand aan in
        // Supabase (Authentication -> Users); zie README.
        create_user: false,
        options: { email_redirect_to: terugNaar || location.href }
      })
    }).then(function (r) {
      if (r.ok) return true;
      return r.json().catch(function () { return {}; }).then(function (fout) {
        var ruw = fout.msg || fout.error_description || fout.error || '';
        // Supabase antwoordt hier met "Signups not allowed for this instance"
        // of "Signups not allowed for otp". Allebei betekenen hetzelfde en
        // allebei zeggen ze niets tegen wie ze leest: het adres heeft gewoon
        // geen account.
        if (/signups? not allowed/i.test(ruw) || fout.error_code === 'otp_disabled') {
          throw new Error('Dit e-mailadres heeft geen toegang tot deze app. ' +
            'Controleer of je het goed hebt getypt.');
        }
        throw new Error(ruw || 'Versturen mislukt.');
      });
    });
  }

  function uitloggen() {
    var huidig = laadSessie();
    bewaarSessie(null);
    if (!huidig) return Promise.resolve();
    return fetch(cfg.supabaseUrl + '/auth/v1/logout', {
      method: 'POST',
      headers: {
        apikey: cfg.supabaseKey,
        Authorization: 'Bearer ' + huidig.access_token
      }
    }).catch(function () { /* lokaal zijn we hoe dan ook uitgelogd */ });
  }

  function gebruiker() {
    return sessie().then(function (s) {
      if (!s) return null;
      return fetch(cfg.supabaseUrl + '/auth/v1/user', {
        headers: { apikey: cfg.supabaseKey, Authorization: 'Bearer ' + s.access_token }
      }).then(function (r) { return r.ok ? r.json() : null; });
    });
  }

  /* --- REST ------------------------------------------------------------ */

  function rest(methode, pad, body, extraHeaders) {
    return sessie().then(function (s) {
      var headers = {
        apikey: cfg.supabaseKey,
        'Content-Type': 'application/json',
        Prefer: 'return=representation'
      };
      if (s) headers.Authorization = 'Bearer ' + s.access_token;
      Object.keys(extraHeaders || {}).forEach(function (k) {
        headers[k] = extraHeaders[k];
      });

      return fetch(cfg.supabaseUrl + '/rest/v1/' + pad, {
        method: methode,
        headers: headers,
        body: body ? JSON.stringify(body) : undefined
      });
    }).then(function (r) {
      if (!r.ok) {
        return r.text().then(function (tekst) {
          var melding = tekst;
          try { melding = JSON.parse(tekst).message || tekst; } catch (e) { /* platte tekst */ }
          throw new Error(melding || ('Supabase gaf ' + r.status));
        });
      }
      return r.status === 204 ? null : r.json();
    });
  }

  /* --- Mappen en items -------------------------------------------------- */

  var api = {
    ingesteld: ingesteld,
    sessie: sessie,
    gebruiker: gebruiker,
    stuurMagicLink: stuurMagicLink,
    uitloggen: uitloggen,
    rest: rest,

    mappen: function () {
      return rest('GET', 'folders?select=id,name,created_at&order=name.asc');
    },
    maakMap: function (naam) {
      return rest('POST', 'folders', { name: naam }).then(function (r) { return r[0]; });
    },
    hernoemMap: function (id, naam) {
      return rest('PATCH', 'folders?id=eq.' + id, { name: naam });
    },
    verwijderMap: function (id) {
      return rest('DELETE', 'folders?id=eq.' + id);
    },

    items: function (mapId) {
      var filter = mapId ? '&folder_id=eq.' + mapId : '';
      return rest('GET', 'saved_items?select=*&order=saved_at.desc' + filter);
    },
    // Alleen de URL's, voor het merken van de bewaarknoppen op de digest. Een
    // volledige items-aanroep haalt ook samenvattingen op en dat is zonde van
    // de bandbreedte op een telefoon.
    bewaardeUrls: function () {
      return rest('GET', 'saved_items?select=url');
    },
    bewaarItem: function (item) {
      // on_conflict + merge-duplicates maakt opnieuw bewaren onschadelijk.
      return rest('POST', 'saved_items?on_conflict=user_id,folder_id,url', item, {
        Prefer: 'return=representation,resolution=merge-duplicates'
      });
    },
    verplaatsItem: function (id, mapId) {
      return rest('PATCH', 'saved_items?id=eq.' + id, { folder_id: mapId });
    },
    verwijderItem: function (id) {
      return rest('DELETE', 'saved_items?id=eq.' + id);
    },

    bronnen: function () {
      return rest('GET', 'sources?select=*&order=channel.asc,priority.asc,name.asc');
    },
    maakBron: function (bron) {
      return rest('POST', 'sources', bron).then(function (r) { return r[0]; });
    },
    wijzigBron: function (id, velden) {
      return rest('PATCH', 'sources?id=eq.' + id, velden);
    },
    verwijderBron: function (id) {
      return rest('DELETE', 'sources?id=eq.' + id);
    }
  };

  return api;
})();
