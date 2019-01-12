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
PIP_NEW=venv/bin/pip
PYTHON_VERSION=python2.7
CMD_FROM_VENV:=". ${VENV}/bin/activate; which"
TOX=$(shell "$(CMD_FROM_VENV)" "tox")
PYTHON=$(shell "$(CMD_FROM_VENV)" "python")
PYTHON_NEW="venv/bin/python"
TOX_PY_LIST="$(shell $(TOX) -l | grep ^py | xargs | sed -e 's/ /,/g')"

REQUIREMENTS_TEST:=requirements/requirements-testing.txt
REQUIREMENTS_TXT:=requirements.txt

VENV_BASE=venv/.venv_base
VENV_TEST=venv/.venv_test
VENV_DIR=venv/.venv_dir


.DEFAULT_GOAL := install

.PHONY: install

install:
	@echo "Building BitDust environment and installing requirements"
	python bitdust.py deploy

venv_install: install

compile:
	$(PYTHON) compile.py build_ext

tox: venv_install setup.py
	$(TOX)

venv: $(VENV_BASE)

$(VENV_DIR):
	@rm -rf venv
	@virtualenv -p $(PYTHON_VERSION) venv
	@touch $@

$(VENV_BASE): $(VENV_DIR) $(REQUIREMENTS_TXT)
	@$(PIP_NEW) install -r $(REQUIREMENTS_TXT)
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
	@echo "Cleanup current BitDust environemt"
	@rm -rf ${VENV}

venv_off:
	@echo "Creating new virtual environment in ${VENV}"
	@virtualenv -p python2.7 ${VENV}
	@$(PIP) install -U "pip>=7.0" -q
	@$(PIP) install -r $(DEPS)

test_tox: clean tox

test_tox/%: venv_install pyclean
	$(TOX) -e $(TOX_PY_LIST) -- $*

test_docker:
	make -C tests/e2e/ -j2 test

test_docker_1:
	make -C tests/e2e/ -j2 test_1
	docker-compose -p "namespace1" logs

test_docker_2:
	make -C tests/e2e/ -j2 test_2
	docker-compose -p "namespace2" logs

test: $(VENV_TEST)
	$(PYTHON_NEW) -m unittest discover -s tests/ -v

test_raid: $(VENV_TEST)
	$(PYTHON_NEW) -m unittest discover -p "test_raid.py" -v
	$(PYTHON_NEW) -m unittest discover -p "test_raid_worker.py" -v

test_regression:
	make -C regression/ test

regression_test:
	make -C regression/ test

regression_rerun:
	make -C regression/ test_all

regression_clean:
	make -C regression/ clean

regression_logs_all:
    # TODO: keep up to date with docker-compose links
	@echo "### [identity-server] #########################################################################"
	docker-compose -f regression/docker-compose.yml exec identity-server cat /root/.bitdust/logs/main.log
	@echo "### [dht_seed1] ##################################################################################"
	docker-compose -f regression/docker-compose.yml exec dht_seed_1 cat /root/.bitdust/logs/main.log
	@echo "### [dht_seed2] ##################################################################################"
	docker-compose -f regression/docker-compose.yml exec dht_seed_2 cat /root/.bitdust/logs/main.log
	@echo "### [stun_1] ##################################################################################"
	docker-compose -f regression/docker-compose.yml exec stun_1 cat /root/.bitdust/logs/main.log
	@echo "### [stun_2] ##################################################################################"
	docker-compose -f regression/docker-compose.yml exec stun_2 cat /root/.bitdust/logs/main.log
	@echo "### [proxy_server_1] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec proxy_server_1 cat /root/.bitdust/logs/main.log
	@echo "### [proxy_server_2] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec proxy_server_2 cat /root/.bitdust/logs/main.log
	@echo "### [supplier_1] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec supplier_1 cat /root/.bitdust/logs/main.log
	@echo "### [supplier_2] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec supplier_2 cat /root/.bitdust/logs/main.log
	@echo "### [supplier_3] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec supplier_3 cat /root/.bitdust/logs/main.log
	@echo "### [supplier_4] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec supplier_4 cat /root/.bitdust/logs/main.log
	@echo "### [supplier_5] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec supplier_5 cat /root/.bitdust/logs/main.log
	@echo "### [supplier_6] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec supplier_6 cat /root/.bitdust/logs/main.log
	@echo "### [supplier_7] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec supplier_7 cat /root/.bitdust/logs/main.log
	@echo "### [supplier_8] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec supplier_8 cat /root/.bitdust/logs/main.log
	@echo "### [customer_1] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec customer_1 cat /root/.bitdust/logs/main.log
	@echo "### [customer_2] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec customer_2 cat /root/.bitdust/logs/main.log
	@echo "### [customer_3] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec customer_3 cat /root/.bitdust/logs/main.log
	@echo "### [customer_4] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec customer_4 cat /root/.bitdust/logs/main.log

