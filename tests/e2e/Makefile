BUILD=.build
RUN_TEST_1=.run_test_1
RUN_TEST_2=.run_test_2
PYTHON_VERSION=2.7

.PHONY: test

clean: clean_1 clean_2

clean_build:
	@rm -f $(BUILD)

test: clean_build clean $(BUILD) $(RUN_TEST_1) $(RUN_TEST_2) test_1 test_2

$(BUILD):
	docker-compose build --build-arg PYTHON_VERSION=$(PYTHON_VERSION)
	@touch $@

$(RUN_TEST_1): $(BUILD)
	$(MAKE) NAMESPACE="namespace1" _run
	@touch $@

$(RUN_TEST_2): $(BUILD)
	$(MAKE) NAMESPACE="namespace2" _run
	@touch $@

test_1: $(RUN_TEST_1)
	$(MAKE) NAMESPACE="namespace1" COMMAND="python -u -m pytest tests/test_role_proxy_router/ -v -s" _test

test_2: $(RUN_TEST_2)
	$(MAKE) NAMESPACE="namespace2" COMMAND="python -u -m pytest tests/test_role_customer/ -v -s" _test

clean_1:
	$(MAKE) NAMESPACE="namespace1" _clean
	@rm -f $(RUN_TEST_1)

clean_2:
	$(MAKE) NAMESPACE="namespace2" _clean
	@rm -f $(RUN_TEST_2)

clean_unused_images:
	docker images | grep '<none>' | awk '{ print $3 }' | xargs docker rmi --force

_test:
	docker-compose -p ${NAMESPACE} exec -T test sh -c "${COMMAND}"

_clean:
	docker-compose -p ${NAMESPACE} down -v -t 1

_run:
	docker-compose -p ${NAMESPACE} up -d
