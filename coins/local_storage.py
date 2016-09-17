#!/usr/bin/python
#local_storage.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (local_storage.py) is part of BitDust Software.
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
from CodernityDB.tree_index import TreeBasedIndex

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
        nodes_index = IndexByIDURL(db().path, 'idurl')
        coins_index = IndexByHash(db().path, 'hash')
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

#------------------------------------------------------------------------------ 

def get(index_name, key, with_doc=True, with_storage=True):
    return db().get(index_name, key, with_doc, with_storage)

def get_many(index_name, key, limit=-1, offset=0, start=None, end=None, with_doc=True, with_storage=True, **kwargs):
    return db().get_many(index_name, key, limit, offset, with_doc, with_storage, start, end, **kwargs)

def get_all(index_name, limit=-1, offset=0, with_doc=True, with_storage=True):
    return db().all(index_name, limit, offset, with_doc, with_storage)

#------------------------------------------------------------------------------ 

def query_from_json(jdata):
    method = jdata.pop('method', None)
    if method not in ['get', 'get_many', 'get_all',]:
        return None, 'unknown method'
    callmethod = globals().get(method)
    if not callmethod:
        return None, 'failed to call target method'
    index_name = jdata.pop('index', None)
    if index_name not in db().indexes_names:
        return None, 'unknown index'
    if 'with_doc' not in jdata:
        jdata['with_doc'] = True
    if 'with_storage' not in jdata:
        jdata['with_storage'] = True
    try:
        result = callmethod(index_name, **jdata)
    except:
        return None, lg.format_exception()
    def _clean_doc(doc):
        doc.pop('_id')
        doc.pop('_rev')
        return doc
    if jdata['with_doc'] and index_name != 'id':
        if method in ['get_many', 'get_all',]:
            return (_clean_doc(r['doc']) for r in result), ''
        else:
            return (_clean_doc(r['doc']) for r in [result,]), ''
    return result, ''

#------------------------------------------------------------------------------ 

class IndexByIDURL(HashIndex):

    def __init__(self, *args, **kwargs):
        kwargs['key_format'] = '16s'
        super(IndexByIDURL, self).__init__(*args, **kwargs)

    def make_key(self, key):
        return md5(key).digest()

    def make_key_value(self, data):
        idurl = data.get('idurl')
        if idurl:
            return md5(idurl).digest(), None
        return None
    

class IndexByHash(HashIndex):

    def __init__(self, *args, **kwargs):
        kwargs['key_format'] = '16s'
        super(IndexByHash, self).__init__(*args, **kwargs)

    def make_key(self, key):
        return key

    def make_key_value(self, data):
        hashval = data.get('hash')
        if hashval:
            return hashval, None
        return None

#------------------------------------------------------------------------------ 

def _test():

#     print db().insert({'idurl': 'http://idurl1234', 'time': '12345678'})
#     print db().insert({'hash': '1234567812345678' + random.choice(['a,b,c']), 'data': {'a':'b', 'c': 'd', 'time': 123456,}})
    
#     print 'query all from "id"'
#     for x in query_from_json({'method': 'get_all', 'index': 'id'})[0]:
#         print x
#    
#     print 'query all from "idurl"'
#     for x in query_from_json({'method': 'get_all', 'index': 'idurl'})[0]:
#         print x

    print 'query one from "idurl"'
    ret = query_from_json({'method': 'get', 'index': 'idurl', 'key': 'http://idurl1234'})
    for x in ret[0]:
        print x

#     print db().get('idurl', 'http://idurl1234')
    


if __name__ == "__main__":
    lg.set_debug_level(20)
    init()
    _test()
    shutdown()
    
