import socket
import json
import random
import os
import time


from namespace import ns
from zlog import exc, exc_short


def get_db(obj, data, name_space):
    db_file_name = ns(name_space).db.db
    with open(db_file_name, 'rb') as infile:
        while True:
            data = infile.read(100)
            if not data:
                break
            obj.send(data)


def send(name_space, god=False):
    db_file_name = ns(name_space).db.db
    db_lock_file_name = ns(name_space).db.db + '.lock'
    if god:
        nodes = ns(name_space).brokers
    else:
        nodes = ns(name_space).nodes.find("nodes", {"relay":1})
        random.shuffle(nodes)
    my_address = ns(name_space).wallet.find("data", "all")[0]['address']
    for x in nodes:
        if x['address'] == my_address:
            continue
        s = socket.socket()
        s.settimeout(5)
        try:
            s.connect((x['ip'], x['port']))
        except:
            s.close()
            exc_short((x['ip'], x['port']))
            continue
        else:
            s.send(json.dumps({"cmd":"get_version"}))
            data = s.recv(1024)
            if data == ns(name_space).version:
                s.close()
                s = socket.socket()
                s.settimeout(5)
                try:
                    s.connect((x['ip'], x['port']))
                except:
                    s.close()
                    exc_short((x['ip'], x['port']))
                    continue
                else:
                    s.send(json.dumps({"cmd":"get_db"}))
                    out = ""
                    while True:
                        data = s.recv(1024)
                        if not data:
                            break
                        out = out + data
                    while os.path.exists(db_lock_file_name):
                        time.sleep(0.1)
                    open(db_lock_file_name, 'w').close()
                    with open(db_file_name, 'wb') as outfile:
                        outfile.write(out)
                    os.remove(db_lock_file_name)
                    break
            else:
                s.close()
