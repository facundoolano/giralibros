.PHONY: test
test:
	uv run manage.py test --settings=giralibros.settings.test

run:
	uv run python manage.py runserver

# FIXME also need to collect static with --settings=giralibros.settings.test and proper env to get SECRET_KEY
BRANCH ?= main
deploy:
	ssh $(SSH) "cd /home/libros/giralibros/ &&\
		git fetch &&\
		git checkout $(BRANCH) &&\
		git pull origin $(BRANCH) --ff-only &&\
		sudo -u libros bash -c \"cd ~/giralibros && uv sync && make collectstatic\" &&\
		sudo systemctl restart gunicorn"

collectstatic:
	set -a && source /etc/giralibros/env && uv run python manage.py collectstatic --settings=giralibros.settings.production --noinput





