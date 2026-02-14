.PHONY: test run deploy collectstatic sql shell
django=uv run manage.py

test:
	$(django) test --settings=giralibros.settings.test

run:
	$(django) runserver

shell:
	$(django) shell

BRANCH ?= main
deploy:
	ssh $(SSH) "cd /home/libros/giralibros/ &&\
		git fetch &&\
		git checkout $(BRANCH) &&\
		git pull origin $(BRANCH) --ff-only &&\
		sudo su libros -l -c \"cd ~/giralibros && uv sync && make collectstatic && uv run manage.py migrate\" &&\
		sudo systemctl restart gunicorn"

collectstatic:
	set -a && . /etc/giralibros/env && uv run python manage.py collectstatic --settings=giralibros.settings.production --noinput


sql:
	sqlite3 -cmd ".open db.sqlite3"


prod-db-pull:
	scp $(SSH):/home/libros/giralibros/db.sqlite3 db.sqlite3

prod-img-pull:
	rsync -avz $(SSH):/var/www/giralibros/media/ ./media/
