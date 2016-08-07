import os
import time

import send_command

from namespace import ns
from zlog import out


def register(obj, data, name_space):
    nodes_lock_file_name = ns(name_space).nodes.db + '.lock'
    while os.path.exists(nodes_lock_file_name):
        time.sleep(0.1)
    open(nodes_lock_file_name,'w').close()
    stuff = ns(name_space).nodes.find("nodes", {"address":data['address']})
    if stuff:
        for x in stuff:
            ns(name_space).nodes.remove("nodes", x)
            ns(name_space).nodes.save()
            out('Old node removed: ' + x['address'])
    ns(name_space).nodes.insert("nodes", data)
    ns(name_space).nodes.save()
    os.remove(nodes_lock_file_name)
    out('New node registered: ' + data['address'])


def send(name_space):
    data = ns(name_space).wallet.find("data", "all")[0]
    send_command.send({
        "cmd":"register", 
        "relay":ns(name_space).relay, 
        "public":data['public'], 
        "address":data['address'], 
        "port":ns(name_space).port
    }, name_space)
