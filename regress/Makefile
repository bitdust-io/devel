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


# PYTHON_VERSION=2.7.15

ALL_TESTS := $(patsubst tests/%,%,$(wildcard tests/*))


.PHONY: test


stop_all:
	@docker stop $$(docker ps -a -q) || exit 0

clean_all:
	@docker rm $$(docker ps -a -q) || exit 0

remove_all:
	@docker rmi -f $$(docker images -a -q) || exit 0

prune:
	@docker system prune

build_tester:
	@docker-compose build --build-arg tester_image

build_app:
	@docker-compose build --build-arg PYTHON_VERSION=$(PYTHON_VERSION) app_image

_one_prepare:
	@echo "PREPARE ${TEST_NAME}"; python3 prepare_test.py ${TEST_NAME};

_one_up:
	@echo "UP ${TEST_NAME}"; docker-compose --file tests/${TEST_NAME}/docker-compose.yml up -d --no-deps --build tester && docker-compose --file tests/${TEST_NAME}/docker-compose.yml up -d 2> /dev/null

_one_down:
	@echo "DOWN ${TEST_NAME}"; docker-compose --file tests/${TEST_NAME}/docker-compose.yml down -v -t 1 2> /dev/null

_one_test:
	@echo "TEST ${TEST_NAME}"; docker-compose --file tests/${TEST_NAME}/docker-compose.yml exec tester sh -c "TEST_NAME=${TEST_NAME} python -u -m pytest /app/tests/${TEST_NAME}/ -v -s" > logs/tester.${TEST_NAME}.log

_one_log:
	@echo "LOG ${TEST_NAME}"; /bin/bash fetch_logs.sh ${TEST_NAME} > /dev/null;

_one_up_test_down:
	@$(MAKE) _one_up && $(MAKE) _one_test && $(MAKE) _one_down

_one_up_test_log_down:
	@$(MAKE) _one_up && $(MAKE) _one_test && $(MAKE) _one_log && $(MAKE) _one_down

up/%:
	@$(MAKE) TEST_NAME=$* _one_up

down/%:
	@$(MAKE) TEST_NAME=$* _one_down

test/%:
	@$(MAKE) TEST_NAME=$* _one_test

log/%:
	@$(MAKE) TEST_NAME=$* _one_log

run/%:
	@$(MAKE) TEST_NAME=$* _one_up_test_down

run_and_log/%:
	@$(MAKE) TEST_NAME=$* _one_up_test_log_down

run_all:
	@echo "$(ALL_TESTS)"; for ONE_TEST in $(ALL_TESTS); do $(MAKE) run/$$ONE_TEST || exit 1; done

test: build_app build_tester run_all
