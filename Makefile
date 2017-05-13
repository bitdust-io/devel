# This Makefile requires the following commands to be available:
# * virtualenv
# * python2.7
# * docker
# * docker-compose

DEPS:=requirements.txt
DOCKER_COMPOSE=$(shell which docker-compose)

PIP:="venv/bin/pip"
CMD_FROM_VENV:=". venv/bin/activate; which"
TOX=$(shell "$(CMD_FROM_VENV)" "tox")
PYTHON=$(shell "$(CMD_FROM_VENV)" "python")
TOX_PY_LIST="$(shell $(TOX) -l | grep ^py | xargs | sed -e 's/ /,/g')"

.PHONY: clean docsclean pyclean test lint isort docs docker setup.py

tox: venv setup.py
	$(TOX)

pyclean:
	@find . -name *.pyc -delete
	@rm -rfv *.egg-info build
	@rm -rfv coverage.xml .coverage

docsclean:
	@rm -frv docs/_build/

clean: pyclean docsclean
	@rm -rfv venv

venv:
	@virtualenv -p python2.7 venv
	@$(PIP) install -U "pip>=7.0" -q
	@$(PIP) install -r $(DEPS)

test: clean tox

test/%: venv pyclean
	$(TOX) -e $(TOX_PY_LIST) -- $*

lint: venv
	@$(TOX) -e lint
	@$(TOX) -e isort-check

isort: venv
	@$(TOX) -e isort-fix

docs: venv
	@$(TOX) -e docs

docker:
	$(DOCKER_COMPOSE) run --rm app bash

docker/%:
	$(DOCKER_COMPOSE) run --rm app make $*

setup.py: venv
	$(PYTHON) setup_gen.py
	@$(PYTHON) setup.py check --restructuredtext

bitdust_clean:
	@rm -rfv ~/.bitdust/

bitdust_install_usr_bin:
	@$(PYTHON) bitdust.py alias > /tmp/bitdust
	sudo mv /tmp/bitdust /usr/bin/
	sudo chmod +x /usr/bin/bitdust

bitdust_install_usr_local_bin:
	@$(PYTHON) bitdust.py alias > /tmp/bitdust
	sudo mv /tmp/bitdust /usr/local/bin/
	sudo chmod +x /usr/local/bin/bitdust
