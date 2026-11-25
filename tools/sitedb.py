"""Website content database (schema `site`) on Supabase and chicago-o. Contract: db/README.md.

    ./site db migrate [--target T]            apply new files in db/migrations/
    ./site db sync [--target T] [--dry-run]   replace all rows from _data/*.yml (the master copy), one transaction
    ./site db check [--target T]              connection, schema version, row counts, last sync

T = supabase | chicago | all (default all; a target whose URL is missing from .env is skipped).
Secrets: values of .env are never printed; driver errors pass through scrub().
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote, unquote

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "_data"
MIGRATIONS = ROOT / "db" / "migrations"
TARGETS = {  # target -> .env keys, first one present wins
    "supabase": ["SUPABASE_POOLER_URL", "SUPABASE_DB_URL"],
    "chicago": ["CHICAGO_DB_URL"],
}
TABLES = ["profile", "interests", "news", "papers", "paper_links", "projects", "teaching", "teaching_items",
          "education", "positions", "position_bullets", "cv_entries", "skills"]
_SECRETS: set[str] = set()


class SiteDbError(Exception):
    """A message that is already safe to print."""


# ---------------------------------------------------------------- secrets
def read_env() -> dict[str, str]:
    env: dict[str, str] = {}
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[7:]
            k, _, v = line.partition("=")
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
                v = v[1:-1]
            env[k.strip()] = v
    for v in env.values():
        if len(v) >= 6:
            _SECRETS.add(v)
        if "://" in v and "@" in v:
            userinfo = v.split("://", 1)[1].rsplit("@", 1)[0]
            user, _, pw = userinfo.partition(":")
            for x in (unquote(pw), pw, quote(unquote(pw), safe=""), unquote(user)):
                if len(x) >= 4:
                    _SECRETS.add(x)
            host = v.split("://", 1)[1].rsplit("@", 1)[1].split("/")[0].split(":")[0]
            if len(host) >= 6:
                _SECRETS.add(host)
    return env


def scrub(text: str) -> str:
    for s in sorted(_SECRETS, key=len, reverse=True):
        text = text.replace(s, "***")
    return text


def connect(url: str):
    import psycopg
    try:
        return psycopg.connect(url, connect_timeout=15, prepare_threshold=None)  # pooler-safe: no prepared statements
    except Exception as e:  # noqa: BLE001
        first = str(e).strip().splitlines()[0] if str(e).strip() else ""
        raise SiteDbError(f"cannot connect: {type(e).__name__}: {scrub(first)}") from None


def targets(choice: str) -> list[tuple[str, str]]:
    env = read_env()
    names = list(TARGETS) if choice == "all" else [choice]
    out = []
    for name in names:
        url = next((env[k] for k in TARGETS[name] if env.get(k)), None)
        if url:
            out.append((name, url))
        else:
            print(f"[{name}] skipped: no {' / '.join(TARGETS[name])} in .env")
    if not out:
        raise SiteDbError("no database configured in .env (see .env.example)")
    return out


# ---------------------------------------------------------------- yaml -> rows
def load(name: str):
    with open(DATA / f"{name}.yml", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or []


def as_list(x) -> list:
    return [] if x is None else list(x)


def build_rows() -> dict[str, list[dict]]:
    """Every table's rows, with temporary keys `_key` / `_parent` linking children to parents."""
    p, cv = load("profile"), load("cv")
    emp = cv.get("employer") or {}
    rows: dict[str, list[dict]] = {t: [] for t in TABLES}
    rows["profile"].append({k: p.get(k) for k in ("name", "headline", "affiliation", "institution", "location",
                                                     "email", "github", "linkedin", "ssrn_author", "cv_pdf",
                                                     "cv_updated", "portrait", "bio")}
                           | {"employer_name": emp.get("name"), "employer_note": emp.get("note")})
    rows["interests"] = [{"sort": i, "text": t} for i, t in enumerate(as_list(p.get("interests")))]
    rows["news"] = [{"sort": i, "date_label": str(n["date"]), "text": n["text"]} for i, n in enumerate(load("news"))]
    for i, w in enumerate(load("papers")):
        rows["papers"].append({"_key": w["slug"], "sort": i, "slug": w["slug"], "status": w["status"],
                               "title": w["title"], "coauthors": as_list(w.get("coauthors")), "year": w.get("year"),
                               "revised": w.get("revised"), "summary": w.get("summary")})
        rows["paper_links"] += [{"_parent": w["slug"], "sort": j, "label": l["label"], "url": l["url"]}
                                for j, l in enumerate(as_list(w.get("links")))]
    rows["projects"] = [{"sort": i, "slug": x["slug"], "name": x["name"], "years": str(x.get("years") or ""),
                         "role": x.get("role"), "description": x.get("description"),
                         "stack": as_list(x.get("stack")), "adopted": x.get("adopted") or None}
                        for i, x in enumerate(load("projects"))]
    for i, t in enumerate(load("teaching")):
        rows["teaching"].append({"_key": i, "sort": i, "org": t["org"], "role": t.get("role"), "years": str(t.get("years") or "")})
        rows["teaching_items"] += [{"_parent": i, "sort": j, "text": s} for j, s in enumerate(as_list(t.get("items")))]
    rows["education"] = [{"sort": i, "years": str(e.get("years") or ""), "degree": e["degree"], "school": e.get("school"),
                          "notes": as_list(e.get("notes"))} for i, e in enumerate(as_list(cv.get("education")))]
    for i, r in enumerate(as_list(cv.get("positions"))):
        rows["positions"].append({"_key": i, "sort": i, "kind": r["kind"], "years": str(r.get("years") or ""),
                                  "title": r["title"], "place": r.get("place")})
        rows["position_bullets"] += [{"_parent": i, "sort": j, "text": b} for j, b in enumerate(as_list(r.get("bullets")))]
    for section, key in (("award", "awards"), ("service", "service"), ("certification", "certifications")):
        rows["cv_entries"] += [{"section": section, "sort": i, "years": str(a.get("years") or ""), "text": a["text"]}
                               for i, a in enumerate(as_list(cv.get(key)))]
    rows["skills"] = [{"sort": i, "grp": s["group"], "items": s["items"]} for i, s in enumerate(as_list(cv.get("skills")))]
    return rows


