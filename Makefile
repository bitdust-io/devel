#
# Makefile
#
# Copyright (C) 2008-2018 Veselin Penev  https://bitdust.io
#
# This file (Makefile) is part of BitDust Software.
#
# BitDust is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BitDust Software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with BitDust Software.  If not, see <http://www.gnu.org/licenses/>.
#
# Please contact us if you have any questions at bitdust.io@gmail.com


# This Makefile requires the following commands to be available:
# * virtualenv
# * python2.7
# * docker
# * docker-compose

DEPS:=requirements.txt
DOCKER_COMPOSE=$(shell which docker-compose)

VENV=${HOME}/.bitdust/venv
PIP=${VENV}/bin/pip
PIP_NEW=${VENV}/bin/pip
# REGRESSION_PY_VER=3.6
# VENV_PYTHON_VERSION=python3.6
CMD_FROM_VENV:=". ${VENV}/bin/activate; which"
TOX=$(shell "$(CMD_FROM_VENV)" "tox")
PYTHON=$(shell "$(CMD_FROM_VENV)" "python")
PYTHON_NEW="${VENV}/bin/python"
COVERAGE_NEW="${VENV}/bin/coverage"
TOX_PY_LIST="$(shell $(TOX) -l | grep ^py | xargs | sed -e 's/ /,/g')"

REQUIREMENTS_TEST:=requirements/requirements-testing.txt
REQUIREMENTS_TXT:=requirements.txt

VENV_BASE=${VENV}/.venv_base
VENV_TEST=${VENV}/.venv_test


.DEFAULT_GOAL := install

.PHONY: install

install:
	@echo "Building BitDust environment and installing requirements";
	@if [ "$(VENV_PYTHON_VERSION)" = "python2.7" ]; then python bitdust.py install; else python3 bitdust.py install; fi;

venv_install: install

compile:
	$(PYTHON) compile.py build_ext

tox: venv_install setup.py
	$(TOX)

venv: $(VENV_BASE)

$(VENV_BASE): install
	@touch $@

$(VENV_TEST): $(VENV_BASE) $(REQUIREMENTS_TEST)
	@$(PIP_NEW) install -r $(REQUIREMENTS_TEST)
	@touch $@

pyclean:
	@find . -name *.pyc -delete
	@rm -rfv *.egg-info build
	@rm -rfv coverage.xml .coverage

docsclean:
	@rm -fr docs/_build/

clean: pyclean docsclean
	@echo "Cleanup current BitDust environment"
	@rm -rf ${VENV}

venv_off:
	@echo "Creating new virtual environment in ${VENV}"
	@virtualenv -p python2.7 ${VENV}
	@$(PIP) install -U "pip>=7.0" -q
	@$(PIP) install -r $(DEPS)

test_tox: clean tox

test_tox/%: venv_install pyclean
	$(TOX) -e $(TOX_PY_LIST) -- $*

test_unit: $(VENV_TEST)
	PYTHONPATH=. $(COVERAGE_NEW) run --omit=*/site-packages/* -m unittest discover -s tests/ -v

test_raid: $(VENV_TEST)
	$(PYTHON_NEW) -m unittest tests.test_raid_worker

test_regression:
	PYTHON_VERSION=$(REGRESSION_PY_VER) make -C regression/ test

regression_test:
	PYTHON_VERSION=$(REGRESSION_PY_VER) make -C regression/ test

regress_test:
	PYTHON_VERSION=$(REGRESSION_PY_VER) make -C regress/ test

regress_test_log:
	PYTHON_VERSION=$(REGRESSION_PY_VER) make -C regress/ test_log

regression_build:
	PYTHON_VERSION=$(REGRESSION_PY_VER) make -C regression/ build

regression_run:
	PYTHON_VERSION=$(REGRESSION_PY_VER) make -C regression/ run

regression_prepare:
	PYTHON_VERSION=$(REGRESSION_PY_VER) make -C regression/ prepare

regression_try:
	PYTHON_VERSION=$(REGRESSION_PY_VER) make -C regression/ try

regression_test_one/%:
	PYTHON_VERSION=$(REGRESSION_PY_VER) make -C regression/ test_one/$*

regression_try_one/%:
	PYTHON_VERSION=$(REGRESSION_PY_VER) make -C regression/ try_one/$*

regression_clean:
	PYTHON_VERSION=$(REGRESSION_PY_VER) make -C regression/ clean

regression_clean_orphans:
	PYTHON_VERSION=$(REGRESSION_PY_VER) make -C regression/ clean_orphans

regression_clean_unused:
	PYTHON_VERSION=$(REGRESSION_PY_VER) make -C regression/ clean_unused_images

regression_log_one/%:
	@echo "### [identity-server] #########################################################################"
	docker-compose -f regression/docker-compose.yml exec $* cat /root/.bitdust/logs/stdout.log

regression_states_one/%:
	@echo "### [identity-server] #########################################################################"
	docker-compose -f regression/docker-compose.yml exec $* cat /root/.bitdust/logs/automats.log

regression_logs_all:
	make -C regression/ logs_all_stdout

regression_errors_all:
	make -C regression/ logs_all_stderr

regression_states_all:
	make -C regression/ logs_all_states

regression_events_all:
	make -C regression/ logs_all_events

regression_exceptions_all:
	@make -C regression/ logs_all_exceptions

regression_logs_fetch:
	make -C regression/ logs_fetch

dht_network_up:
	docker-compose -f tests/dht/docker-compose.yml up --force-recreate --build

dht_network_run_producer:
	docker-compose -f tests/dht/docker-compose.yml exec dht_producer bash -c "/root/.bitdust/venv/bin/python /bitdust/tests/dht/test_producer.py 1 5"

dht_network_run_producer/%:
	docker-compose -f tests/dht/docker-compose.yml exec dht_producer bash -c "/root/.bitdust/venv/bin/python /bitdust/tests/dht/test_producer.py 1 $*"

dht_network_run_consumer:
	docker-compose -f tests/dht/docker-compose.yml exec dht_consumer bash -c "/root/.bitdust/venv/bin/python /bitdust/tests/dht/test_consumer.py 1 5"

dht_network_run_consumer/%:
	docker-compose -f tests/dht/docker-compose.yml exec dht_consumer bash -c "/root/.bitdust/venv/bin/python /bitdust/tests/dht/test_consumer.py 1 $*"

dht_network_ssh_producer:
	docker-compose -f tests/dht/docker-compose.yml exec dht_producer bash

dht_network_ssh_consumer:
	docker-compose -f tests/dht/docker-compose.yml exec dht_consumer bash


lint: venv_install
	@$(TOX) -e lint
	@$(TOX) -e isort-check

isort: venv_install
	@$(TOX) -e isort-fix

docs: venv_install
	@$(TOX) -e docs

docker:
	$(DOCKER_COMPOSE) run --rm app bash

docker/%:
	$(DOCKER_COMPOSE) run --rm app make $*

setup.py: venv_install
	$(PYTHON_NEW) setup_gen.py
	@$(PYTHON_NEW) setup.py check --restructuredtext

fullclean:
	@rm -rfv ~/.bitdust/

link:
	@echo "#!/bin/bash" > ~/.bitdust/bitdust
	@echo "$(PYTHON) -u `pwd`/bitdust.py \"\$$@\"" >> ~/.bitdust/bitdust
	@chmod +x ~/.bitdust/bitdust
	@echo "created executable script in ${HOME}/.bitdust/bitdust"

health_id_servers:
	@./scripts/ping_id_servers
