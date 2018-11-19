# testing

**How to run:**

`git clone https://github.com/bitdust-io/public.git bitdust --progress`

`cd ./bitdust/regression/`

`docker-compose up --build --force-recreate`

`docker-compose exec tester sh -c "python -u -m pytest /app/tests/ -v -s"`
