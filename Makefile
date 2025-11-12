serve:
	docker compose up -d --build
	docker compose logs -f backend

shell:
	docker compose run --rm backend python ./manage.py shell_plus --ipython

manage:
	docker compose run --rm backend python ./manage.py $(filter-out $@,$(MAKECMDGOALS))

makemigrations:
	docker compose run --rm backend python ./manage.py makemigrations

migrate:
	docker compose run --rm backend python ./manage.py migrate

test:
	docker compose run --rm backend pytest

restart-worker:
	docker compose up -d workers --force-recreate

restart-stripe:
	docker compose up -d stripe --force-recreate

test-webhook:
	docker compose run --rm stripe trigger customer.subscription.created

stripe-sync:
	docker compose run --rm backend python ./manage.py djstripe_sync_models Product Price


prod-shell:
	./deployment/prod-shell.sh
