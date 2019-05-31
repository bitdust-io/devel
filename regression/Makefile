#
# Makefile
#
# Copyright (C) 2008-2018 Stanislav Evseev, Veselin Penev  https://bitdust.io
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

BUILD=.build
RUN_ALL=.run_all
# PYTHON_VERSION=2.7.15

.PHONY: test

clean: clean_all

clean_build:
	@echo "running on $(PYTHON_VERSION)"
	@rm -f $(BUILD)

test: clean_build clean $(BUILD) $(RUN_ALL) test_all

run: clean_build clean $(BUILD) $(RUN_ALL)

prepare: clean_build clean $(BUILD) $(RUN_ALL) prepare_all

try: try_all

$(BUILD):
	docker-compose build --build-arg PYTHON_VERSION=$(PYTHON_VERSION)
	@touch $@

$(RUN_ALL): $(BUILD)
	$(MAKE) _run_all
	@touch $@

build:
	docker-compose up -d --build --force-recreate --remove-orphans

test_all: $(RUN_ALL)
	$(MAKE) COMMAND="python -u -m pytest /app/tests/ -v -s" _test

try_all: $(RUN_ALL)
	$(MAKE) COMMAND="python -u -m pytest /app/tests/ -v -s" _try

prepare_all: $(RUN_ALL)
	$(MAKE) COMMAND="python -u -m pytest /app/tests/ -v -s" _prepare

test_one/%: $(RUN_ALL)
	$(MAKE) COMMAND="python -u -m pytest /app/$* -v -s" _test

try_one/%: $(RUN_ALL)
	$(MAKE) COMMAND="python -u -m pytest /app/$* -v -s" _try

clean_all:
	$(MAKE) _clean_all
	@rm -f $(RUN_ALL)

_test:
	docker-compose exec tester sh -c "${COMMAND}"

_try:
	docker-compose exec tester sh -c "OPEN_TUNNELS=1 STOP_NODES=0 CLEAN_NODES=0 START_NODES=0 ${COMMAND}"

_prepare:
	docker-compose exec tester sh -c "RUN_TESTS=0 ${COMMAND}"

_clean_all:
	docker-compose down -v -t 1

clean_orphans:
	docker-compose down -v -t 1 --remove-orphans

_run_all:
	docker-compose up -d

clean_unused_images:
	# docker images | grep '<none>' | awk '{ print $3 }' | xargs docker rmi --force
	docker images -aq -f 'dangling=true' | xargs docker rmi

logs_fetch:
	@rm -rf .logs
	@mkdir .logs
	@for node in "identity-server" "identity-server-a" "identity-server-b" "stun_1" "stun_2" "dht_seed_0" "dht_seed_1" "dht_seed_2" "dht_seed_3" "dht_seed_4" "supplier_1" "proxy_server_1" "proxy_server_2" "supplier_2" "supplier_3" "supplier_4" "supplier_5" "supplier_6" "supplier_7" "supplier_8" "customer_1" "customer_2" "customer_3" "customer_4" "customer_5" "customer_backup" "customer_restore"; do docker-compose exec $$node sh -c "cat /root/.bitdust/logs/automats.log" > .logs/$$node.automats.log; docker-compose exec $$node sh -c "cat /root/.bitdust/logs/event.log" > .logs/$$node.event.log; docker-compose exec $$node sh -c "cat /root/.bitdust/logs/packet.log" > .logs/$$node.packet.log; docker-compose exec $$node sh -c "cat /root/.bitdust/logs/stdout.log" > .logs/$$node.stdout.log; echo $$node; done

logs_all_stdout:
    # TODO: keep up to date with docker-compose links
	@for node in "identity-server" "identity-server-a" "identity-server-b" "stun_1" "stun_2" "dht_seed_0" "dht_seed_1" "dht_seed_2" "dht_seed_3" "dht_seed_4" "supplier_1" "proxy_server_1" "proxy_server_2" "supplier_2" "supplier_3" "supplier_4" "supplier_5" "supplier_6" "supplier_7" "supplier_8" "customer_1" "customer_2" "customer_3" "customer_4" "customer_5" "customer_backup" "customer_restore"; do echo "[$$node] ==================================="; docker-compose exec $$node cat /root/.bitdust/logs/stdout.log; done

logs_all_stderr:
    # TODO: keep up to date with docker-compose links
	@for node in "identity-server" "identity-server-a" "identity-server-b" "stun_1" "stun_2" "dht_seed_0" "dht_seed_1" "dht_seed_2" "dht_seed_3" "dht_seed_4" "supplier_1" "proxy_server_1" "proxy_server_2" "supplier_2" "supplier_3" "supplier_4" "supplier_5" "supplier_6" "supplier_7" "supplier_8" "customer_1" "customer_2" "customer_3" "customer_4" "customer_5" "customer_backup" "customer_restore"; do echo "[$$node] ==================================="; docker-compose exec $$node cat /root/.bitdust/logs/stderr.log; done

logs_all_states:
	# TODO: keep up to date with docker-compose links
	@for node in "identity-server" "identity-server-a" "identity-server-b" "stun_1" "stun_2" "dht_seed_0" "dht_seed_1" "dht_seed_2" "dht_seed_3" "dht_seed_4" "supplier_1" "proxy_server_1" "proxy_server_2" "supplier_2" "supplier_3" "supplier_4" "supplier_5" "supplier_6" "supplier_7" "supplier_8" "customer_1" "customer_2" "customer_3" "customer_4" "customer_5" "customer_backup" "customer_restore"; do echo "[$$node] ==================================="; docker-compose exec $$node cat /root/.bitdust/logs/automats.log; done

logs_all_events:
	# TODO: keep up to date with docker-compose links
	@for node in "identity-server" "identity-server-a" "identity-server-b" "stun_1" "stun_2" "dht_seed_0" "dht_seed_1" "dht_seed_2" "dht_seed_3" "dht_seed_4" "supplier_1" "proxy_server_1" "proxy_server_2" "supplier_2" "supplier_3" "supplier_4" "supplier_5" "supplier_6" "supplier_7" "supplier_8" "customer_1" "customer_2" "customer_3" "customer_4" "customer_5" "customer_backup" "customer_restore"; do echo "[$$node] ==================================="; docker-compose exec $$node cat /root/.bitdust/logs/event.log; done

logs_all_exceptions:
	# TODO: keep up to date with docker-compose links
	@for node in "identity-server" "identity-server-a" "identity-server-b" "stun_1" "stun_2" "dht_seed_0" "dht_seed_1" "dht_seed_2" "dht_seed_3" "dht_seed_4" "supplier_1" "proxy_server_1" "proxy_server_2" "supplier_2" "supplier_3" "supplier_4" "supplier_5" "supplier_6" "supplier_7" "supplier_8" "customer_1" "customer_2" "customer_3" "customer_4" "customer_5" "customer_backup" "customer_restore"; do echo "[$$node] ==================================="; docker-compose exec $$node cat /root/.bitdust/logs/exception_*.log; done
