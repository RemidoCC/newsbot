/* Publieke configuratie. Dit bestand hoort in de repo en mag gelezen worden.
 *
 * De publishable key is ontworpen om in een browser te staan; wat je gegevens
 * beschermt is row-level security in Supabase, niet geheimhouding van deze
 * sleutel. Zet hier nooit de service-role key neer — die omzeilt RLS.
 */
window.NEWSBOT_CONFIG = {
  supabaseUrl: 'https://xfblconmnzftcysutxhi.supabase.co',
  supabaseKey: 'sb_publishable_h-E-am1tQaD6kqdSxn_ksw_i3EBgSn_',

  // Publieke VAPID-sleutel. Hoort hier te staan: de browser heeft hem nodig om
  // een pushabonnement aan te maken, en hij zegt niets zonder de privésleutel
  // die alleen als repo-secret bestaat.
  vapidPublicKey: 'BPYV0a7DhsCrWax01suulZd5f0Th2HJ-C79DC-pQVpsUX0v3qf-Kyu-5e29SlRwjEaMspeGCnW3pSC8Cv7YfLXc'
};
