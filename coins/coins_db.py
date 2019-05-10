#!/usr/bin/python
# coins_db.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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
..

module:: coins_db
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from __future__ import print_function
from six.moves import map
import six

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

import os

from twisted.internet import reactor  # @UnresolvedImport

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import sys
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg

from system import bpio

from main import settings

from coins import coins_index
from coins import coins_io

#------------------------------------------------------------------------------

if six.PY2:
    from CodernityDB.database import Database, RecordNotFound, RecordDeleted, PreconditionsException, DatabaseIsNotOpened
    from CodernityDB.index import IndexNotFoundException
else:
    from CodernityDB.database import Database, RecordNotFound, RecordDeleted, PreconditionsException, DatabaseIsNotOpened
    from CodernityDB.index import IndexNotFoundException    

#------------------------------------------------------------------------------

_LocalStorage = None

#------------------------------------------------------------------------------

def init():
    global _LocalStorage
    if _LocalStorage is not None:
        lg.warn('local storage already initialized')
        return
    contract_chain_dir = os.path.join(settings.ContractChainDir(), 'current')
    _LocalStorage = Database(contract_chain_dir)
    _LocalStorage.custom_header = coins_index.make_custom_header()
    if _Debug:
        lg.out(_DebugLevel, 'coins_db.init in %s' % contract_chain_dir)
    if db().exists():
        try:
            db().open()
        except:
            temp_dir = os.path.join(settings.ContractChainDir(), 'tmp')
            if os.path.isdir(temp_dir):
                bpio._dir_remove(temp_dir)
            tmpdb = regenerate_indexes(temp_dir)
            rewrite_indexes(db(), tmpdb)
            bpio._dir_remove(temp_dir)
            db().open()
            db().reindex()
    else:
        db().create()
    refresh_indexes(db())


def shutdown():
    global _LocalStorage
    if _LocalStorage is None:
        lg.warn('local storage is not initialized')
        return
    if _Debug:
        lg.out(_DebugLevel, 'coins_db.shutdown')
    try:
        _LocalStorage.close()
    except:
        pass
    _LocalStorage = None

#------------------------------------------------------------------------------

def db(instance='current'):
    global _LocalStorage
    return _LocalStorage

#------------------------------------------------------------------------------

def rewrite_indexes(db_instance, source_db_instance):
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'coins_db.rewrite_indexes')
    source_location = os.path.join(source_db_instance.path, '_indexes')
    source_indexes = os.listdir(source_location)
    existing_location = os.path.join(db_instance.path, '_indexes')
    existing_indexes = os.listdir(existing_location)
    for existing_index_file in existing_indexes:
        if existing_index_file != '00id.py':
            index_name = existing_index_file[2:existing_index_file.index('.')]
            existing_index_path = os.path.join(existing_location, existing_index_file)
            os.remove(existing_index_path)
            if _Debug:
                lg.out(_DebugLevel, '        removed index at %s' % existing_index_path)
            buck_path = os.path.join(db_instance.path, index_name + '_buck')
            if os.path.isfile(buck_path):
                os.remove(buck_path)
                if _Debug:
                    lg.out(_DebugLevel, '            also bucket at %s' % buck_path)
            stor_path = os.path.join(db_instance.path, index_name + '_stor')
            if os.path.isfile(stor_path):
                os.remove(stor_path)
                if _Debug:
                    lg.out(_DebugLevel, '            also storage at %s' % stor_path)
    for source_index_file in source_indexes:
        if source_index_file != '00id.py':
            index_name = source_index_file[2:source_index_file.index('.')]
            destination_index_path = os.path.join(existing_location, source_index_file)
            source_index_path = os.path.join(source_location, source_index_file)
            if not bpio.WriteTextFile(destination_index_path, bpio.ReadTextFile(source_index_path)):
                lg.warn('failed writing index to %s' % destination_index_path)
                continue
            destination_buck_path = os.path.join(db_instance.path, index_name + '_buck')
            source_buck_path = os.path.join(source_db_instance.path, index_name + '_buck')
            if not bpio.WriteBinaryFile(destination_buck_path, bpio.ReadBinaryFile(source_buck_path)):
                lg.warn('failed writing index bucket to %s' % destination_buck_path)
                continue
            destination_stor_path = os.path.join(db_instance.path, index_name + '_stor')
            source_stor_path = os.path.join(source_db_instance.path, index_name + '_stor')
            if not bpio.WriteBinaryFile(destination_stor_path, bpio.ReadBinaryFile(source_stor_path)):
                lg.warn('failed writing index storage to %s' % destination_stor_path)
                continue
            if _Debug:
                lg.out(_DebugLevel, '        wrote index %s from %s' % (index_name, source_index_path))


