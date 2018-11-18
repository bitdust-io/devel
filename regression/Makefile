BUILD=.build
RUN_ALL=.run_all
RUN_TEST_1=.run_test_1
RUN_TEST_2=.run_test_2
PYTHON_VERSION=2.7

.PHONY: test

clean: clean_all

clean_build:
	@rm -f $(BUILD)

test: clean_build clean $(BUILD) $(RUN_ALL) test_all

$(BUILD):
	docker-compose build --build-arg PYTHON_VERSION=$(PYTHON_VERSION)
	@touch $@

$(RUN_ALL): $(BUILD)
	$(MAKE) _run_all
	@touch $@

$(RUN_TEST_1): $(BUILD)
	$(MAKE) NAMESPACE="namespace1" _run
	@touch $@

$(RUN_TEST_2): $(BUILD)
	$(MAKE) NAMESPACE="namespace2" _run
	@touch $@

test_all: $(RUN_ALL)
	$(MAKE) COMMAND="python -u -m pytest /app/tests/ -v -s" _test_all

test_1: $(RUN_TEST_1)
	$(MAKE) NAMESPACE="namespace1" COMMAND="python -u -m pytest /app/tests/test_role_proxy_router/ -v -s" _test

test_2: $(RUN_TEST_2)
	$(MAKE) NAMESPACE="namespace2" COMMAND="python -u -m pytest /app/tests/test_role_customer/ -v -s" _test

clean_all:
	$(MAKE) _clean_all
	@rm -f $(RUN_ALL)

clean_1:
	$(MAKE) NAMESPACE="namespace1" _clean
	@rm -f $(RUN_TEST_1)

clean_2:
	$(MAKE) NAMESPACE="namespace2" _clean
	@rm -f $(RUN_TEST_2)

clean_unused_images:
	docker images | grep '<none>' | awk '{ print $3 }' | xargs docker rmi --force

_test:
	docker-compose -p ${NAMESPACE} exec -T tester sh -c "${COMMAND}"

_test_all:
	docker-compose exec tester sh -c "${COMMAND}"

_clean:
	docker-compose -p ${NAMESPACE} down -v -t 1

_clean_all:
	docker-compose down -v -t 1

_run_all:
	docker-compose up -d

_run:
	docker-compose -p ${NAMESPACE} up -d
