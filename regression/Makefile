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

_run_all:
	docker-compose up -d

clean_unused_images:
	# docker images | grep '<none>' | awk '{ print $3 }' | xargs docker rmi --force
	docker images -aq -f 'dangling=true' | xargs docker rmi

logs_fetch:
	@rm -rf .logs
	@mkdir .logs
	@for node in "identity-server" "identity-server-a" "identity-server-b" "identity-server-c" "identity-server-d" "identity-server-e" "stun_1" "stun_2" "dht_seed_0" "dht_seed_1" "dht_seed_2" "dht_seed_3" "dht_seed_4" "supplier_1" "proxy_server_1" "proxy_server_2" "supplier_2" "supplier_3" "supplier_4" "supplier_5" "supplier_6" "supplier_7" "supplier_8" "customer_1" "customer_2" "customer_3" "customer_4" "customer_5" "customer_backup" "customer_restore"; do docker-compose exec $$node sh -c "cat /root/.bitdust/logs/automats.log" > .logs/$$node.automats.log; docker-compose exec $$node sh -c "cat /root/.bitdust/logs/event.log" > .logs/$$node.event.log; docker-compose exec $$node sh -c "cat /root/.bitdust/logs/packet.log" > .logs/$$node.packet.log; docker-compose exec $$node sh -c "cat /root/.bitdust/logs/stdout.log" > .logs/$$node.stdout.log; echo $$node; done

logs_all_stdout:
    # TODO: keep up to date with docker-compose links
	@echo "### [identity-server] #########################################################################"
	docker-compose exec identity-server cat /root/.bitdust/logs/stdout.log
	@echo "### [identity-server-a] #########################################################################"
	docker-compose exec identity-server-a cat /root/.bitdust/logs/stdout.log
	@echo "### [identity-server-b] #########################################################################"
	docker-compose exec identity-server-b cat /root/.bitdust/logs/stdout.log
	@echo "### [identity-server-c] #########################################################################"
	docker-compose exec identity-server-c cat /root/.bitdust/logs/stdout.log
	@echo "### [identity-server-d] #########################################################################"
	docker-compose exec identity-server-d cat /root/.bitdust/logs/stdout.log
	@echo "### [identity-server-e] #########################################################################"
	docker-compose exec identity-server-e cat /root/.bitdust/logs/stdout.log
	@echo "### [dht_seed0] ##################################################################################"
	docker-compose exec dht_seed_0 cat /root/.bitdust/logs/stdout.log
	@echo "### [dht_seed1] ##################################################################################"
	docker-compose exec dht_seed_1 cat /root/.bitdust/logs/stdout.log
	@echo "### [dht_seed2] ##################################################################################"
	docker-compose exec dht_seed_2 cat /root/.bitdust/logs/stdout.log
	@echo "### [dht_seed3] ##################################################################################"
	docker-compose exec dht_seed_3 cat /root/.bitdust/logs/stdout.log
	@echo "### [dht_seed4] ##################################################################################"
	docker-compose exec dht_seed_4 cat /root/.bitdust/logs/stdout.log
	@echo "### [stun_1] ##################################################################################"
	docker-compose exec stun_1 cat /root/.bitdust/logs/stdout.log
	@echo "### [stun_2] ##################################################################################"
	docker-compose exec stun_2 cat /root/.bitdust/logs/stdout.log
	@echo "### [proxy_server_1] ##############################################################################"
	docker-compose exec proxy_server_1 cat /root/.bitdust/logs/stdout.log
	@echo "### [proxy_server_2] ##############################################################################"
	docker-compose exec proxy_server_2 cat /root/.bitdust/logs/stdout.log
	@echo "### [supplier_1] ##############################################################################"
	docker-compose exec supplier_1 cat /root/.bitdust/logs/stdout.log
	@echo "### [supplier_2] ##############################################################################"
	docker-compose exec supplier_2 cat /root/.bitdust/logs/stdout.log
	@echo "### [supplier_3] ##############################################################################"
	docker-compose exec supplier_3 cat /root/.bitdust/logs/stdout.log
	@echo "### [supplier_4] ##############################################################################"
	docker-compose exec supplier_4 cat /root/.bitdust/logs/stdout.log
	@echo "### [supplier_5] ##############################################################################"
	docker-compose exec supplier_5 cat /root/.bitdust/logs/stdout.log
	@echo "### [supplier_6] ##############################################################################"
	docker-compose exec supplier_6 cat /root/.bitdust/logs/stdout.log
	@echo "### [supplier_7] ##############################################################################"
	docker-compose exec supplier_7 cat /root/.bitdust/logs/stdout.log
	@echo "### [supplier_8] ##############################################################################"
	docker-compose exec supplier_8 cat /root/.bitdust/logs/stdout.log
	@echo "### [customer_1] ##############################################################################"
	docker-compose exec customer_1 cat /root/.bitdust/logs/stdout.log
	@echo "### [customer_2] ##############################################################################"
	docker-compose exec customer_2 cat /root/.bitdust/logs/stdout.log
	@echo "### [customer_3] ##############################################################################"
	docker-compose exec customer_3 cat /root/.bitdust/logs/stdout.log
	@echo "### [customer_4] ##############################################################################"
	docker-compose exec customer_4 cat /root/.bitdust/logs/stdout.log
	@echo "### [customer_5] ##############################################################################"
	docker-compose exec customer_5 cat /root/.bitdust/logs/stdout.log
	@echo "### [customer_backup] ##############################################################################"
	docker-compose exec customer_backup cat /root/.bitdust/logs/stdout.log
	@echo "### [customer_restore] ##############################################################################"
	docker-compose exec customer_restore cat /root/.bitdust/logs/stdout.log

