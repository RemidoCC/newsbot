/* Publieke configuratie. Dit bestand hoort in de repo en mag gelezen worden.
 *
 * De publishable key is ontworpen om in een browser te staan; wat je gegevens
 * beschermt is row-level security in Supabase, niet geheimhouding van deze
 * sleutel. Zet hier nooit de service-role key neer — die omzeilt RLS.
 */
window.NEWSBOT_CONFIG = {
  supabaseUrl: 'https://xfblconmnzftcysutxhi.supabase.co',
  supabaseKey: 'sb_publishable_h-E-am1tQaD6kqdSxn_ksw_i3EBgSn_',

  // Wordt in fase 7 ingevuld met de publieke VAPID-sleutel.
  vapidPublicKey: ''
};
