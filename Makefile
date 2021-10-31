#
# Makefile
#
# Copyright (C) 2008 Veselin Penev  https://bitdust.io
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
# * python3
# * docker
# * docker-compose


DEPS:=requirements.txt
DOCKER_COMPOSE=$(shell which docker-compose)

VENV=${HOME}/.bitdust/venv
PIP=${VENV}/bin/pip
PIP_NEW=${VENV}/bin/pip
REGRESSION_PY_VER=3.6
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
	@echo "Building BitDust environment and installing requirements VENV_PYTHON_VERSION=$(VENV_PYTHON_VERSION)";
	@if [ "$(VENV_PYTHON_VERSION)" = "" ]; then\
		python3 bitdust.py install;\
	else\
		$(VENV_PYTHON_VERSION) bitdust.py install;\
	fi;

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
	PYTHONPATH=. $(COVERAGE_NEW) run --omit=*/site-packages/*,*CodernityDB*,*transport/http/* -m unittest discover -s tests/ -v

test_raid: $(VENV_TEST)
	$(PYTHON_NEW) -m unittest tests.test_raid_worker

test_regress:
	$(MAKE) regress_clean_run_report



regress_stop:
	PYTHON_VERSION=$(REGRESSION_PY_VER) make --no-print-directory -C regress/ stop_all
	make --no-print-directory -C regress/ clean_all

regress_test:
	PYTHON_VERSION=$(REGRESSION_PY_VER) make --no-print-directory -C regress/ VERBOSE=1 test

regress_test_log:
	PYTHON_VERSION=$(REGRESSION_PY_VER) make --no-print-directory -C regress/ test_log

regress_clean:
	make --no-print-directory -C regress/ clean_coverage
	make --no-print-directory -C regress/ clean_logs

regress_prepare:
	PYTHON_VERSION=$(REGRESSION_PY_VER) make --no-print-directory -C regress/ prepare

regress_run:
	PYTHON_VERSION=$(REGRESSION_PY_VER) _PAUSE_BEFORE=0 make --no-print-directory -C regress/ run_all

regress_run_parallel:
	PYTHON_VERSION=$(REGRESSION_PY_VER) _PAUSE_BEFORE=0 make --no-print-directory -j 3 -C regress/ run_parallel

regress_run_log:
	PYTHON_VERSION=$(REGRESSION_PY_VER) make --no-print-directory -C regress/ run_all_log

regress_run_one/%:
	make --no-print-directory -C regress/ clean_coverage
	make --no-print-directory -C regress/ clean_logs
	PYTHON_VERSION=$(REGRESSION_PY_VER) make --no-print-directory -C regress/ TEST_NAME=$* _one_up_test_coverage_down

regress_run_try_one/%:
	make --no-print-directory -C regress/ clean_coverage
	make --no-print-directory -C regress/ clean_logs
	PYTHON_VERSION=$(REGRESSION_PY_VER) make --no-print-directory -C regress/ TEST_NAME=$* _one_up_test_log

regress_run_log_one/%:
	make --no-print-directory -C regress/ clean_coverage
	make --no-print-directory -C regress/ clean_logs
	PYTHON_VERSION=$(REGRESSION_PY_VER) make --no-print-directory -C regress/ TEST_NAME=$* _one_up_test_log_down

regress_report:
	PYTHON_VERSION=$(REGRESSION_PY_VER) make --no-print-directory -C regress/ report

regress_clean_run_report:
	make --no-print-directory -C regress/ stop_all
	make --no-print-directory -C regress/ clean_all
	PYTHON_VERSION=$(REGRESSION_PY_VER) make --no-print-directory -C regress/ prepare
	PYTHON_VERSION=$(REGRESSION_PY_VER) _DEBUG=1 _PAUSE_BEFORE=0 make --no-print-directory -C regress/ -j 1 run_parallel

regress_clean_run_log_py27:
	make --no-print-directory -C regress/ stop_all
	make --no-print-directory -C regress/ clean_all
	PYTHON_VERSION=2.7.15 make --no-print-directory -C regress/ prepare
	PYTHON_VERSION=2.7.15 _DEBUG=1 make --no-print-directory -C regress/ run_all_log

regress_one/%:
	make --no-print-directory -C regress/ stop_all
	make --no-print-directory -C regress/ clean_all
	# make --no-print-directory -C regress/ clean_coverage
	# make --no-print-directory -C regress/ clean_logs
	PYTHON_VERSION=3.6 make --no-print-directory -C regress/ prepare
	PYTHON_VERSION=3.6 make --no-print-directory -C regress/ VERBOSE=${VERBOSE} TEST_NAME=$* _one_up_test_coverage_log



dht_network_up:
	docker-compose -f tests/dht/docker-compose.yml up --force-recreate --build

dht_network_run_producer:
	docker-compose -f tests/dht/docker-compose.yml exec dht_producer bash -c "/root/.bitdust/venv/bin/python /app/bitdust/tests/dht/test_producer.py 1 5"

dht_network_run_producer/%:
	docker-compose -f tests/dht/docker-compose.yml exec dht_producer bash -c "/root/.bitdust/venv/bin/python /app/bitdust/tests/dht/test_producer.py 1 $*"

dht_network_run_consumer:
	docker-compose -f tests/dht/docker-compose.yml exec dht_consumer bash -c "/root/.bitdust/venv/bin/python /app/bitdust/tests/dht/test_consumer.py 1 5"

dht_network_run_consumer/%:
	docker-compose -f tests/dht/docker-compose.yml exec dht_consumer bash -c "/root/.bitdust/venv/bin/python /app/bitdust/tests/dht/test_consumer.py 1 $*"

dht_network_ssh_base:
	docker-compose -f tests/dht/docker-compose.yml exec dht_base bash

dht_network_ssh_seed_1:
	docker-compose -f tests/dht/docker-compose.yml exec dht_seed_1 bash

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

no_debug:
	@if [ "$(OSTYPE)" = "darwin" ]; then\
		find . -type f -name "*.py" -exec sed -i '' -e 's/_Debug = True/_Debug = False/g' {} +;\
	else\
		find . -type f -name "*.py" -exec sed -i -e 's/_Debug = True/_Debug = False/g' {} +;\
	fi;
	@echo 'all ".py" local files were updated with "_Debug = False"'
