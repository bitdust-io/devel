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
	@echo "UP ${TEST_NAME}"; docker-compose --file tests/${TEST_NAME}/docker-compose.yml up -d --no-deps --build tester && docker-compose --file tests/${TEST_NAME}/docker-compose.yml up -d 1> /dev/null 2> /dev/null

_one_down:
	@echo "DOWN ${TEST_NAME}"; docker-compose --file tests/${TEST_NAME}/docker-compose.yml down -v -t 1 1> /dev/null 2> /dev/null

_one_test:
	@echo "TEST ${TEST_NAME}"; mkdir -p logs; docker-compose --file tests/${TEST_NAME}/docker-compose.yml exec tester sh -c "TEST_NAME=${TEST_NAME} python -u -m pytest /app/tests/${TEST_NAME}/ -v -s" > logs/tester.${TEST_NAME}.log || (cat logs/tester.${TEST_NAME}.log && exit 1)

_one_coverage:
	@echo "COVERAGE ${TEST_NAME}"; mkdir -p ./coverage/${TEST_NAME}/; docker cp $$(docker-compose --file tests/${TEST_NAME}/docker-compose.yml ps -q tester):/app/coverage/. ./coverage/${TEST_NAME}/

_one_log:
	@echo "LOG ${TEST_NAME}"; /bin/bash fetch_logs.sh ${TEST_NAME} > /dev/null;

_one_up_test_coverage_down:
	@$(MAKE) --no-print-directory _one_prepare && $(MAKE) --no-print-directory _one_up && $(MAKE) --no-print-directory _one_test && $(MAKE) --no-print-directory _one_coverage && $(MAKE) --no-print-directory _one_down

_one_up_test_log_down:
	@$(MAKE) _one_prepare && $(MAKE) _one_up && $(MAKE) _one_test && $(MAKE) _one_log && $(MAKE) _one_down

up/%:
	@$(MAKE) TEST_NAME=$* _one_up

down/%:
	@$(MAKE) TEST_NAME=$* _one_down

test/%:
	@$(MAKE) TEST_NAME=$* _one_test

cover/%:
	@$(MAKE) TEST_NAME=$* _one_coverage

log/%:
	@$(MAKE) TEST_NAME=$* _one_log

run/%:
	@$(MAKE) TEST_NAME=$* _one_up_test_coverage_down

run_log/%:
	@$(MAKE) TEST_NAME=$* _one_up_test_log_down

coverage_combine:
	@echo "COVERAGE COMBINE"; mkdir -p ./coverage_all/; rm -rf ./coverage_all/*; for ONE_TEST in $(ALL_TESTS); do cp -r ./coverage/$$ONE_TEST/*/.coverage* ./coverage_all/; done; mv -f ../.coverage ./coverage_all/.coverage_unit_tests; ~/.bitdust/venv/bin/python -m pip install coverage; cd coverage_all; ~/.bitdust/venv/bin/python -m coverage combine; cd ../../; python3 -c "import os; cur=os.path.abspath('.'); fin=open('regress/coverage_all/.coverage'); s=fin.read(); fin.close(); s=s.replace('/app/bitdust', cur); open('.coverage', 'w').write(s);" cd regress/;

coverage_report:
	@echo "COVERAGE REPORT"; cd ..; ~/.bitdust/venv/bin/python -m coverage report -i --omit="transport/http/*,transport/udp/*,tests/*,regress/*,regression/*,coins/*,broadcast/*,updates/os_windows_update.py,storage/filemanager_api.py,setup.py,setup_gen.py,raid/worker.py,storage/backup_schedule.py,parallelp/pp/*,main/install_wizard.py,lib/txrestapi/txrestapi/*,lib/schedule.py,lib/jsontemplate.py,lib/fastjsonrpc/*,interface/jsonrpc_client.py,interface/cmd_line_json.py,interface/cmd_line_json_templates.py,dht/entangled/dtuple.py,currency/*,chat/terminal_chat.py,CodernityDB/*,CodernityDB3/*",lib/txws.py; cd regress;

run_all:
	@echo "$(ALL_TESTS)"; rm -rf coverage/*; rm -rf coverage_all/*; for ONE_TEST in $(ALL_TESTS); do $(MAKE) run/$$ONE_TEST || exit 1; done;

run_all_log:
	@echo "$(ALL_TESTS)"; mkdir -p logs; for ONE_TEST in $(ALL_TESTS); do $(MAKE) run_log/$$ONE_TEST || exit 1; done;

prepare: build_app build_tester

report: coverage_combine coverage_report

test_log: prepare run_all_log

test: prepare run_all report
