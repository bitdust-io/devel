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
#
# This Makefile requires the following commands to be available:
# * virtualenv
# * python3
# * docker
# * docker-compose

ifeq ($(PYTHON_VERSION),)
	PYTHON_VERSION=python3.9
endif

ifeq ($(REGRESSION_PY_VER),)
	REGRESSION_PY_VER=3.9
endif

REQUIREMENTS_TXT:=requirements.txt
REQUIREMENTS_TESTING_TXT:=requirements-testing.txt
VENV_HOME=${HOME}/.bitdust/venv
OS=$(shell lsb_release -si 2>/dev/null || uname)
PIP:="venv/bin/pip3"
PYTHON="venv/bin/python3"
PYTHON_HOME="${VENV_HOME}/bin/python"
DOCKER_COMPOSE=$(shell which docker-compose)
CMD_FROM_VENV:=". venv/bin/activate; which"
COVERAGE="venv/bin/coverage"

.DEFAULT_GOAL := venv

.PHONY: clean pyclean

pyclean:
	@find . -name '*.pyc' -exec rm -f {} +
	@find . -name '*.pyo' -exec rm -f {} +
	@find . -name __pycache__ -delete
	@find . -name .DS_Store -delete
	@rm -rf *.egg-info build
	@rm -rf coverage.xml .coverage

clean: pyclean
	@rm -rf venv

venv:
	@$(PYTHON_VERSION) -m venv venv
	@$(PIP) install --upgrade pip
	@$(PIP) install -r $(REQUIREMENTS_TXT)
	@$(PIP) install -r $(REQUIREMENTS_TESTING_TXT)

install:
	@echo "Building BitDust environment and installing requirements VENV_PYTHON_VERSION=$(VENV_PYTHON_VERSION)";
	@if [ "$(VENV_PYTHON_VERSION)" = "" ]; then\
		python3 bitdust.py install;\
	else\
		$(VENV_PYTHON_VERSION) bitdust.py install;\
	fi;

test_unit: venv
	PYTHONPATH=. $(COVERAGE) run --omit=*/site-packages/*,*CodernityDB*,*transport/http/* -m unittest discover -s tests/ -v

test: test_unit

setup.py: venv
	$(PYTHON) setup_gen.py
	$(PYTHON) setup.py check --restructuredtext

link:
	@echo "#!/bin/bash" > ~/.bitdust/bitdust
	@echo "$(PYTHON_HOME) -u `pwd`/bitdust.py \"\$$@\"" >> ~/.bitdust/bitdust
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

debug_on:
	@find ./bitdust -type f -name "*.py" -exec python3 -c 'import sys; inp=open(sys.argv[1]).read();outp=inp.replace("_Debug = False", "_Debug = True"); open(sys.argv[1],"w").write(outp); print(sys.argv[1], len(outp), "CHANGED" if inp != outp else "");' '{}' \;

debug_off:
	@find ./bitdust -type f -name "*.py" -exec python3 -c 'import sys; inp=open(sys.argv[1]).read();outp=inp.replace("_Debug = True", "_Debug = False"); open(sys.argv[1],"w").write(outp); print(sys.argv[1], len(outp), "CHANGED" if inp != outp else "");' '{}' \;

test_regress:
	$(MAKE) regress_clean_run_report

regress_stop:
	PYTHON_VERSION=$(REGRESSION_PY_VER) make --no-print-directory -C regress/ stop_all
	make --no-print-directory -C regress/ clean_all

regress_test:
	PYTHON_VERSION=$(REGRESSION_PY_VER) make --no-print-directory -C regress/ VERBOSE=1 test

regress_test_log:
	PYTHON_VERSION=$(REGRESSION_PY_VER) make --no-print-directory -C regress/ VERBOSE=3 test_log

regress_clean:
	make --no-print-directory -C regress/ clean_coverage
	make --no-print-directory -C regress/ clean_logs

regress_prepare:
	PYTHON_VERSION=$(REGRESSION_PY_VER) make --no-print-directory -C regress/ prepare

regress_run:
	PYTHON_VERSION=$(REGRESSION_PY_VER) _PAUSE_BEFORE=0 make --no-print-directory -C regress/ run_all

regress_run_parallel:
	PYTHON_VERSION=$(REGRESSION_PY_VER) _PAUSE_BEFORE=0 make --no-print-directory -j 2 -C regress/ run_parallel

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
	PYTHON_VERSION=$(REGRESSION_PY_VER) _DEBUG=0 _PAUSE_BEFORE=0 make --no-print-directory -C regress/ -j 4 run_parallel
	make --no-print-directory -C regress/ stop_all
	make --no-print-directory -C regress/ clean_all

regress_clean_run_log_py27:
	make --no-print-directory -C regress/ stop_all
	make --no-print-directory -C regress/ clean_all
	PYTHON_VERSION=2.7.15 make --no-print-directory -C regress/ prepare
	PYTHON_VERSION=2.7.15 _DEBUG=1 make --no-print-directory -C regress/ run_all_log

regress_one/%:
	make --no-print-directory -C regress/ stop_all
	make --no-print-directory -C regress/ clean_all
	PYTHON_VERSION=3.6 make --no-print-directory -C regress/ prepare
	PYTHON_VERSION=3.6 make --no-print-directory -C regress/ VERBOSE=3 TEST_NAME=$* _one_up_test_coverage_log

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