logs_all_stderr:
    # TODO: keep up to date with docker-compose links
	@echo "### [identity-server] #########################################################################"
	docker-compose exec identity-server cat /root/.bitdust/logs/stderr.log
	@echo "### [identity-server-a] #########################################################################"
	docker-compose exec identity-server-a cat /root/.bitdust/logs/stderr.log
	@echo "### [identity-server-b] #########################################################################"
	docker-compose exec identity-server-b cat /root/.bitdust/logs/stderr.log
	@echo "### [identity-server-c] #########################################################################"
	docker-compose exec identity-server-c cat /root/.bitdust/logs/stderr.log
	@echo "### [identity-server-d] #########################################################################"
	docker-compose exec identity-server-d cat /root/.bitdust/logs/stderr.log
	@echo "### [identity-server-e] #########################################################################"
	docker-compose exec identity-server-e cat /root/.bitdust/logs/stderr.log
	@echo "### [dht_seed0] ##################################################################################"
	docker-compose exec dht_seed_0 cat /root/.bitdust/logs/stderr.log
	@echo "### [dht_seed1] ##################################################################################"
	docker-compose exec dht_seed_1 cat /root/.bitdust/logs/stderr.log
	@echo "### [dht_seed2] ##################################################################################"
	docker-compose exec dht_seed_2 cat /root/.bitdust/logs/stderr.log
	@echo "### [dht_seed3] ##################################################################################"
	docker-compose exec dht_seed_3 cat /root/.bitdust/logs/stderr.log
	@echo "### [dht_seed4] ##################################################################################"
	docker-compose exec dht_seed_4 cat /root/.bitdust/logs/stderr.log
	@echo "### [stun_1] ##################################################################################"
	docker-compose exec stun_1 cat /root/.bitdust/logs/stderr.log
	@echo "### [stun_2] ##################################################################################"
	docker-compose exec stun_2 cat /root/.bitdust/logs/stderr.log
	@echo "### [proxy_server_1] ##############################################################################"
	docker-compose exec proxy_server_1 cat /root/.bitdust/logs/stderr.log
	@echo "### [proxy_server_2] ##############################################################################"
	docker-compose exec proxy_server_2 cat /root/.bitdust/logs/stderr.log
	@echo "### [supplier_1] ##############################################################################"
	docker-compose exec supplier_1 cat /root/.bitdust/logs/stderr.log
	@echo "### [supplier_2] ##############################################################################"
	docker-compose exec supplier_2 cat /root/.bitdust/logs/stderr.log
	@echo "### [supplier_3] ##############################################################################"
	docker-compose exec supplier_3 cat /root/.bitdust/logs/stderr.log
	@echo "### [supplier_4] ##############################################################################"
	docker-compose exec supplier_4 cat /root/.bitdust/logs/stderr.log
	@echo "### [supplier_5] ##############################################################################"
	docker-compose exec supplier_5 cat /root/.bitdust/logs/stderr.log
	@echo "### [supplier_6] ##############################################################################"
	docker-compose exec supplier_6 cat /root/.bitdust/logs/stderr.log
	@echo "### [supplier_7] ##############################################################################"
	docker-compose exec supplier_7 cat /root/.bitdust/logs/stderr.log
	@echo "### [supplier_8] ##############################################################################"
	docker-compose exec supplier_8 cat /root/.bitdust/logs/stderr.log
	@echo "### [customer_1] ##############################################################################"
	docker-compose exec customer_1 cat /root/.bitdust/logs/stderr.log
	@echo "### [customer_2] ##############################################################################"
	docker-compose exec customer_2 cat /root/.bitdust/logs/stderr.log
	@echo "### [customer_3] ##############################################################################"
	docker-compose exec customer_3 cat /root/.bitdust/logs/stderr.log
	@echo "### [customer_4] ##############################################################################"
	docker-compose exec customer_4 cat /root/.bitdust/logs/stderr.log
	@echo "### [customer_5] ##############################################################################"
	docker-compose exec customer_5 cat /root/.bitdust/logs/stderr.log
	@echo "### [customer_backup] ##############################################################################"
	docker-compose exec customer_backup cat /root/.bitdust/logs/stderr.log
	@echo "### [customer_restore] ##############################################################################"
	docker-compose exec customer_restore cat /root/.bitdust/logs/stderr.log

