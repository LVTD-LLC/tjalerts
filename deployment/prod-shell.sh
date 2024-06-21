ssh -t root@138.201.126.181 'docker exec -it $(docker ps --filter "name=srv-captain--hnjobs" | grep "^.*srv-captain--hnjobs\." | awk '\''{print $1}'\'') python manage.py shell_plus --ipython'
