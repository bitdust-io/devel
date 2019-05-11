#!/usr/bin/python
# message_db.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (message_db.py) is part of BitDust Software.
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

module:: message_db
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from __future__ import print_function
from six.moves import map
import six

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

import os
import json

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import sys
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg

from system import bpio

from lib import utime

from crypt import key

from main import settings

from chat import message_index

from userid import my_id

#------------------------------------------------------------------------------

if six.PY2:
    from CodernityDB.database import (
        Database, RecordNotFound, RecordDeleted,
        IndexNotFoundException, DatabaseIsNotOpened,
        PreconditionsException, DatabaseConflict,
    )
    # from CodernityDB.database_super_thread_safe import SuperThreadSafeDatabase
else:
    from CodernityDB3.database import (
        Database, RecordNotFound, RecordDeleted,
        IndexNotFoundException, DatabaseIsNotOpened,
        PreconditionsException, DatabaseConflict,
    )
    # from CodernityDB3.database_super_thread_safe import SuperThreadSafeDatabase

#------------------------------------------------------------------------------

_LocalStorage = None

#------------------------------------------------------------------------------

def init(reindex=True, recreate=True):
    global _LocalStorage
    if _LocalStorage is not None:
        lg.warn('local storage already initialized')
        return
    chat_history_dir = os.path.join(settings.ChatHistoryDir(), 'current')
    # _LocalStorage = SuperThreadSafeDatabase(chat_history_dir)
    _LocalStorage = Database(chat_history_dir)
    _LocalStorage.custom_header = message_index.make_custom_header()
    if _Debug:
        lg.out(_DebugLevel, 'message_db.init in %s' % chat_history_dir)
    if db().exists():
        try:
            db().open()
        except:
            lg.exc()
            lg.err('failed to open database')
            if not recreate:
                raise Exception('failed to open database')
            lg.info('local DB will be recreated now')
            recreate_db(chat_history_dir)
    else:
        lg.info('create fresh local DB')
        db().create()
    if reindex:
        if not refresh_indexes(db()):
            lg.err('failed to refresh indexes')
            if not recreate:
                raise Exception('failed to refresh indexes')
            lg.info('local DB will be recreated')
            recreate_db(chat_history_dir)
            refresh_indexes(db())


def shutdown():
    global _LocalStorage
    if _LocalStorage is None:
        lg.warn('local storage is not initialized')
        return
    if _Debug:
        lg.out(_DebugLevel, 'message_db.shutdown')
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
        lg.out(_DebugLevel, 'message_db.rewrite_indexes')
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


def refresh_indexes(db_instance, rewrite=True, reindex=True):
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'message_db.refresh_indexes in %s' % db_instance.path)
    ok = True
    for ind, ind_class in message_index.definitions():
        ind_obj = ind_class(db_instance.path, ind)
        if ind not in db_instance.indexes_names:
            try:
                db_instance.add_index(ind_obj, create=True)
                if _Debug:
                    lg.out(_DebugLevel, '        added index %s' % ind)
            except:
                lg.exc('failed adding index "%r"' % ind)
        else:
            if rewrite:
                try:
                    # db_instance.destroy_index(ind)
                    # db_instance.add_index(ind_obj, create=True)
                    # db_instance.reindex_index(ind)
                    db_instance.edit_index(ind_obj, reindex=False)
                    if _Debug:
                        lg.out(_DebugLevel, '        updated index %s' % ind)
                except:
                    lg.exc('failed rewriting index "%r"' % ind)
    return ok


def regenerate_indexes(temp_dir):
    """
    """
    tmpdb = Database(temp_dir)
    tmpdb.custom_header = message_index.make_custom_header()
    tmpdb.create()
    refresh_indexes(tmpdb)
    tmpdb.close()
    lg.info('local DB indexes regenerated in %r' % temp_dir)
    return tmpdb


def recreate_db(chat_history_dir):
    """
    """
    global _LocalStorage
    temp_dir = os.path.join(settings.ChatHistoryDir(), 'tmp')
    if os.path.isdir(temp_dir):
        bpio._dir_remove(temp_dir)
    tmpdb = regenerate_indexes(temp_dir)
    try:
        db().close()
    except:
        pass
    rewrite_indexes(db(), tmpdb)
    bpio._dir_remove(temp_dir)
    try:
        db().open()
        db().reindex()
    except:
        # really bad... we will lose whole data
        _LocalStorage = Database(chat_history_dir)
        _LocalStorage.custom_header = message_index.make_custom_header()
        try:
            _LocalStorage.destroy()
        except:
            pass
        try:
            _LocalStorage.create()
        except Exception as exc:
            lg.warn('failed to create local storage: %r' % exc)
    lg.info('local DB re-created in %r' % chat_history_dir)

#------------------------------------------------------------------------------

def _to_list(ret):
    """
    """
    if ret and ret[0]:
        lst = list(ret[0])
        # print '\n'.join(map(str, lst))
        return lst
    else:
        # print ret[1]
        return ret[1]

def _clean_doc(doc):
    doc.pop('_id')
    doc.pop('_rev')
    return doc

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

def insert(message_json):
    return db().insert(message_json)


def remove(message_json):
    # TODO: first need to lookup to get _id and _rev fields
    # return db().delete(...)
    return False


def exist(message_json):
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

def search(query_json):
    try:
        for r in db().all('id', with_doc=True, with_storage=True):
            if 'body' in query_json:
                if r['payload']['body'].count(query_json['body']):
                    yield r
    except (PreconditionsException, IndexNotFoundException, DatabaseIsNotOpened, ):
        pass

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

def message_to_string(coin_json):
    return json.dumps(coin_json, sort_keys=True)


def get_message_hash(message_json):
    coin_hashbase = message_to_string(message_json)
    return key.Hash(coin_hashbase, hexdigest=True)


def build_json_message(data, message_id, sender=None, recipient=None):
    """
    """
    if not sender:
        sender = my_id.getGlobalID(key_alias='master')
    if not recipient:
        recipient = my_id.getGlobalID(key_alias='master')
    new_json = {
        "payload": {
            "type": "message",
            "message_id": message_id,
            "time": utime.utcnow_to_sec1970(),
            "data": data,
        },
        'sender': {
            'glob_id': sender,
        },
        'recipient': {
            'glob_id': recipient,
        }
    }
    return new_json

#------------------------------------------------------------------------------

def _test_query(inp):
    print('Query:')
    print(inp)
    print('===================================')
    lst = _to_list(query_json(inp))
    print('\n'.join(map(str, lst)))
    print('total:', len(lst))
    return lst


def main():
    if len(sys.argv) < 2:
        print("""
        commands:
        get_all <index>
        get_many <index> <key>
        get <index> <key>
        insert "message body" "message id"
        search "json query"
        indexes
        tmpdb <destination folder>
        """)
        return

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

    if sys.argv[1] == 'refresh':
        print('ReIndexing')
        init()
        refresh_indexes(db())
        shutdown()

    if sys.argv[1] == 'tmpdb':
        regenerate_indexes(sys.argv[2])

    if sys.argv[1] == 'insert':
        init()
        print(insert(build_json_message(data=sys.argv[2], message_id=sys.argv[3])))
        shutdown()

    if sys.argv[1] == 'search':
        init()
        print('\n'.join(map(str, [m for m in search(json.loads(sys.argv[2]))])))
        shutdown()


if __name__ == "__main__":
    lg.set_debug_level(20)
    main()
