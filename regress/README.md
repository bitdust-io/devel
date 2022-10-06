# BitDust Regression tests


### How To

You must have [Docker](https://docs.docker.com/install/) installed and running already on your machine.

Also you need to install [Docker Compose](https://docs.docker.com/compose/install/) tool.


If you did not cloned BitDust sources locally yet:

        git clone https://github.com/bitdust-io/public.git bitdust


Make sure you are inside `regress` sub folder:

        cd bitdust/regress/


Then just run the whole BitDust regression set with a single command:

        PYTHON_VERSION=3.6 make test


All regression tests are split into groups, you can find them in `tests/` sub folder.

To run a single regression group you can use such commands:

        make stop_all
        PYTHON_VERSION=3.6 make prepare
        make run/identity_recover


To be able to analyze BitDust issues you can check the output logs.
Such command will automatically copy log files from all containers into `logs/` sub folder for you after finishing the test case:

        make run_log/identity_recover


To create a new regression group you first create a new sub folder inside `tests/` folder.
Then you need to build new `conf.json` file and place it in that sub folder - that files describes all containers in the regression group. Based on it a new `docker-compose.yml` file will be automatically generated and used when you run a test.

You can take copy `conf.json` file from another existing regression group and modify for your needs. Try to reduce number of containers you use - it will speed up the tests.

Then you create a python file which actually suppose to orchestrate and test BitDust software running on multiple containers. So create a new file `tests/new_regression_group/test_someting.py` (next to `conf.json` file), build new `pytest` method and run the test:

        PYTHON_VERSION=3.6 make prepare
        make run_log/new_regression_group
