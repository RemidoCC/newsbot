-- newsbot — schema voor Supabase.
--
-- Plakken in de SQL-editor van je project en uitvoeren. Het script is
-- idempotent: je kunt het opnieuw draaien zonder dat er iets stukgaat.
--
-- Uitgangspunten:
--
-- 1. Alles hangt aan auth.uid(). Je logt in met een magic link, en row-level
--    security zorgt dat je alleen bij je eigen rijen kunt. De publishable key
--    in de frontend hoort publiek te zijn; wat je data beschermt is RLS, niet
--    geheimhouding van die key.
--
-- 2. Eén uitzondering: `sources` is publiek leesbaar. collect.py draait in
--    GitHub Actions en heeft daar geen ingelogde gebruiker. De alternatieven
--    waren een service-role key als repo-secret (een veel te machtige sleutel
--    voor het ophalen van feed-URL's) of een edge function. Feed-URL's zijn
--    niet geheim en de repo is toch al publiek, dus publiek lezen is hier de
--    verstandigste keuze. Schrijven blijft wel aan de eigenaar voorbehouden.

-- ---------------------------------------------------------------------------
-- Mappen
-- ---------------------------------------------------------------------------

create table if not exists folders (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade
              default auth.uid(),
  name        text not null check (length(trim(name)) between 1 and 60),
  created_at  timestamptz not null default now()
);

create unique index if not exists folders_user_naam_uniek
  on folders (user_id, lower(name));

-- ---------------------------------------------------------------------------
-- Opgeslagen artikelen
-- ---------------------------------------------------------------------------

create table if not exists saved_items (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null references auth.users(id) on delete cascade
               default auth.uid(),
  folder_id    uuid references folders(id) on delete cascade,
  title        text not null,
  summary      text,
  url          text not null,
  source_name  text not null,
  published    timestamptz,
  channel      text,
  topics       text[],
  saved_at     timestamptz not null default now(),
  note         text
);

-- Hetzelfde artikel twee keer in dezelfde map bewaren heeft geen zin.
create unique index if not exists saved_items_uniek
  on saved_items (user_id, folder_id, url);

create index if not exists saved_items_op_map on saved_items (folder_id, saved_at desc);

-- ---------------------------------------------------------------------------
-- Nieuwsbronnen — beheerd vanuit /beheer
-- ---------------------------------------------------------------------------

create table if not exists sources (
  id                uuid primary key default gen_random_uuid(),
  user_id           uuid not null references auth.users(id) on delete cascade
                    default auth.uid(),
  name              text not null check (length(trim(name)) between 1 and 120),
  url               text not null,
  homepage          text,
  type              text not null default 'rss'
                    check (type in ('rss', 'newsletter', 'reddit', 'hn', 'x')),
  channel           text not null default 'ai' check (channel in ('ai', 'bieb')),
  region            text not null default 'int' check (region in ('nl', 'int')),
  language          text not null default 'nl',
  priority          smallint not null default 3 check (priority between 1 and 9),
  max_items         smallint not null default 30 check (max_items between 1 and 100),
  include_keywords  text[],
  enabled           boolean not null default true,
  -- Wordt bijgewerkt door de verify-workflow; puur informatief in de UI.
  verify_status     text check (verify_status in ('ok','verouderd','geen-datums','kapot')),
  verify_detail     text,
  verified_at       timestamptz,
  created_at        timestamptz not null default now()
);

create unique index if not exists sources_user_url_uniek on sources (user_id, url);

-- ---------------------------------------------------------------------------
-- Pushabonnementen
-- ---------------------------------------------------------------------------

create table if not exists push_subscriptions (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade
              default auth.uid(),
  endpoint    text unique not null,
  p256dh      text not null,
  auth        text not null,
  created_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Row-level security
-- ---------------------------------------------------------------------------

alter table folders            enable row level security;
alter table saved_items        enable row level security;
alter table sources            enable row level security;
alter table push_subscriptions enable row level security;

-- Eigen rijen: volledig beheer, verder niets. `with check` staat er los van
-- `using` omdat je anders een rij naar een andere gebruiker zou kunnen
-- verplaatsen met een update.
do $$
declare
  t text;
begin
  foreach t in array array['folders', 'saved_items', 'push_subscriptions']
  loop
    execute format('drop policy if exists eigen_rijen on %I', t);
    execute format(
      'create policy eigen_rijen on %I for all to authenticated
         using (user_id = auth.uid()) with check (user_id = auth.uid())', t);
  end loop;
end $$;

-- sources: iedereen mag lezen (zie toelichting bovenaan), eigenaar mag schrijven.
drop policy if exists sources_publiek_lezen on sources;
create policy sources_publiek_lezen on sources
  for select to anon, authenticated using (true);

drop policy if exists sources_eigenaar_schrijft on sources;
create policy sources_eigenaar_schrijft on sources
  for insert to authenticated with check (user_id = auth.uid());

drop policy if exists sources_eigenaar_wijzigt on sources;
create policy sources_eigenaar_wijzigt on sources
  for update to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists sources_eigenaar_verwijdert on sources;
create policy sources_eigenaar_verwijdert on sources
  for delete to authenticated using (user_id = auth.uid());

-- ---------------------------------------------------------------------------
-- Controle
-- ---------------------------------------------------------------------------

-- Na het uitvoeren zou dit vier rijen moeten geven, allemaal met rls = true.
-- select relname, relrowsecurity as rls
--   from pg_class
--  where relname in ('folders','saved_items','sources','push_subscriptions');
