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


.PHONY: test


stop_all:
	@docker stop $$(docker ps -a -q)

clean_all:
	@docker rm $$(docker ps -a -q)

remove_all:
	@docker rmi -f $$(docker images -a -q)

prune:
	@docker system prune

build_tester:
	@docker-compose build --build-arg tester_image

build_app:
	@docker-compose build --build-arg PYTHON_VERSION=$(PYTHON_VERSION) app_image

_one_prepare:
	@python3 prepare_test.py ${TEST_NAME};

_one_up:
	@docker-compose --file tests/${TEST_NAME}/docker-compose.yml up -d --no-deps --build tester; docker-compose --file tests/${TEST_NAME}/docker-compose.yml up -d;

_one_down:
	@docker-compose --file tests/${TEST_NAME}/docker-compose.yml down -v -t 1;

_one_test:
	@docker-compose --file tests/${TEST_NAME}/docker-compose.yml exec tester sh -c "TEST_NAME=${TEST_NAME} python -u -m pytest /app/testds/${TEST_NAME}/ -v -s" > logs/tester.${TEST_NAME}.log || $(error test ${TEST_NAME} failed)

_one_log:
	@/bin/bash fetch_logs.sh ${TEST_NAME}

_one_up_test_down:
	@$(MAKE) _one_up; $(MAKE) _one_test; $(MAKE) _one_down; 

_one_up_test_log_down:
	@$(MAKE) _one_up; $(MAKE) _one_test; $(MAKE) _one_log; $(MAKE) _one_down;

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

test_customer_family:
	@$(MAKE) TEST_NAME=customer_family _one_up_test_down;

test_identity_rotate_customer:
	@$(MAKE) TEST_NAME=identity_rotate_customer _one_up_test_down;

test_identity_rotate_supplier:
	@$(MAKE) TEST_NAME=identity_rotate_supplier _one_up_test_down;

test: test_customer_family test_identity_rotate_customer test_identity_rotate_supplier

