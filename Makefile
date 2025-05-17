redis:
	redis-stack-server --port 6381

shell:
	poetry run python manage.py shell_plus --ipython

prod-shell:
	./deployment/prod-shell.sh
