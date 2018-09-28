# This Makefile requires the following commands to be available:
# * virtualenv
# * python2.7
# * docker
# * docker-compose

DEPS:=requirements.txt
DOCKER_COMPOSE=$(shell which docker-compose)

VENV="${HOME}/.bitdust/venv"
PIP:="${VENV}/bin/pip"
CMD_FROM_VENV:=". ${VENV}/bin/activate; which"
TOX=$(shell "$(CMD_FROM_VENV)" "tox")
PYTHON=$(shell "$(CMD_FROM_VENV)" "python")
TOX_PY_LIST="$(shell $(TOX) -l | grep ^py | xargs | sed -e 's/ /,/g')"

.DEFAULT_GOAL := install

.PHONY: install

install: clean venv deploy
	@echo "Building BitDust environemt and installing requirements"

deploy:
	$(PYTHON) bitdust.py deploy

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

venv:
	@echo "Creating new virtual environment in ${VENV}"
	@virtualenv -p python2.7 ${VENV}
	@$(PIP) install -U "pip>=7.0" -q
	# @$(PIP) install -r $(DEPS)

test: clean tox

test_raid:
	@$(PYTHON) -m unittest -v tests.test_raid.Test.test_small_file

test_raid_slow:
	@$(PYTHON) -m unittest -v tests.test_raid.Test.test_big_file

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

fullclean:
	@rm -rfv ~/.bitdust/

link:
	@echo "#!/bin/bash" > ~/.bitdust/bitdust
	@echo "$(PYTHON) -u `pwd`/bitdust.py \"\$$@\"" >> ~/.bitdust/bitdust
	@chmod +x ~/.bitdust/bitdust
	@echo "created executable script in ${HOME}/.bitdust/bitdust"

smoketest:
	@for srv in `$(PYTHON) -c "import userid.known_servers; s=userid.known_servers.by_host(); print ' '.join(['{}:{}'.format(i, s[i][0]) for i in s])"`; do echo "\n$$srv"; curl -I --connect-timeout 2 $$srv 2>/dev/null | grep "HTTP"; done

smoketestdht:
	@for srv in `$(PYTHON) -c "import dht.known_nodes; s=dht.known_nodes.default_nodes(); print ' '.join(['{}:{}'.format(i[0], i[1]) for i in s])"`; do echo "\n$$srv"; rndudpport=`echo $$RANDOM % 10000 + 10000 | bc`; rm -rf /tmp/bitdust_dht_smoketest; ~/.bitdust/venv/bin/python dht/dht_service.py ping --dhtdb=/tmp/bitdust_dht_smoketest --udpport=$$rndudpport --seeds="$$srv"; done
