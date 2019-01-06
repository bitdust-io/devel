# testing

**How to run:**

You must have Docker installed and running already on your machine.


`git clone https://github.com/bitdust-io/public.git bitdust`

`cd ./bitdust/regression/`

`docker-compose up --build --force-recreate`

`docker-compose exec tester sh -c "python -u -m pytest /app/tests/ -v -s"`


or


`git clone https://github.com/bitdust-io/public.git bitdust`
`cd ./bitdust`
`make regression_test`