logs_all_states:
	# TODO: keep up to date with docker-compose links
	@echo "### [identity-server] #########################################################################"
	docker-compose exec identity-server cat /root/.bitdust/logs/automats.log
	@echo "### [identity-server-a] #########################################################################"
	docker-compose exec identity-server-a cat /root/.bitdust/logs/automats.log
	@echo "### [identity-server-b] #########################################################################"
	docker-compose exec identity-server-b cat /root/.bitdust/logs/automats.log
	@echo "### [identity-server-c] #########################################################################"
	docker-compose exec identity-server-c cat /root/.bitdust/logs/automats.log
	@echo "### [identity-server-d] #########################################################################"
	docker-compose exec identity-server-d cat /root/.bitdust/logs/automats.log
	@echo "### [identity-server-e] #########################################################################"
	docker-compose exec identity-server-e cat /root/.bitdust/logs/automats.log
	@echo "### [dht_seed0] ##################################################################################"
	docker-compose exec dht_seed_0 cat /root/.bitdust/logs/automats.log
	@echo "### [dht_seed1] ##################################################################################"
	docker-compose exec dht_seed_1 cat /root/.bitdust/logs/automats.log
	@echo "### [dht_seed2] ##################################################################################"
	docker-compose exec dht_seed_2 cat /root/.bitdust/logs/automats.log
	@echo "### [dht_seed3] ##################################################################################"
	docker-compose exec dht_seed_3 cat /root/.bitdust/logs/automats.log
	@echo "### [dht_seed4] ##################################################################################"
	docker-compose exec dht_seed_4 cat /root/.bitdust/logs/automats.log
	@echo "### [stun_1] ##################################################################################"
	docker-compose exec stun_1 cat /root/.bitdust/logs/automats.log
	@echo "### [stun_2] ##################################################################################"
	docker-compose exec stun_2 cat /root/.bitdust/logs/automats.log
	@echo "### [proxy_server_1] ##############################################################################"
	docker-compose exec proxy_server_1 cat /root/.bitdust/logs/automats.log
	@echo "### [proxy_server_2] ##############################################################################"
	docker-compose exec proxy_server_2 cat /root/.bitdust/logs/automats.log
	@echo "### [supplier_1] ##############################################################################"
	docker-compose exec supplier_1 cat /root/.bitdust/logs/automats.log
	@echo "### [supplier_2] ##############################################################################"
	docker-compose exec supplier_2 cat /root/.bitdust/logs/automats.log
	@echo "### [supplier_3] ##############################################################################"
	docker-compose exec supplier_3 cat /root/.bitdust/logs/automats.log
	@echo "### [supplier_4] ##############################################################################"
	docker-compose exec supplier_4 cat /root/.bitdust/logs/automats.log
	@echo "### [supplier_5] ##############################################################################"
	docker-compose exec supplier_5 cat /root/.bitdust/logs/automats.log
	@echo "### [supplier_6] ##############################################################################"
	docker-compose exec supplier_6 cat /root/.bitdust/logs/automats.log
	@echo "### [supplier_7] ##############################################################################"
	docker-compose exec supplier_7 cat /root/.bitdust/logs/automats.log
	@echo "### [supplier_8] ##############################################################################"
	docker-compose exec supplier_8 cat /root/.bitdust/logs/automats.log
	@echo "### [customer_1] ##############################################################################"
	docker-compose exec customer_1 cat /root/.bitdust/logs/automats.log
	@echo "### [customer_2] ##############################################################################"
	docker-compose exec customer_2 cat /root/.bitdust/logs/automats.log
	@echo "### [customer_3] ##############################################################################"
	docker-compose exec customer_3 cat /root/.bitdust/logs/automats.log
	@echo "### [customer_4] ##############################################################################"
	docker-compose exec customer_4 cat /root/.bitdust/logs/automats.log
	@echo "### [customer_5] ##############################################################################"
	docker-compose exec customer_5 cat /root/.bitdust/logs/automats.log
	@echo "### [customer_backup] ##############################################################################"
	docker-compose exec customer_backup cat /root/.bitdust/logs/automats.log
	@echo "### [customer_restore] ##############################################################################"
	docker-compose exec customer_restore cat /root/.bitdust/logs/automats.log
