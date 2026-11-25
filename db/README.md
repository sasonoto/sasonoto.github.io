# Content database (schema `site`)

The website is static and never reads the database. The database is a structured copy of the content, for queries and
for generating tailored resumes or the LaTeX CV later.

- **Master copy:** `_data/*.yml` in this repo. Edit there, commit, then `./site db sync`.
  Sync replaces every row in one transaction (truncate + insert), so the database always equals the YAML.
  Never edit rows by hand: the next sync overwrites them.
- **Two copies, same schema:** Supabase project `personal-site` (`SUPABASE_POOLER_URL`, fallback `SUPABASE_DB_URL`) and
  chicago-o `site_db` owned by `site_user` (`CHICAGO_DB_URL`, Tailscale only). Connection strings live in `.env`
  (git-ignored, never printed). Template: `.env.example`.
- **Locked down:** row-level security on every table with no policies; `public` (and on Supabase `anon`,
  `authenticated`) get nothing. Only the owner connection in `.env` reads or writes.

| command | does |
|:--|:--|
| `./site db migrate [--target T]` | apply new files in `db/migrations/` (tracked in `site.schema_migrations`) |
| `./site db sync [--target T] [--dry-run]` | replace all rows from `_data/*.yml`; records a row in `site.sync_runs` with the git commit |
| `./site db check [--target T]` | connection, schema version, row counts, last sync |

`T` = `supabase`, `chicago` or `all` (default). A target with no URL in `.env` is skipped.

| table | from |
|:--|:--|
| `profile` (one row), `interests` | `_data/profile.yml` (+ `cv.yml` employer) |
| `news` | `_data/news.yml` |
| `papers`, `paper_links` | `_data/papers.yml` |
| `projects` | `_data/projects.yml` |
| `teaching`, `teaching_items` | `_data/teaching.yml` |
| `education`, `positions`, `position_bullets`, `cv_entries` (award / service / certification), `skills` | `_data/cv.yml` |

Setup once: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`, fill `.env`, `./site db migrate`, `./site db sync`.
Supabase free projects pause after a quiet week; the site does not care, but sync fails until the project is restored
(a weekly keep-alive on chicago-o avoids it).
