.PHONY: test run deploy collectstatic sql
django=uv run manage.py

test:
	$(django) test --settings=giralibros.settings.test

run:
	$(django) runserver



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


