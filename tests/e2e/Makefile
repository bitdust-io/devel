.PHONY: all

all: run_1 run_2

run_all: all

test_parallel: test_1 test_2

clean_all: clean_1 clean_2

run:
	docker-compose -p ${NAMESPACE} up --build --force-recreate -d

clean: 
	docker-compose -p ${NAMESPACE} down -v

test:
	docker-compose -p ${NAMESPACE} exec test sh -c "${COMMAND}"

run_1:
	$(MAKE) NAMESPACE="namespace1" run
run_2:
	$(MAKE) NAMESPACE="namespace2" run

test_1:
	$(MAKE) NAMESPACE="namespace1" COMMAND="pytest tests/test_ss/ -v -s" test
	
test_2:
	$(MAKE) NAMESPACE="namespace2" COMMAND="pytest tests/test_upload_file/ -v -s" test

clean_1:
	$(MAKE) NAMESPACE="namespace1" clean

clean_2:
	$(MAKE) NAMESPACE="namespace2" clean
