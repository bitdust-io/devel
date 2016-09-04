#!/usr/bin/python
#local_storage.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: local_storage

"""

_Debug = True

#------------------------------------------------------------------------------ 

import os
import random
from hashlib import md5

from CodernityDB.database import Database
from CodernityDB.hash_index import HashIndex
from CodernityDB.hash_index import UniqueHashIndex

#------------------------------------------------------------------------------ 

if __name__ == '__main__':
    import sys, os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------ 

from logs import lg

from main import settings

#------------------------------------------------------------------------------ 

_LocalStorage = None

#------------------------------------------------------------------------------ 

def init():
    global _LocalStorage
    if _LocalStorage is not None:
        lg.warn('local storage already initialized')
        return
    _LocalStorage = Database(os.path.join(settings.BlockChainDir(), 'current'))
    if db().exists():
        db().open()
    else:
        id_index = UniqueHashIndex(db().path, 'id')
        nodes_index = AllNodes(db().path, 'nodes')
        coins_index = AllCoins(db().path, 'coins')
        db().set_indexes([id_index, nodes_index, coins_index])
        db().create()
    
    
def shutdown():
    global _LocalStorage
    if _LocalStorage is None:
        lg.warn('local storage is not initialized')
        return
    _LocalStorage.close()
    _LocalStorage = None

#------------------------------------------------------------------------------ 

def db():
    global _LocalStorage
    return _LocalStorage

def write_coin(data):
    return db().insert(data)
    
def read_coin(coinhash):
    return db().get('coins', coinhash, with_doc=True, with_storage=True)
    
def read_coins():
    return db().all('coins', with_doc=True, with_storage=True)

def read_items():
    return db().all('id', with_doc=True, with_storage=True)

#------------------------------------------------------------------------------ 

class AllNodes(HashIndex):

    def __init__(self, *args, **kwargs):
        kwargs['key_format'] = '16s'
        super(AllNodes, self).__init__(*args, **kwargs)

    def make_key(self, key):
        return md5(key).digest()

    def make_key_value(self, data):
        if data.get('idurl'):
            return md5(data.get('idurl')).digest(), None
        return None
    

class AllCoins(HashIndex):

    def __init__(self, *args, **kwargs):
        kwargs['key_format'] = '16s'
        super(AllCoins, self).__init__(*args, **kwargs)

    def make_key(self, key):
        return md5(key).digest()

    def make_key_value(self, data):
        if data.get('hash'):
            return md5(data.get('hash')).digest(), None
        return None

#------------------------------------------------------------------------------ 

def _test():
    # print db().count(db().all, 'id')
    # print db().insert({'idurl': 'http://idurl1234',
    #              'time': '12345678'})
    # print db().insert({'hash': '1234567812345678' + random.choice(['a,b,c']), 
    #              'data': {'a':'b', 'c': 'd',
    #              'time': 123456,}})
    # import pdb
    # pdb.set_trace()
    # v = read_coin('1234567812345678')
    # print v
    
    for x in read_items():
        print x
        
    # print [x for x in read_coins()]
    
    # print read_coin('1234567812345678a,b,c')
    

if __name__ == "__main__":
    lg.set_debug_level(20)
    init()
    _test()
    shutdown()
    
