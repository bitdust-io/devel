import landerdb
import os

relay = 1 if os.path.isfile('relay.on') else 0
base_difficulty = 3
mining_threads = 1
brokers = [ {"ip": "185.65.200.231", "port": 6568},
            {"ip": "37.18.255.32",   "port": 6568},
            # {"ip":"zcoin.zapto.org", "port":6565}
          ]
version = "0.2.2"
host = "0.0.0.0"
port = 6568

import pdb
pdb.set_trace()

nodes = landerdb.Connect("nodes.db")
wallet = landerdb.Connect("wallet.db")
db = landerdb.Connect("db.db")
