import os
import socket
import json
import random
import time

import send_command

from namespace import ns
from zlog import out, exc


def count_send(name_space):
    mine = ns(name_space).nodes.find("nodes", "all")
    if not mine:
        mine = 0
    else:
        mine = len(mine)
    out('mine coins: ' + str(mine))
    check = send_command.send({"cmd":"get_nodes_count"}, name_space, out=True)
    if not check:
        return
    check = json.loads(check)
    if check['nodes'] > mine:
        send(name_space)


def count(obj, data, name_space):
    co = ns(name_space).nodes.find("nodes", "all")
    if not co:
        co = 0
    else:
        co = len(co)
    obj.send(json.dumps({"nodes":co}))


def get_nodes(obj, data, name_space):
    nodes_file_name = ns(name_space).nodes.db
    with open(nodes_file_name, 'rb') as infile:
        while True:
            data = infile.read(100)
            if not data:
                break
            obj.send(data)


def send(name_space, god=False):
    nodes_file_name = ns(name_space).nodes.db
    nodes_lock_file_name = ns(name_space).nodes.db + '.lock'
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
            exc()
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
                    exc()
                    continue
                else:
                    s.send(json.dumps({"cmd":"get_nodes"}))
                    out = ""
                    while True:
                        data = s.recv(1024)
                        if not data:
                            break
                        out = out + data
                    while os.path.exists(nodes_lock_file_name):
                        time.sleep(0.1)
                    open(nodes_lock_file_name, 'w').close()
                    with open(nodes_file_name, 'wb') as outfile:
                        outfile.write(out)
                    os.remove(nodes_lock_file_name)
                    break
            else:
                s.close()