regression_logs_all_states:
    # TODO: keep up to date with docker-compose links
	@echo "### [identity-server] #########################################################################"
	docker-compose -f regression/docker-compose.yml exec identity-server cat /root/.bitdust/logs/main.log
	@echo "### [dht_seed1] ##################################################################################"
	docker-compose -f regression/docker-compose.yml exec dht_seed_1 cat /root/.bitdust/logs/main.log
	@echo "### [dht_seed2] ##################################################################################"
	docker-compose -f regression/docker-compose.yml exec dht_seed_2 cat /root/.bitdust/logs/main.log
	@echo "### [stun_1] ##################################################################################"
	docker-compose -f regression/docker-compose.yml exec stun_1 cat /root/.bitdust/logs/main.log
	@echo "### [stun_2] ##################################################################################"
	docker-compose -f regression/docker-compose.yml exec stun_2 cat /root/.bitdust/logs/main.log
	@echo "### [proxy_server_1] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec proxy_server_1 cat /root/.bitdust/logs/main.log
	@echo "### [proxy_server_2] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec proxy_server_2 cat /root/.bitdust/logs/main.log
	@echo "### [supplier_1] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec supplier_1 cat /root/.bitdust/logs/main.log
	@echo "### [supplier_2] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec supplier_2 cat /root/.bitdust/logs/main.log
	@echo "### [supplier_3] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec supplier_3 cat /root/.bitdust/logs/main.log
	@echo "### [supplier_4] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec supplier_4 cat /root/.bitdust/logs/main.log
	@echo "### [supplier_5] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec supplier_5 cat /root/.bitdust/logs/main.log
	@echo "### [supplier_6] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec supplier_6 cat /root/.bitdust/logs/main.log
	@echo "### [supplier_7] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec supplier_7 cat /root/.bitdust/logs/main.log
	@echo "### [supplier_8] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec supplier_8 cat /root/.bitdust/logs/main.log
	@echo "### [customer_1] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec customer_1 cat /root/.bitdust/logs/main.log
	@echo "### [customer_2] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec customer_2 cat /root/.bitdust/logs/main.log
	@echo "### [customer_3] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec customer_3 cat /root/.bitdust/logs/main.log
	@echo "### [customer_4] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec customer_4 cat /root/.bitdust/logs/main.log

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
	$(PYTHON) setup_gen.py
	@$(PYTHON) setup.py check --restructuredtext

fullclean:
	@rm -rfv ~/.bitdust/

link:
	@echo "#!/bin/bash" > ~/.bitdust/bitdust
	@echo "$(PYTHON) -u `pwd`/bitdust.py \"\$$@\"" >> ~/.bitdust/bitdust
	@chmod +x ~/.bitdust/bitdust
	@echo "created executable script in ${HOME}/.bitdust/bitdust"

smoketest:
	@for srv in `$(PYTHON) -c "import userid.known_servers; s=userid.known_servers.by_host(); print(' '.join(['{}:{}'.format(i, s[i][0]) for i in s]))"`; do echo "\n$$srv"; curl -I --connect-timeout 10 $$srv 2>/dev/null | grep "HTTP"; done

smoketestdht:
	@for srv in `$(PYTHON) -c "import dht.known_nodes; s=dht.known_nodes.default_nodes(); print(' '.join(['{}:{}'.format(i[0], i[1]) for i in s]))"`; do echo "\n$$srv"; rndudpport=`echo $$RANDOM % 10000 + 10000 | bc`; rm -rf /tmp/bitdust_dht_smoketest; ~/.bitdust/venv/bin/python dht/dht_service.py ping --dhtdb=/tmp/bitdust_dht_smoketest --udpport=$$rndudpport --seeds="$$srv"; done
