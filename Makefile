.PHONY: test
test:
	uv run manage.py test --settings=giralibros.settings.test

run:
	uv run python manage.py runserver

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