PARENT = {"paper_links": ("papers", "paper_id"), "teaching_items": ("teaching", "teaching_id"),
          "position_bullets": ("positions", "position_id")}


def git_commit() -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
        return out.stdout.strip() or None
    except OSError:
        return None


# ---------------------------------------------------------------- commands
def cmd_migrate(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("create schema if not exists site")
        cur.execute("create table if not exists site.schema_migrations (version text primary key, "
                    "applied_at timestamptz not null default now())")
        cur.execute("select version from site.schema_migrations")
        done = {r[0] for r in cur.fetchall()}
    conn.commit()
    new = [f for f in sorted(MIGRATIONS.glob("*.sql")) if f.stem not in done]
    for f in new:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute(f.read_text(encoding="utf-8"))
            cur.execute("insert into site.schema_migrations (version) values (%s)", (f.stem,))
        print(f"  applied {f.name}")
    if not new:
        print("  up to date")


def cmd_sync(conn, rows: dict[str, list[dict]], dry_run: bool) -> None:
    counts = {t: len(rows[t]) for t in TABLES}
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("truncate " + ", ".join(f"site.{t}" for t in TABLES) + " restart identity cascade")
        ids: dict[str, dict] = {}
        for t in TABLES:
            for r in rows[t]:
                vals = {k: v for k, v in r.items() if not k.startswith("_")}
                if t in PARENT:
                    ptable, col = PARENT[t]
                    vals[col] = ids[ptable][r["_parent"]]
                cols = list(vals)
                sql = (f"insert into site.{t} ({', '.join(cols)}) values ({', '.join(['%s'] * len(cols))})"
                       + (" returning id" if "_key" in r and t != "profile" else ""))
                cur.execute(sql, [vals[c] for c in cols])
                if "_key" in r:
                    ids.setdefault(t, {})[r["_key"]] = cur.fetchone()[0]
        cur.execute("insert into site.sync_runs (git_commit, counts) values (%s, %s)",
                    (git_commit(), json.dumps(counts)))
        if dry_run:
            raise _Rollback()
    print("  " + ", ".join(f"{t} {n}" for t, n in counts.items() if n))


class _Rollback(Exception):
    pass


def cmd_check(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("select current_database(), current_user, split_part(version(), ' ', 2)")
        db, user, ver = cur.fetchone()
        print(f"  connected: database {db}, user {user}, Postgres {ver}")
        cur.execute("select to_regclass('site.schema_migrations') is not null")
        if not cur.fetchone()[0]:
            print("  schema site: not created yet (run migrate)")
            return
        cur.execute("select coalesce(max(version), '-') from site.schema_migrations")
        print(f"  schema version: {cur.fetchone()[0]}")
        counts = []
        for t in TABLES:
            cur.execute(f"select count(*) from site.{t}")
            counts.append(f"{t} {cur.fetchone()[0]}")
        print("  rows: " + ", ".join(counts))
        cur.execute("select synced_at, git_commit from site.sync_runs order by id desc limit 1")
        last = cur.fetchone()
        print(f"  last sync: {last[0]:%Y-%m-%d %H:%M} (commit {last[1] or '-'})" if last else "  last sync: never")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="./site db", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["migrate", "sync", "check"])
    ap.add_argument("--target", choices=["all", *TARGETS], default="all")
    ap.add_argument("--dry-run", action="store_true", help="sync: run everything, then roll back")
    a = ap.parse_args(argv)
    try:
        rows = build_rows() if a.command == "sync" else None
        failed = 0
        for name, url in targets(a.target):
            print(f"[{name}] {a.command}{' (dry run)' if a.dry_run else ''}")
            try:
                with connect(url) as conn:
                    if a.command == "migrate":
                        cmd_migrate(conn)
                    elif a.command == "sync":
                        try:
                            cmd_sync(conn, rows, a.dry_run)
                        except _Rollback:
                            print("  rolled back (dry run)")
                    else:
                        cmd_check(conn)
            except SiteDbError as e:
                print(f"  error: {e}")
                failed += 1
            except Exception as e:  # noqa: BLE001
                first = str(e).strip().splitlines()[0] if str(e).strip() else ""
                print(f"  error: {type(e).__name__}: {scrub(first)}")
                failed += 1
        return 1 if failed else 0
    except SiteDbError as e:
        print(f"error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
