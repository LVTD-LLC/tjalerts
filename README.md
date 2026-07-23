# Tech Job Alerts

Tech Job Alerts is a Django application that turns developer job posts into a structured, searchable jobs database.

The app powers [jobs.lvtd.dev](https://jobs.lvtd.dev/). It imports job posts from Hacker News, Remote OK, and We Work Remotely, enriches them into structured records, and helps people and agents browse, filter, compare, and consume relevant jobs.

## What It Does

- Aggregates developer jobs from Hacker News Who is Hiring threads, Remote OK, and We Work Remotely.
- Uses OpenAI-backed extraction and embeddings to normalize job titles, technologies, company details, compensation, locations, remote policy, contact data, and application links.
- Provides keyword search, semantic intent search, technology filters, role filters, source filters, location filters, salary filters, work-mode filters, and recency filters.
- Exposes job data through a web UI, HTTP API, and a read-only MCP server, with CLI access on the product roadmap.
- Exposes public browsing pages for jobs, companies, technologies, titles, highest-paid roles, and blog content.
- Includes internal admin workflows for imports, vector backfills, salary extraction, and data cleanup.
- Ships with structured logging, Sentry, PostHog, Logfire, and Django Q workers for background jobs.

## Stack

- Python 3.13
- Django 5.2
- Django Ninja for API routes
- Django Filter for job filtering
- Django Q2 and Redis for background jobs
- Postgres with pgvector for embeddings and similarity search
- Hotwire Turbo, Stimulus, Bootstrap, Tailwind, and webpack for frontend assets
- Mailgun/Anymail, MailHog, MJML, Buttondown, Sentry, PostHog, Logfire, MinIO/S3, and Stripe CLI integrations
- Docker Compose for local services

## Project Layout

```text
hn_jobs/      Django project settings, URLs, middleware, observability, and shared helpers
jobs/         Job models, filters, views, import tasks, alert logic, and enrichment code
api/          Django Ninja API endpoints and schemas
mcp_server/   Read-only FastMCP tools backed by the shared jobs service layer
pages/        Marketing/static pages, support form, and admin panel views
users/        Custom user model, auth forms, account views, and signals
blog/         Blog models, views, URLs, and templates
frontend/     Stimulus controllers, styles, webpack config, and built asset manifest
templates/    Django templates for the public app, accounts, emails, and components
deployment/   Dockerfiles and production entrypoint scripts
docs/         Operational notes
```

## Local Development

The repo is set up to run through Docker Compose. You need Docker with Compose support.

Create a `.env` file in the project root before starting the app. The settings module reads several service tokens at import time, so define the variables even when you are using local placeholders.

```env
ENVIRONMENT=dev
DEBUG=True
SECRET_KEY=dev-secret-key
SITE_URL=http://localhost:8000

DATABASE_URL=postgres://tjalerts:tjalerts@db:5432/tjalerts
REDIS_URL=redis://:tjalerts@redis:6379/0
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,backend
CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000

AWS_S3_ENDPOINT_URL=http://minio:9000
AWS_ACCESS_KEY_ID=tjalerts
AWS_SECRET_ACCESS_KEY=tjalerts

OPENAI_API_KEY=replace-me
API_TOKEN=dev-api-token
BUTTONDOWN_API_TOKEN=dev-buttondown-token
MAILGUN_API_KEY=
MJML_SECRET=dev-mjml-secret
ADMIN_KEY=dev-admin-key

GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

SENTRY_DSN=
SENTRY_BROWSER_DSN=
POSTHOG_API_KEY=
LOGFIRE_TOKEN=

DJSTRIPE_WEBHOOK_SECRET=
STRIPE_TEST_SECRET_KEY=
WEBHOOK_UUID=dev
```

Then start the development stack:

```bash
make serve
```

This starts the local services and follows backend logs in the foreground. Use `docker compose down` when you want to stop the stack.

Useful local URLs:

- App: <http://localhost:8000>
- Webpack dev server: <http://localhost:9091>
- MailHog: <http://localhost:8025>
- MinIO console: <http://localhost:9001>

The backend container runs migrations before starting Django. The frontend container installs npm dependencies and runs the webpack dev server.

## Common Commands

```bash
make serve                  # Build and start the local Docker stack (follows backend logs)
make shell                  # Open a Django shell_plus session in the backend container
make manage createsuperuser # Run any Django management command
make migrate                # Run Django migrations
make makemigrations         # Create Django migrations
make test                   # Run the configured pytest command in Docker
make restart-worker         # Recreate the Django Q worker container
npm run build               # Build frontend assets for production
npm run watch               # Watch frontend assets without the dev server
```

The npm commands require Node on the host, or can be run from the Docker `frontend` service.

## Background Jobs And Imports

Background work runs through Django Q and Redis. The `workers` service starts `python manage.py qcluster`.

Main import/enrichment workflows live in `jobs/tasks.py`:

- Hacker News Who is Hiring import and extraction
- Remote OK API import
- We Work Remotely RSS import
- OpenAI job data extraction
- embedding generation and vector backfills
- salary extraction
- scheduled job imports and enrichment
- contact/email validation and reporting

Staff-only admin actions in the app enqueue several of these workflows from the admin panel and job routes.

## API

The API is served under `/api/`.

Common endpoints include:

- `GET /api/jobs`
- `GET /api/companies`
- `GET /api/technologies/search?query=django`
- `GET /api/technology/{id}`
- `GET /api/title/search?query=backend`
- `GET /api/title/{id}`
- `GET /api/posts/similar/{id}`

The jobs endpoint supports pagination and filtering by technologies and source:

```text
/api/jobs?technologies=Python,Django&source=Hacker%20News&page=1&page_size=20
```

Internal and admin-oriented routes are intentionally omitted from this public endpoint list.

## MCP

The read-only MCP server is served over streamable HTTP at `/mcp/`. It exposes:

- `search_jobs` for bounded text, technology, source, remote, and salary searches
- `get_job` for fetching one public job by UUID

Both tools call `jobs.services`, the transport-neutral query layer intended for reuse by
future API and CLI surfaces. The MCP app does not expose import, enrichment, admin, or
other mutation operations.

## Frontend

Frontend source lives in `frontend/src/` and is bundled by webpack into `frontend/build/`, which Django serves through `python-webpack-boilerplate` and WhiteNoise.

Stimulus controllers handle interaction patterns such as filters, search-and-select controls, loading states, textarea behavior, and similar-post interactions.

## Deployment

Production-oriented Dockerfiles and entrypoints live in `deployment/`.

- `deployment/Dockerfile.server` builds frontend assets, installs Python dependencies, and starts `deployment/entrypoint.sh -s`.
- `deployment/Dockerfile.workers` builds frontend assets, installs Python dependencies, and starts `deployment/entrypoint.sh -w`.
- `deployment/entrypoint.sh` selects server or worker mode. Server mode collects static files, runs migrations, and starts Gunicorn; worker mode starts Django Q.

See [docs/production-data-changes.md](docs/production-data-changes.md) for notes on keeping startup migrations schema-only and running large data work separately.

## Notes

- The app defaults to `hn_jobs.settings.local` when using `manage.py`.
- WSGI and ASGI default to `hn_jobs.settings.production`.
- The local Compose database uses a custom Postgres image with pgvector support.
- OpenAI-backed import and enrichment tasks need a real `OPENAI_API_KEY`.
- Optional integrations can be left blank for local browsing, but workflows that call those services will fail until real credentials are configured.
