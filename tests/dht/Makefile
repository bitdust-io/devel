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


build:
	docker-compose up -d --build --force-recreate --remove-orphans

produce:
	docker-compose exec dht_producer /root/.bitdust/venv/bin/python /app/bitdust/tests/dht/test_producer.py 1 10

consume:
	docker-compose exec dht_consumer /root/.bitdust/venv/bin/python /app/bitdust/tests/dht/test_consumer.py 1 10

dumpdb:
	docker-compose exec dht_seed_1 /root/.bitdust/venv/bin/python -c "import sqlite3; db=sqlite3.connect('/root/.bitdust/metadata/dhtdb'); cur=db.cursor(); cur.execute('SELECT * FROM data'); import pprint; pprint.pprint(cur.fetchall());"
	# python -c "import sqlite3; db=sqlite3.connect('/tmp/db4'); cur=db.cursor(); cur.execute('SELECT * FROM data'); import pprint, pickle; pprint.pprint([(r[0], pickle.loads(r[1])) for r in cur.fetchall()]);"
