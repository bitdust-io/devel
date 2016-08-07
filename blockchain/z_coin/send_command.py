import socket
import json
import random

from namespace import ns


def send(cmd, name_space, out=False, god=False):
    if god:
        nodes = ns(name_space).brokers
    else:
        nodes = ns(name_space).nodes.find("nodes", {"relay":1})
        random.shuffle(nodes)
    if not nodes:
        nodes = ns(name_space).brokers
    my_address = ns(name_space).wallet.find("data", "all")[0]['address']
    for x in nodes:
        if x['address'] == my_address:
            continue
        s = socket.socket()
        try:
            s.connect((x['ip'], x['port']))
        except:
            s.close()
            continue
        else:
            s.send(json.dumps({"cmd":"get_version"}))
            data = s.recv(1024)
            if data == ns(name_space).version:
                s.close()
                s = socket.socket()
                try:
                    s.connect((x['ip'], x['port']))
                except:
                    s.close()
                    continue
                else:
                    s.send(json.dumps(cmd))
                    out = ""
                    while True:
                        data = s.recv(1024)
                        if not data:
                            break
                        out = out + data
                    s.close()
                    if out:
                        return out
            else:
                s.close()

