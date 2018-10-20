# This Makefile requires the following commands to be available:
# * virtualenv
# * python2.7
# * docker
# * docker-compose

DEPS:=requirements.txt
DOCKER_COMPOSE=$(shell which docker-compose)

VENV=${HOME}/.bitdust/venv
PIP=${VENV}/bin/pip
CMD_FROM_VENV:=". ${VENV}/bin/activate; which"
TOX=$(shell "$(CMD_FROM_VENV)" "tox")
PYTHON=$(shell "$(CMD_FROM_VENV)" "python")
TOX_PY_LIST="$(shell $(TOX) -l | grep ^py | xargs | sed -e 's/ /,/g')"

.DEFAULT_GOAL := install

.PHONY: install

install:
	@echo "Building BitDust environment and installing requirements"
	python bitdust.py deploy

venv: install

compile:
	$(PYTHON) compile.py build_ext

tox: venv setup.py
	$(TOX)

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

test_tox/%: venv pyclean
	$(TOX) -e $(TOX_PY_LIST) -- $*

test_docker_test_1:
	make -C tests/e2e/ -j2 all
	make -C tests/e2e/ test_1
	docker-compose -p "namespace1" logs

test_docker_test_2:
	make -C tests/e2e/ -j2 all
	make -C tests/e2e/ test_2
	docker-compose -p "namespace2" logs

test: install
	$(PYTHON) -m unittest discover -s tests/ -v

test_raid: install
	$(PYTHON) -m unittest discover -p "test_raid.py" -v

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

fullclean:
	@rm -rfv ~/.bitdust/

link:
	@echo "#!/bin/bash" > ~/.bitdust/bitdust
	@echo "$(PYTHON) -u `pwd`/bitdust.py \"\$$@\"" >> ~/.bitdust/bitdust
	@chmod +x ~/.bitdust/bitdust
	@echo "created executable script in ${HOME}/.bitdust/bitdust"

smoketest:
	@for srv in `$(PYTHON) -c "import userid.known_servers; s=userid.known_servers.by_host(); print ' '.join(['{}:{}'.format(i, s[i][0]) for i in s])"`; do echo "\n$$srv"; curl -I --connect-timeout 10 $$srv 2>/dev/null | grep "HTTP"; done

smoketestdht:
	@for srv in `$(PYTHON) -c "import dht.known_nodes; s=dht.known_nodes.default_nodes(); print ' '.join(['{}:{}'.format(i[0], i[1]) for i in s])"`; do echo "\n$$srv"; rndudpport=`echo $$RANDOM % 10000 + 10000 | bc`; rm -rf /tmp/bitdust_dht_smoketest; ~/.bitdust/venv/bin/python dht/dht_service.py ping --dhtdb=/tmp/bitdust_dht_smoketest --udpport=$$rndudpport --seeds="$$srv"; done
