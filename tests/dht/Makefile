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

stop:
	@docker stop $$(docker ps -a -q) || exit 0

clean:
	@docker rm $$(docker ps -a -q) || exit 0

kill:
	@docker rmi -f $$(docker images -a -q) || exit 0

build:
	docker-compose up -d --build --force-recreate --remove-orphans

run:
	docker-compose up --build --force-recreate --remove-orphans

ps:
	docker-compose exec producer bash -c "ps aux"

shell:
	docker-compose exec producer bash

produce:
	docker-compose exec producer bash -c "/root/.bitdust/venv/bin/python /app/bitdust/dht/dht_service.py $(cmd)"

produce_sample_data:
	docker-compose exec producer /root/.bitdust/venv/bin/python /app/bitdust/tests/dht/test_producer.py 1 10

consume_sample_data:
	docker-compose exec consumer /root/.bitdust/venv/bin/python /app/bitdust/tests/dht/test_consumer.py 1 15

dumpdb:
	docker-compose exec seed1 /root/.bitdust/venv/bin/python -c "import sqlite3; db=sqlite3.connect('/root/.bitdust/dht/db_0'); cur=db.cursor(); cur.execute('SELECT * FROM data'); import pprint; pprint.pprint(cur.fetchall());"
	# python -c "import sqlite3; db=sqlite3.connect('/tmp/db4'); cur=db.cursor(); cur.execute('SELECT * FROM data'); import pprint, pickle; pprint.pprint([(r[0], pickle.loads(r[1])) for r in cur.fetchall()]);"
