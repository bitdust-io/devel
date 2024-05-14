#
# Makefile
#
# Copyright (C) 2018 Stanislav Evseev, Veselin Penev  https://bitdust.io
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
# * python3
# * docker
# * docker-compose

ifeq ($(PYTHON_VERSION),)
	PYTHON_VERSION=3.9
endif

ALL_TESTS := $(patsubst tests/%,%,$(wildcard tests/*))

SOME_TESTS := chat storage dht

assert-is-file = $(if $(realpath $1/),$(error Assertion failure: [$1] is a file!))

.PHONY: test


stop_all:
	@docker stop $$(docker ps -a -q) || exit 0

clean_all:
	@docker rm $$(docker ps -a -q) || exit 0

remove_all:
	@docker rmi -f $$(docker images -a -q) || exit 0

prune:
	@docker system prune

clean_logs:
	@rm -rf logs/;
	@mkdir -p logs/;

clean_coverage:
	@mkdir -p coverage_all/;
	@rm -rf coverage/*;
	@rm -rf coverage_all/*;

build_tester:
	@docker-compose build tester_image

build_app:
	@docker-compose build --build-arg PYTHON_VERSION=$(PYTHON_VERSION) app_image

$(ALL_TESTS):
	@$(MAKE) --no-print-directory --output-sync=none spawn_run_log/$@

_all_tests: $(ALL_TESTS)
	@echo "ALL TESTS ARE FINISHED"

_one_prepare:
	@echo "PREPARE ${TEST_NAME}"; python3 prepare_test.py ${TEST_NAME};

_one_up:
	@echo "UP ${TEST_NAME}"
	@docker-compose --file tests/${TEST_NAME}/docker-compose.yml up -d --no-deps --build tester 1>/dev/null 2>logs/container.${TEST_NAME}.err && docker-compose --file tests/${TEST_NAME}/docker-compose.yml up -d  1>/dev/null 2>>logs/container.${TEST_NAME}.err

_one_down:
	@echo "DOWN ${TEST_NAME}";
	@docker-compose --file tests/${TEST_NAME}/docker-compose.yml down -v -t 1 1>/dev/null 2>/dev/null || echo "DOWN ${TEST_NAME} failed but ignored"

_one_clean_test:
	@echo "DOCKER COMPOSE EXEC ${TEST_NAME} DEBUG=${_DEBUG} PAUSE_BEFORE=${_PAUSE_BEFORE}";
	@mkdir -p logs;
	@docker-compose --file tests/${TEST_NAME}/docker-compose.yml exec -T tester sh -c "TEST_NAME=${TEST_NAME} _DEBUG=${_DEBUG} STOP_NODES=1 CLEAN_NODES=1 PAUSE_BEFORE=${_PAUSE_BEFORE} python3 -u -m pytest /app/tests/${TEST_NAME}/ -v -s"  # 2> logs/container.${TEST_NAME}.err

_one_test:
	@echo "TEST ${TEST_NAME} DEBUG=${_DEBUG}";
	@mkdir -p logs;
	@docker-compose --file tests/${TEST_NAME}/docker-compose.yml exec -T tester sh -c "TEST_NAME=${TEST_NAME} _DEBUG=${_DEBUG} VERBOSE=${VERBOSE} python3 -u -m pytest /app/tests/${TEST_NAME}/ -v -s" 2> logs/container.${TEST_NAME}.stderr || (echo "test ${TEST_NAME} FAILED !!!" && echo "FAIL" > logs/container.${TEST_NAME}.fail && exit 1)

_one_test_rerun:
	@echo "TEST with 1 re-run ${TEST_NAME} DEBUG=${_DEBUG} PAUSE_BEFORE=${_PAUSE_BEFORE}";
	@mkdir -p logs;
	@$(MAKE) --no-print-directory --output-sync=none _one_clean_test || (echo "\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\ntest ${TEST_NAME} DID NOT PASS FIRST TIME, try to re-run" && $(MAKE) --no-print-directory _one_clean_test ) || (echo "test ${TEST_NAME} FAILED !!!" && echo "FAIL" > logs/container.${TEST_NAME}.fail && exit 1)

_one_test_execute:
	@echo "TEST ${TEST_NAME} DEBUG=${_DEBUG} PAUSE_BEFORE=${_PAUSE_BEFORE}";
	@mkdir -p logs;
	@$(MAKE) --no-print-directory --output-sync=none _one_clean_test || (echo "test ${TEST_NAME} FAILED !!!" && echo "FAIL" > logs/container.${TEST_NAME}.fail && exit 1)

_one_coverage:
	@echo "COVERAGE ${TEST_NAME}";
	@mkdir -p ./coverage/${TEST_NAME}/;
	@docker cp $$(docker-compose --file tests/${TEST_NAME}/docker-compose.yml ps -q tester):/app/coverage/. ./coverage/${TEST_NAME}/

_one_log:
	@echo "LOG ${TEST_NAME}";
	@/bin/bash fetch_logs.sh ${TEST_NAME} ;

_one_post_report:
	@echo "LOG ${TEST_NAME}";
	@/bin/bash build_report.sh ${TEST_NAME} > /dev/null;

_one_up_test_coverage_down:
	@$(MAKE) --no-print-directory --output-sync=line _one_prepare && $(MAKE) --no-print-directory --output-sync=line _one_up && $(MAKE) --no-print-directory --output-sync=none _one_test && $(MAKE) --no-print-directory --output-sync=line _one_coverage && $(MAKE) --no-print-directory --output-sync=line _one_down

_one_up_test_log_down:
	@$(MAKE) --no-print-directory _one_prepare && $(MAKE) --no-print-directory _one_up && ( $(MAKE) --no-print-directory _one_test || ( $(MAKE) --no-print-directory _one_log && echo "TEST FAILED!!!" && exit 1 ) ) && $(MAKE) --no-print-directory _one_coverage && $(MAKE) --no-print-directory _one_log && $(MAKE) --no-print-directory _one_down

_one_up_test_log_down_parallel:
	@$(MAKE) --no-print-directory --output-sync=none _one_prepare && $(MAKE) --no-print-directory --output-sync=none _one_up && $(MAKE) --no-print-directory --output-sync=none _one_test_execute && $(MAKE) --no-print-directory --output-sync=recurse _one_coverage && $(MAKE) --no-print-directory --output-sync=recurse _one_log && $(MAKE) --no-print-directory --output-sync=recurse _one_down

_one_up_test_log:
	@$(MAKE) --no-print-directory --output-sync=line _one_prepare && $(MAKE) --no-print-directory --output-sync=line _one_up && ( $(MAKE) --no-print-directory --output-sync=none _one_test || echo "TEST FAILED!!!" ) && $(MAKE) --no-print-directory --output-sync=line _one_log

_one_up_test_coverage_log:
	@$(MAKE) --no-print-directory --output-sync=line _one_prepare && $(MAKE) --no-print-directory --output-sync=line _one_up && ( $(MAKE) --no-print-directory --output-sync=none _one_test || echo "TEST FAILED!!!" ) && $(MAKE) --no-print-directory --output-sync=line _one_coverage && $(MAKE) --no-print-directory --output-sync=line _one_log

up/%:
	@$(MAKE) --no-print-directory TEST_NAME=$* _one_up

down/%:
	@$(MAKE) --no-print-directory TEST_NAME=$* _one_down

test/%:
	@$(MAKE) --no-print-directory TEST_NAME=$* _one_test

cover/%:
	@$(MAKE) --no-print-directory TEST_NAME=$* _one_coverage

log/%:
	@$(MAKE) --no-print-directory TEST_NAME=$* _one_log

run/%:
	@$(MAKE) --no-print-directory --output-sync=line TEST_NAME=$* _one_up_test_coverage_down
	@echo ''; echo '';

run_log/%:
	@$(MAKE) --no-print-directory --output-sync=line TEST_NAME=$* _DEBUG=1 _one_up_test_log_down

spawn_run_log/%:
	@echo "STARTING $*"
	@$(MAKE) --no-print-directory --output-sync=none TEST_NAME=$* _DEBUG=1 _PAUSE_BEFORE=${_PAUSE_BEFORE} _one_up_test_log_down_parallel

run_log_up/%:
	@$(MAKE) --no-print-directory TEST_NAME=$* _DEBUG=1 _one_up_test_log

post_report/%:
	@$(MAKE) --no-print-directory TEST_NAME=$* _DEBUG=1 _one_post_report

coverage_combine:
	@echo "COVERAGE COMBINE"; for ONE_TEST in $(ALL_TESTS); do cp -r ./coverage/$$ONE_TEST/*/.coverage* ./coverage_all/ 2>/dev/null; done; mv -f ../.coverage ./coverage_all/.coverage_unit_tests 2>/dev/null; ~/.bitdust/venv/bin/python3 -m pip install "coverage<5"; cd coverage_all; ~/.bitdust/venv/bin/python3 -m coverage combine; cd ../../; python3 -c "import os; cur=os.path.abspath('.'); fin=open('regress/coverage_all/.coverage'); s=fin.read(); fin.close(); s=s.replace('/app/bitdust', cur); open('.coverage', 'w').write(s);"; cd regress;

coverage_report:
	@echo "COVERAGE REPORT"; cd ..; ~/.bitdust/venv/bin/python3 -m coverage report -i --omit="transport/http/*,transport/udp/*,tests/*,regress/*,coins/*,broadcast/*,updates/os_windows_update.py,setup.py,setup_gen.py,raid/worker.py,storage/backup_schedule.py,parallelp/pp/*,main/install_wizard.py,lib/txrestapi/txrestapi/*,lib/schedule.py,lib/jsontemplate.py,interface/cmd_line_json.py,interface/cmd_line_json_templates.py,dht/entangled/dtuple.py,currency/*,chat/terminal_chat.py,CodernityDB/*,CodernityDB3/*",lib/txws.py; cd regress;

build_report_all:
	@echo "$(ALL_TESTS)"; for ONE_TEST in $(ALL_TESTS); do $(MAKE) --no-print-directory post_report/$$ONE_TEST || exit 1; done;

run_all: clean_coverage clean_logs
	@echo "ALL TESTS: $(ALL_TESTS)"; for ONE_TEST in $(ALL_TESTS); do $(MAKE) --no-print-directory run/$$ONE_TEST || exit 1; done;

run_all_log: clean_coverage clean_logs
	@echo "ALL TESTS: $(ALL_TESTS)"; for ONE_TEST in $(ALL_TESTS); do $(MAKE) --no-print-directory run_log/$$ONE_TEST || exit 1; done;

run_parallel: clean_coverage clean_logs _all_tests

check_parallel_results:
	@test ! -f logs/*.fail || { echo FAILED; exit 1; }
	@echo SUCCESS!!!

prepare: build_app build_tester

report: coverage_combine coverage_report check_parallel_results

test_log: prepare run_all_log report

test: prepare run_all report

shell:
	docker-compose --file tests/$(test)/docker-compose.yml exec $(node) bash