def refresh_indexes(db_instance):
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'coins_db.refresh_indexes in %s' % db_instance.path)
    for ind, ind_class in coins_index.definitions():
        ind_obj = ind_class(db_instance.path, ind)
        if ind not in db_instance.indexes_names:
            try:
                db_instance.add_index(ind_obj, create=True)
                if _Debug:
                    lg.out(_DebugLevel, '        added index %s' % ind)
            except:
                if _Debug:
                    lg.out(_DebugLevel, '        index skipped %s' % ind)
        else:
            db_instance.destroy_index(ind)
            db_instance.add_index(ind_obj, create=True)
            if _Debug:
                lg.out(_DebugLevel, '        updated index %s' % ind)


def regenerate_indexes(temp_dir):
    """
    """
    tmpdb = Database(temp_dir)
    tmpdb.custom_header = coins_index.make_custom_header()
    tmpdb.create()
    refresh_indexes(tmpdb)
    tmpdb.close()
    return tmpdb

#------------------------------------------------------------------------------

def to_list(ret):
    """
    """
    if ret and ret[0]:
        lst = list(ret[0])
        # print '\n'.join(map(str, lst))
        return lst
    else:
        # print ret[1]
        return ret[1]

#------------------------------------------------------------------------------ 

def get(index_name, key, with_doc=True, with_storage=True):
    # TODO: here and bellow need to add input validation
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

#------------------------------------------------------------------------------

def insert(coin_json):
    return db().insert(coin_json)


def remove(coin_json):
    # TODO: first need to lookup to get _id and _rev fields
    return db().delete()


def exist(coin_json):
#     if 'tm' in coin_json:
#         if not list(get('time', key=coin_json['tm'])):
#             return False
#     if 'idurl' in coin_json:
#         if not list(get('idurl', key=coin_json['idurl'])):
#             return False
#     if 'hash' in coin_json:
#         if not list(get('hash', key=coin_json['hash'])):
#             return False
#     return True
    return False

#------------------------------------------------------------------------------

def _clean_doc(doc):
    doc.pop('_id')
    doc.pop('_rev')
    return doc

#------------------------------------------------------------------------------

def query_json(jdata):
    """
    Input keys:

        + method: 'get', 'get_many' or 'get_all'
        + index: 'id', 'idurl', 'creator', etc.
        + key: key to read single record from db (optional)
        + start: low key limit to search records in range
        + end: high key limit to search records in range
        + offset: pagination offset
        + limit: pagination size

    Returns tuple:

        (generator object or None, error message)
    """
    if not db() or not db().opened:
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
        lg.exc()
        return None, 'exception raised during processing'
    if jdata['with_doc'] and index_name != 'id':
        return (_clean_doc(r['doc']) for r in result), None
    return result, None

#------------------------------------------------------------------------------

_prev_hash = ''

def _test_coin_worker(customer_idurl, duration, amount, price=1.0, trustee=None):
    global _prev_hash
    from coins import coins_miner
    storage_coin = coins_io.storage_contract_open(customer_idurl, duration, amount, price, trustee)
    storage_coin['miner']['prev'] = _prev_hash
    d = coins_miner.start_offline_job(storage_coin)
    d.addBoth(_test_coin_mined, customer_idurl, duration, amount, price, trustee)


def _test_coin_mined(coin_json, customer_idurl, duration, amount, price, trustee):
    global _prev_hash
    import json
    print('COIN MINED!!!')
    print(json.dumps(coin_json, indent=2))
    insert(coin_json)
    _prev_hash = coin_json['miner']['hash']
    reactor.callLater(1, _test_coin_worker, customer_idurl, duration, amount, price, trustee)
    return coin_json


def _test_query(inp):
    print('Query:')
    print(inp)
    print('===================================')
    lst = to_list(query_json(inp))
    print('\n'.join(map(str, lst)))
    print('total:', len(lst))
    return lst


def _test():
    if len(sys.argv) < 2:
        print("""
        commands:
        work <idurl> <duration> <amount>
        get_all <index>
        get_many <index> <key>
        get <index> <key>
        indexes
        tmpdb <destination folder>
        """)
        return

    if sys.argv[1] == 'work':
        init()
        _test_coin_worker(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
        reactor.run()
        shutdown()

    if sys.argv[1] == 'get_all':
        init()
        _test_query({
            'method': 'get_all',
            'index': sys.argv[2],
        })
        shutdown()

    if sys.argv[1] == 'get_many':
        init()
        _test_query({
            'method': 'get_many',
            'index': sys.argv[2],
            'key': sys.argv[3],
        })
        shutdown()

    if sys.argv[1] == 'get':
        init()
        _test_query({
            'method': 'get',
            'index': sys.argv[2],
            'key': sys.argv[3],
        })
        shutdown()

    if sys.argv[1] == 'indexes':
        init()
        print('Indexes in %s are:' % db().path)
        print('  ' + ('\n  '.join(db().indexes_names)))
        shutdown()

    if sys.argv[1] == 'tmpdb':
        regenerate_indexes(sys.argv[2])


if __name__ == "__main__":
    lg.set_debug_level(20)
    _test()
