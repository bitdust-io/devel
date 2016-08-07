import os

import landerdb


_Namespaces = {}
_BaseDir = '.'


def base_dir():
    global _BaseDir
    return _BaseDir


def set_base_dir(path):
    global _BaseDir
    _BaseDir = path


def ns(name):
    global _Namespaces
    return _Namespaces.get(name)


def new(name, port=6568):
    global _Namespaces
    _Namespaces[name] = Namespace(name, port)
    return ns(name)


def erase(name):
    global _Namespaces
    return _Namespaces.pop(name, None)


def list_all():
    global _Namespaces
    return _Namespaces.keys()
    

class Namespace(object):
    def __init__(self, name, port=6568):
        self.name = name
        self.relay = 1
        self.base_difficulty = 3
        self.mining_threads = 1
        self.brokers = [
            {"ip": "185.65.200.231", "port": port},
            {"ip": "37.18.255.32",   "port": port},
        ]
        self.version = "0.2.2"
        self.host = "0.0.0.0"
        self.port = port
        self.timeout_connect = 3
        base_path = os.path.join(base_dir(), self.name)
        if not os.path.exists(base_path):
            os.makedirs(base_path)
        self.nodes = landerdb.Connect("nodes.db", base_path)
        self.wallet = landerdb.Connect("wallet.db", base_path)
        self.db = landerdb.Connect("db.db", base_path)

