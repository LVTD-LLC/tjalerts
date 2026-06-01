#!/bin/sh

# Default to server command if no arguments provided
if [ $# -eq 0 ]; then
    echo "No arguments provided. Defaulting to running the server."
    server=true
else
    server=false
fi

# All commands before the conditional ones
export PROJECT_NAME=hn_jobs
export DJANGO_SETTINGS_MODULE="hn_jobs.settings.production"

while getopts ":sw" option; do
    case "${option}" in
        s)  # Run server
            server=true
            ;;
        w)  # Run worker
            server=false
            ;;
        *)  # Invalid option
            echo "Invalid option: -$OPTARG" >&2
            ;;
    esac
done
shift $((OPTIND - 1))

# If no valid option provided, default to server
if [ "$server" = true ]; then
    python manage.py collectstatic --noinput
    # Startup migrations keep simple deploys convenient, but the web process
    # cannot serve traffic until this command exits. Keep migrations here
    # schema-only and fast. Run large data backfills as separate one-off
    # management commands or worker jobs before/after deploy; see
    # docs/production-data-changes.md.
    if [ "${RUN_MIGRATIONS_ON_STARTUP:-true}" != "false" ]; then
        python manage.py migrate
    else
        echo "Skipping startup migrations because RUN_MIGRATIONS_ON_STARTUP=$RUN_MIGRATIONS_ON_STARTUP"
        python manage.py migrate --check || {
            echo "ERROR: Pending migrations detected. Run migrations before starting the server." >&2
            exit 1
        }
    fi
    # python manage.py djstripe_sync_models
    gunicorn ${PROJECT_NAME}.wsgi:application --bind 0.0.0.0:80 --workers 3 --threads 2 --reload
else
    python manage.py qcluster
fi
