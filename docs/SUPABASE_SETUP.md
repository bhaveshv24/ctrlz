# Supabase database setup

Vercel serves the existing frontend; Render runs the existing API. Supabase Postgres persists accounts, hashed sessions, throttling, project configurations, incidents, events, probes, and demo records. This integration retains CtrlZ's existing email login; it does not use Supabase Auth or Realtime.

## Render configuration after deploying this code

1. Supabase → Connect → Direct tab → **Session pooler** → **URI**. Copy the generated host and username exactly; use port 5432. No paid IPv4 add-on is needed.
2. Substitute your database password. Percent-encode reserved characters in the password. Never commit the URI, include it in screenshots, or set it in Vercel.
3. In Render → Environment, replace `DATABASE_URL` with that URI, beginning `postgresql://`. The backend selects the psycopg driver and enforces SSL for Supabase hosts.
4. Keep `DATA_DIR` and `IMPORT_ROOT` pointing to writable local directories. Keep existing CORS, NVIDIA settings and registration settings.
5. Configure both admin email/password pairs using `CTRLZ_ADMIN_1_EMAIL`, `CTRLZ_ADMIN_1_PASSWORD`, `CTRLZ_ADMIN_2_EMAIL`, `CTRLZ_ADMIN_2_PASSWORD`, and the optional seeded user using `CTRLZ_USER_EMAIL` / `CTRLZ_USER_PASSWORD`. Seed passwords must be at least 12 characters. They only apply when an email does not already exist.
6. Save and deploy. Tables are created automatically in private `ctrlz_accounts` and `ctrlz_workspace_*` schemas. Do not add these schemas to the Data API exposed schemas. RLS is enabled without browser policies: access stays behind Render's authenticated API.
7. Register a test user, save a disabled project, restart Render, then sign in again and confirm the project remains. Never call the migration complete until this production restart check succeeds.

## Existing SQLite data

Changing the URL does not copy old data. Before a redeploy wipes ephemeral files, stop writes and obtain a backup of `DATA_DIR` and the operator SQLite database from the running deployment. If those files are already lost, this migration cannot recover them. Do not seed/start the Postgres deployment until the copy is complete.

Run against an empty target, on a machine holding that backup, with the target URI privately configured as `DATABASE_URL`:

```sh
uv run --project backend python scripts/migrate_sqlite_postgres.py --data-dir /absolute/backup/data --operator-db /absolute/backup/ctrlz.db
```

The script copies password hashes, sessions, users and each workspace in one transaction, rejects nonempty targets, and retains the source files. Review row counts before switching production. Keep the backup until verified.

## Remaining file persistence

Postgres does not persist uploaded repositories, Git worktrees, repaired ZIP files or Chroma's local index. Those remain ephemeral on Render Free. Old incident history survives, but source-dependent repair retries and ZIP downloads may require reimport after a restart. Durable artifact storage is a separate implementation step; this database change does not claim to solve it.

## Local verification

Normal tests retain SQLite support. A disposable PostgreSQL instance is required for integration tests:

```sh
CTRLZ_TEST_POSTGRES_URL=postgresql://... uv run --project backend --extra test python -m pytest backend/tests/test_postgres.py -q
```

CI provisions a disposable PostgreSQL 17 service for these tests. Never run them against production: they create accounts and workspaces.
