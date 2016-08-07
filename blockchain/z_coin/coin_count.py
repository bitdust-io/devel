import json

import send_command
import get_db

from namespace import ns
from zlog import out


def coin_count(obj, data, name_space):
    coins = ns(name_space).db.find("coins", "all")    
    if coins:
        obj.send(json.dumps({"coins":len(coins)}))
    else:
        obj.send(json.dumps({"coins":0}))


def send(name_space):
    coins = ns(name_space).db.find("coins", "all")
    if coins:
        coins = len(coins)
    else:
        coins = 0
    o = send_command.send({"cmd":"coin_count"}, name_space, out=True)
    if not o:
        out("Couldn't get number of coins, restart please")
        return
    try:
        o = json.loads(o)
    except:
        out("Couldn't get number of coins, if this persists please reset.")
        return
    else:
        out("total coins: " + str(o))
        if o['coins'] > coins:
            get_db.send(name_space)


