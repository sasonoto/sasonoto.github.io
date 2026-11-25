-- Website content database, schema `site`. Same file runs on Supabase (project personal-site) and chicago-o (site_db).
-- Master copy of the content is the repo's _data/*.yml; `./site db sync` replaces these rows from it.
-- Nothing here is read by the website itself (it is static), so no table is exposed to the browser.

create schema if not exists site;

create table if not exists site.schema_migrations (
  version    text primary key,
  applied_at timestamptz not null default now()
);

create table site.profile (
  id            smallint primary key default 1 check (id = 1),   -- one row
  name          text not null,
  headline      text,
  affiliation   text,
  institution   text,
  location      text,
  email         text,
  github        text,
  linkedin      text,
  ssrn_author   text,
  cv_pdf        text,
  cv_updated    text,
  portrait      text,
  bio           text,
  employer_name text,
  employer_note text
);

create table site.interests (
  id   serial primary key,
  sort int  not null,
  text text not null
);

create table site.news (
  id         serial primary key,
  sort       int  not null,
  date_label text not null,
  text       text not null
);

create table site.papers (
  id        serial primary key,
  sort      int  not null,
  slug      text not null unique,
  status    text not null check (status in ('working_paper', 'published', 'in_progress')),
  title     text not null,
  coauthors text[] not null default '{}',
  year      int,
  revised   int,
  summary   text
);

create table site.paper_links (
  id       serial primary key,
  paper_id int  not null references site.papers (id) on delete cascade,
  sort     int  not null,
  label    text not null,
  url      text not null
);

create table site.projects (
  id          serial primary key,
  sort        int  not null,
  slug        text not null unique,
  name        text not null,
  years       text,
  role        text,
  description text,
  stack       text[] not null default '{}',
  adopted     text
);

create table site.teaching (
  id    serial primary key,
  sort  int  not null,
  org   text not null,
  role  text,
  years text
);

create table site.teaching_items (
  id          serial primary key,
  teaching_id int  not null references site.teaching (id) on delete cascade,
  sort        int  not null,
  text        text not null
);

create table site.education (
  id     serial primary key,
  sort   int  not null,
  years  text,
  degree text not null,
  school text,
  notes  text[] not null default '{}'
);

create table site.positions (
  id    serial primary key,
  sort  int  not null,
  kind  text not null check (kind in ('research', 'professional', 'leave')),
  years text,
  title text not null,
  place text
);

create table site.position_bullets (
  id          serial primary key,
  position_id int  not null references site.positions (id) on delete cascade,
  sort        int  not null,
  text        text not null
);

create table site.cv_entries (            -- short dated lines: awards, service, certifications
  id      serial primary key,
  section text not null check (section in ('award', 'service', 'certification')),
  sort    int  not null,
  years   text,
  text    text not null
);

create table site.skills (
  id    serial primary key,
  sort  int  not null,
  grp   text not null,
  items text not null
);

create table site.sync_runs (
  id         serial primary key,
  synced_at  timestamptz not null default now(),
  git_commit text,
  counts     jsonb not null
);

-- Locked down: row-level security on, no policies, so only the owner / service connection can read or write.
do $$
declare t text;
begin
  for t in select tablename from pg_tables where schemaname = 'site' loop
    execute format('alter table site.%I enable row level security', t);
  end loop;
end $$;

revoke all on schema site from public;

-- Supabase only: the browser roles get nothing in this schema (they do not exist on chicago-o).
do $$
begin
  if exists (select 1 from pg_roles where rolname = 'anon') then
    execute 'revoke all on schema site from anon, authenticated';
    execute 'revoke all on all tables in schema site from anon, authenticated';
  end if;
end $$;
