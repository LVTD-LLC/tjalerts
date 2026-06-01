# Production Data Changes

Do not put long-running data rewrites in Django migrations.

The web container runs `python manage.py migrate` before Gunicorn starts. If a
migration spends minutes backfilling rows, production can return 502s while the
new web process waits for that migration to finish.

Prefer this flow for production-scale data changes:

1. Ship a schema-only migration that is fast and backward-compatible. Add new
   columns as nullable or with application-level defaults when possible.
2. Deploy code that can read both the old and new shape.
3. Run the data rewrite separately as an idempotent management command, Django
   Q2 task, or one-off production shell snippet. Process rows in bounded
   batches and log progress.
4. After the backfill completes, ship a follow-up migration for constraints,
   required fields, and indexes. On PostgreSQL, create large indexes
   concurrently when possible.

Use `RUN_MIGRATIONS_ON_STARTUP=false` only when migrations are being run by a
separate release step or manually before the web process starts. Any other value
runs startup migrations. Do not disable startup migrations without a replacement
path, or new code may boot against an old schema. The entrypoint still runs
`python manage.py migrate --check` in this mode so the web process fails fast if
unapplied migrations remain.
