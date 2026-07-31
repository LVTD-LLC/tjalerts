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

test-cli:
	go test ./...

restart-worker:
	docker compose up -d workers --force-recreate

prod-shell:
	./deployment/prod-shell.sh
