#!/usr/bin/python
# coins_db.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (coins_db.py) is part of BitDust Software.
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
.. module:: coins_db

"""

#------------------------------------------------------------------------------

_Debug = True

#------------------------------------------------------------------------------

import os
import json
from hashlib import md5

from CodernityDB.database import Database, RecordNotFound, RecordDeleted, PreconditionsException, DatabaseIsNotOpened
from CodernityDB.hash_index import HashIndex
from CodernityDB.tree_index import TreeBasedIndex
from CodernityDB.index import IndexNotFoundException

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import sys
    import os.path as _p
    sys.path.insert(
        0, _p.abspath(
            _p.join(
                _p.dirname(
                    _p.abspath(
                        sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg

from main import settings

from crypt import key

#------------------------------------------------------------------------------

_LocalStorage = None

#------------------------------------------------------------------------------


def indexes():
    return {
        'owner': IndexByOwnerIDURL,
        'hash': IndexByHash,
        'prev': IndexByPrevHash,
        'time': IndexByTime,
        'miner': IndexByMinerIDURL,
    }


def refresh_indexes():
    for ind, ind_class in indexes().items():
        ind_obj = ind_class(db().path, ind)
        if ind not in db().indexes_names:
            db().add_index(ind_obj, create=True)
        else:
            db().edit_index(ind_obj, reindex=True)

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
        db().create()
    refresh_indexes()


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


def get(index_name, key, with_doc=True, with_storage=True):
    try:
        res = db().get(index_name, key, with_doc, with_storage)
    except (RecordNotFound, RecordDeleted, ):
        return iter(())
    except (IndexNotFoundException, DatabaseIsNotOpened, ):
        return iter(())
    return (r for r in [res, ])


def get_many(index_name, key=None, limit=-1, offset=0,
             start=None, end=None,
             with_doc=True, with_storage=True, **kwargs):
    try:
        for r in db().get_many(index_name, key, limit, offset,
                               with_doc, with_storage,
                               start, end, **kwargs):
            yield r
    except (PreconditionsException, IndexNotFoundException, DatabaseIsNotOpened, ):
        pass


def get_all(index_name, limit=-1, offset=0, with_doc=True, with_storage=True):
    try:
        for r in db().all(index_name, limit, offset, with_doc, with_storage):
            yield r
    except (PreconditionsException, IndexNotFoundException, DatabaseIsNotOpened):
        pass


def insert(acoin):
    return db().insert(acoin)


def exist(acoin):
    if 'tm' in acoin:
        if not list(get('time', key=acoin['tm'])):
            return False
    if 'idurl' in acoin:
        if not list(get('idurl', key=acoin['idurl'])):
            return False
    if 'hash' in acoin:
        if not list(get('hash', key=acoin['hash'])):
            return False
    return True

#------------------------------------------------------------------------------


def _clean_doc(doc):
    doc.pop('_id')
    doc.pop('_rev')
    return doc


def query_json(jdata):
    """
    Input keys:
        method: 'get', 'get_many' or 'get_all'
        index: 'id', 'idurl', etc.
        key: key to read single record from db (optional)
        start: low key limit to search records in range
        end: high key limit to search records in range
    Returns tuple:
        generator object or None, error message
    """
    if not db().opened:
        return None, 'database is closed'
    method = jdata.pop('method', None)
    if method not in ['get', 'get_many', 'get_all', ]:
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
    if jdata['with_doc'] and index_name != 'id':
        return (_clean_doc(r['doc']) for r in result), ''
    return result, ''

#------------------------------------------------------------------------------


class IndexByTime(TreeBasedIndex):

    def __init__(self, *args, **kwargs):
        kwargs['key_format'] = 'I'
        kwargs['node_capacity'] = 128
        super(IndexByTime, self).__init__(*args, **kwargs)

    def make_key(self, key):
        return key

    def make_key_value(self, data):
        tm = data.get('tm')
        if tm:
            return tm, None
        return None


class IndexByOwnerIDURL(HashIndex):

    def __init__(self, *args, **kwargs):
        kwargs['key_format'] = '16s'
        super(IndexByOwnerIDURL, self).__init__(*args, **kwargs)

    def make_key(self, key):
        return md5(key).digest()

    def make_key_value(self, data):
        idurl = data.get('data', dict()).get('owner')
        if idurl:
            return md5(idurl).digest(), None
        return None


class IndexByMinerIDURL(HashIndex):

    def __init__(self, *args, **kwargs):
        kwargs['key_format'] = '16s'
        super(IndexByMinerIDURL, self).__init__(*args, **kwargs)

    def make_key(self, key):
        return md5(key).digest()

    def make_key_value(self, data):
        miner_idurl = data.get('data', dict()).get('miner')
        if miner_idurl:
            return md5(miner_idurl).digest(), None
        return None


class IndexByHash(HashIndex):

    def __init__(self, *args, **kwargs):
        kwargs['key_format'] = '40s'
        super(IndexByHash, self).__init__(*args, **kwargs)

    def make_key(self, key):
        return key

    def make_key_value(self, data):
        hashval = data.get('hash')
        if hashval:
            return hashval
        return None


class IndexByPrevHash(HashIndex):

    def __init__(self, *args, **kwargs):
        kwargs['key_format'] = '40s'
        super(IndexByHash, self).__init__(*args, **kwargs)

    def make_key(self, key):
        return key

    def make_key_value(self, data):
        hashval = data.get('prev')
        if hashval:
            return hashval
        return None

#------------------------------------------------------------------------------


def _test():
    from lib import utime
    import time
    import datetime

    def _p(ret):
        if ret and ret[0]:
            print '\n'.join(map(str, list(ret[0])))
        else:
            print ret[1]

#     print insert({'idurl': 'http://idurl1234', 'time': '12345678'})
# print insert({'hash': '1234567812345678' + random.choice(['a,b,c']),
# 'data': {'a':'b', 'c': 'd', 'time': 123456,}})

#     print insert({'idurl': 'http://veselin-p2p.ru/veselin_kpn.xml',
#                   'hash': 'abcdef',
#                   'tm': utime.since1970(datetime.datetime.utcnow())})
#
#     time.sleep(3)
#
#     print insert({'idurl': 'http://veselin-p2p.ru/veselin_kpn123.xml',
#                   'hash': 'abcdef123',
#                   'tm': utime.since1970(datetime.datetime.utcnow())})
#
#     time.sleep(4)
#
#     print insert({'idurl': 'http://veselin-p2p.ru/veselin_kpn567.xml',
#                   'hash': 'abcdef567',
#                   'tm': utime.since1970(datetime.datetime.utcnow())})

#     print 'query all from "id"'
#     for x in query_from_json({'method': 'get_all', 'index': 'id'})[0]:
#         print x
#
#     print 'query all from "idurl"'
#     for x in query_from_json({'method': 'get_all', 'index': 'idurl'})[0]:
#         print x

    print 'query one from "hash"'
    _p(query_json({'method': 'get', 'index': 'hash', 'key': 'abcdef123', }))

    print 'query many from "hash"'
    _p(query_json({'method': 'get_many',
                   'index': 'hash', 'key': 'abcdef123', }))

    print 'query one from "time"'
    _p(query_json({'method': 'get', 'index': 'time', 'key': 1474380456, }))

    print 'query one from "idurl"'
    _p(query_json({'method': 'get', 'index': 'idurl',
                   'key': 'http://veselin-p2p.ru/veselin_kpn123.xml'}))

    print 'query some from "time"'
    _p(query_json({'method': 'get_many', 'index': 'time',
                   'limit': 3, 'offset': 2, 'start': 0, 'end': None, }))

    print 'query all from "hash"'
    _p(query_json({'method': 'get_all', 'index': 'hash'}))

    print 'query some from "time"'
    _p(query_json({'method': 'get_many', 'index': 'time', 'key': 1474380456, }))

    print 'query one from "id"'
    _p(query_json({'method': 'get', 'index': 'id',
                   'key': '5d909de518db44329183d187927cabc9', }))

    print 'query all from "id"'
    _p(query_json({'method': 'get_all', 'index': 'id'}))

    print 'test item exists:', exist({'tm': 1474380456,
                                      'hash': 'abcdef123',
                                      'idurl': 'http://veselin-p2p.ru/veselin_kpn123.xml'})


if __name__ == "__main__":
    lg.set_debug_level(20)
    init()
    _test()
    shutdown()
