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

regression_logs:
    # TODO: keep up to date with docker-compose links
	@echo "### [identity-server] #########################################################################"
	docker-compose -f regression/docker-compose.yml exec identity-server cat /root/.bitdust/logs/main.log
	@echo "### [stun_1] ##################################################################################"
	docker-compose -f regression/docker-compose.yml exec stun_1 cat /root/.bitdust/logs/main.log
	@echo "### [stun_2] ##################################################################################"
	docker-compose -f regression/docker-compose.yml exec stun_2 cat /root/.bitdust/logs/main.log
	@echo "### [supplier_1] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec supplier_1 cat /root/.bitdust/logs/main.log
	@echo "### [supplier_2] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec supplier_2 cat /root/.bitdust/logs/main.log
	@echo "### [customer_1] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec customer_1 cat /root/.bitdust/logs/main.log
	@echo "### [customer_2] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec customer_2 cat /root/.bitdust/logs/main.log
	@echo "### [customer_3] ##############################################################################"
	docker-compose -f regression/docker-compose.yml exec customer_3 cat /root/.bitdust/logs/main.log

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
