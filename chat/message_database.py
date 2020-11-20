#!/usr/bin/python
# message_database.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (message_database.py) is part of BitDust Software.
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

module:: message_database
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from __future__ import print_function

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

import os
import json
import sqlite3

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import sys
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg

from lib import utime
from lib import strng

from main import settings
from main import events

from crypt import my_keys

from userid import my_id

#------------------------------------------------------------------------------

_HistoryDB = None
_HistoryCursor = None

#------------------------------------------------------------------------------

MESSAGE_TYPES = {
    'message': 1,
    'private_message': 2,
    'group_message': 3,
    'personal_message': 4,
}

MESSAGE_TYPE_CODES = {
    1: 'message',
    2: 'private_message',
    3: 'group_message',
    4: 'personal_message',
}

#------------------------------------------------------------------------------

def init(filepath=None):
    """
    """
    global _HistoryDB
    global _HistoryCursor

    if not filepath:
        filepath = settings.ChatMessagesHistoryDatabaseFile()

    if _Debug:
        lg.args(_DebugLevel, filepath=filepath)

    sqlite3.register_adapter(dict, adapt_json)
    sqlite3.register_adapter(list, adapt_json)
    sqlite3.register_adapter(tuple, adapt_json)
    sqlite3.register_converter('JSON', convert_json)

    if not os.path.isfile(filepath):
        _HistoryDB = sqlite3.connect(filepath, timeout=1)
        _HistoryDB.execute('PRAGMA case_sensitive_like = 1;')
        _HistoryCursor = _HistoryDB.cursor()

        _HistoryCursor.execute('''CREATE TABLE IF NOT EXISTS "history" (
            "sender_local_key_id" INTEGER,
            "recipient_local_key_id" INTEGER,
            "payload_type" INTEGER,
            "payload_time" INTEGER,
            "payload_message_id" TEXT,
            "payload_body" JSON)''')
        _HistoryCursor.execute('CREATE INDEX "sender local key id" on history(sender_local_key_id)')
        _HistoryCursor.execute('CREATE INDEX "recipient local key id" on history(recipient_local_key_id)')

        _HistoryCursor.execute('''CREATE TABLE IF NOT EXISTS "conversations" (
            "conversation_id" TEXT,
            "payload_type" INTEGER,
            "started_time" INTEGER,
            "last_updated_time" INTEGER,
            "last_message_id" TEXT)''')
        _HistoryCursor.execute('CREATE INDEX "conversation id" on conversations(conversation_id)')

        _HistoryCursor.execute('''CREATE TABLE IF NOT EXISTS "keys" (
            "key_id" TEXT,
            "local_key_id" INTEGER,
            "public_key" TEXT)''')
        _HistoryCursor.execute('CREATE INDEX "key id" on keys(key_id)')
        _HistoryCursor.execute('CREATE INDEX "local key id" on keys(local_key_id)')
        _HistoryCursor.execute('CREATE INDEX "public key" on keys(public_key)')

        _HistoryDB.commit()
        _HistoryDB.close()

    _HistoryDB = sqlite3.connect(filepath, timeout=1)
    _HistoryDB.text_factory = str
    _HistoryDB.execute('PRAGMA case_sensitive_like = 1;')
    _HistoryDB.commit()
    _HistoryCursor = _HistoryDB.cursor()

    events.add_subscriber(on_key_registered, 'key-registered')


def shutdown():
    """
    """
    global _HistoryDB
    global _HistoryCursor
    if _Debug:
        lg.dbg(_DebugLevel, '')

    events.remove_subscriber(on_key_registered, 'key-registered')

    _HistoryDB.commit()
    _HistoryDB.close()
    _HistoryDB = None
    _HistoryCursor = None

#------------------------------------------------------------------------------

def db(instance='current'):
    global _HistoryDB
    return _HistoryDB


def cur(instance='current'):
    global _HistoryCursor
    return _HistoryCursor

#------------------------------------------------------------------------------

def adapt_json(data):
    return (json.dumps(data, sort_keys=True)).encode()

def convert_json(blob):
    return json.loads(blob.decode())

#------------------------------------------------------------------------------

def build_json_message(data, message_id, message_time=None, sender=None, recipient=None, message_type=None, direction=None):
    """
    """
    if not sender:
        sender = my_id.getGlobalID(key_alias='master')
    if not recipient:
        recipient = my_id.getGlobalID(key_alias='master')
    if direction is None and message_type in ['private_message', None, ]:
        direction = 'out' if sender == my_id.getGlobalID(key_alias='master') else 'in'
    new_json = {
        "payload": {
            "type": message_type or "message",
            "message_id": strng.to_text(message_id),
            "time": message_time or utime.utcnow_to_sec1970(),
            "data": data,
        },
        'sender': {
            'glob_id': sender,
        },
        'recipient': {
            'glob_id': recipient,
        },
        'direction': direction,
    }
    return new_json

#------------------------------------------------------------------------------

def insert_message(message_json):
    """
    Writes JSON message to the message database.
    """
    try:
        sender_glob_id = message_json['sender']['glob_id']
        recipient_glob_id = message_json['recipient']['glob_id']
        payload_type = MESSAGE_TYPES.get(message_json['payload']['type'], 1)
        payload_time = message_json['payload']['time']
        payload_message_id = message_json['payload']['message_id']
        payload_body =  message_json['payload']['data']
        # TODO: store "direction"
        # direction = message_json['direction']
    except:
        lg.exc()
        return False
    if _Debug:
        lg.args(_DebugLevel, sender=sender_glob_id, recipient=recipient_glob_id, typ=payload_type, message_id=payload_message_id)
    recipient_local_key_id = my_keys.get_local_key_id(recipient_glob_id)
    if payload_type in [3, 4, ]:
        sender_local_key_id = recipient_local_key_id
    else:
        sender_local_key_id = my_keys.get_local_key_id(sender_glob_id)
    if sender_local_key_id is None or recipient_local_key_id is None:
        lg.err('failed to store message because local_key_id is not found, sender=%r recipient=%r' % (
            sender_local_key_id, recipient_local_key_id, ))
        return False
    cur().execute('''INSERT INTO history (
            sender_local_key_id,
            recipient_local_key_id,
            payload_type,
            payload_time,
            payload_message_id,
            payload_body
        ) VALUES (?, ?, ?, ?, ?, ?)''', (
        sender_local_key_id,
        recipient_local_key_id,
        payload_type,
        payload_time,
        payload_message_id,
        payload_body,
    ))
    db().commit()
    update_conversation(sender_local_key_id, recipient_local_key_id, payload_type, payload_time, payload_message_id)
    return True


def update_conversation(sender_local_key_id, recipient_local_key_id, payload_type, payload_time, payload_message_id):
    conversation_id = None
    if payload_type in [3, 4, ]:
        conversation_id = '{}&{}'.format(recipient_local_key_id, recipient_local_key_id)
    elif payload_type == 2:
        if recipient_local_key_id < sender_local_key_id:
            conversation_id = '{}&{}'.format(recipient_local_key_id, sender_local_key_id)
        else:
            conversation_id = '{}&{}'.format(sender_local_key_id, recipient_local_key_id)
    else:
        lg.err('unexpected message type: %r' % payload_type)
        return
    if conversation_id is None:
        lg.err('failed to update conversation, local_key_id was not found')
        return
    sql = 'SELECT * FROM conversations WHERE conversation_id=?'
    params = [conversation_id, ]
    found_conversation = list(cur().execute(sql, params))
    if found_conversation:
        sql = 'UPDATE conversations SET last_updated_time=?, last_message_id=? WHERE conversation_id=?'
        params = [payload_time, payload_message_id, conversation_id, ]
    else:
        sql = 'INSERT INTO conversations (conversation_id, payload_type, started_time, last_updated_time, last_message_id) VALUES (?, ?, ?, ?, ?)'
        params = [conversation_id, payload_type, payload_time, payload_time, payload_message_id, ]
    if _Debug:
        lg.args(_DebugLevel, conversation_id=conversation_id, found_conversation=len(found_conversation), params=params)
    cur().execute(sql, params)
    db().commit()
    return True


def query_messages(sender_id=None, recipient_id=None, bidirectional=True, order_by_time=True, message_types=[], offset=None, limit=None):
    """
    """
    sql = 'SELECT * FROM history'
    q = ''
    params = []
    if bidirectional and sender_id and recipient_id:
        recipient_local_key_id = my_keys.get_local_key_id(recipient_id)
        sender_local_key_id = my_keys.get_local_key_id(sender_id)
        if recipient_local_key_id is None or sender_local_key_id is None:
            lg.warn('local_key_id was not found, recipient_local_key_id=%r sender_local_key_id=%r' % (recipient_local_key_id, sender_local_key_id, ))
            return []
        q += ' sender_local_key_id IN (?, ?) AND recipient_local_key_id IN (?, ?)'
        params += [sender_local_key_id, recipient_local_key_id, sender_local_key_id, recipient_local_key_id, ]
    else:
        if sender_id:
            sender_local_key_id = my_keys.get_local_key_id(sender_id)
            if sender_local_key_id is None:
                lg.warn('local_key_id was not found for sender %r' % sender_id)
                return []
            q += ' sender_local_key_id=?'
            params += [sender_local_key_id, ]
        if recipient_id:
            recipient_local_key_id = my_keys.get_local_key_id(recipient_id)
            if recipient_local_key_id is None:
                lg.warn('local_key_id was not found for recipient %r' % recipient_id)
                return []
            q += ' recipient_local_key_id=?'
            params += [recipient_local_key_id, ]
    if message_types:
        if params:
            q += ' AND payload_type IN (%s)' % (','.join(['?', ] * len(message_types)))
        else:
            q += ' payload_type IN (%s)' % (','.join(['?', ] * len(message_types)))
        params.extend([MESSAGE_TYPES.get(mt, 1) for mt in message_types])
    if q:
        sql += ' WHERE %s' % q
    if order_by_time:
        sql += ' ORDER BY payload_time DESC'
    if limit is not None:
        sql += ' LIMIT ?'
        params += [limit, ]
    if offset is not None:
        sql += ' OFFSET ?'
        params += [offset, ]
    if _Debug:
        lg.args(_DebugLevel, sql=sql, params=params)
    results = []
    local_key_ids = {}
    for row in cur().execute(sql, params):
        sender_local_key_id = row[0]
        recipient_local_key_id = row[1]
        if sender_local_key_id not in local_key_ids:
            local_key_ids[sender_local_key_id] = my_keys.get_local_key(sender_local_key_id)
        if recipient_local_key_id not in local_key_ids:
            local_key_ids[recipient_local_key_id] = my_keys.get_local_key(recipient_local_key_id)
        if not local_key_ids.get(sender_local_key_id) or not local_key_ids.get(recipient_local_key_id):
            lg.warn('unknown sender or recipient local key_id')
            continue
        json_msg = build_json_message(
            data=json.loads(row[5]),
            message_id=row[4],
            message_time=row[3],
            sender=local_key_ids[sender_local_key_id],
            recipient=local_key_ids[recipient_local_key_id],
            message_type=MESSAGE_TYPE_CODES.get(int(row[2]), 'private_message'),
        )
        if order_by_time:
            results.insert(0, json_msg)
        else:
            results.append(json_msg)
    return results


def list_conversations(order_by_time=True, message_types=[], offset=None, limit=None):
    sql = 'SELECT * FROM conversations'
    q = ''
    params = []
    if message_types:
        q += ' payload_type IN (%s)' % (','.join(['?', ] * len(message_types)))
        params.extend([MESSAGE_TYPES.get(mt, 1) for mt in message_types])
    if q:
        sql += ' WHERE %s' % q
    if order_by_time:
        sql += ' ORDER BY last_updated_time DESC'
    if limit is not None:
        sql += ' LIMIT ?'
        params += [limit, ]
    if offset is not None:
        sql += ' OFFSET ?'
        params += [offset, ]
    if _Debug:
        lg.args(_DebugLevel, sql=sql, params=params)
    results = []
    for row in cur().execute(sql, params):
        results.append(dict(
            conversation_id=row[0],
            type=MESSAGE_TYPE_CODES.get(int(row[1]), 'private_message'), 
            started=row[2],
            last_updated=row[3],
            last_message_id=row[4],
        ))
    return results


#------------------------------------------------------------------------------

def update_history_with_new_local_key_id(old_id, new_id):
    sql = 'UPDATE history SET sender_local_key_id=? WHERE sender_local_key_id=?'
    params = [new_id, old_id, ]
    cur().execute(sql, params)
    db().commit()
    if _Debug:
        lg.args(_DebugLevel, sql=sql, params=params)
    sql = 'UPDATE history SET recipient_local_key_id=? WHERE recipient_local_key_id=?'
    params = [new_id, old_id, ]
    cur().execute(sql, params)
    db().commit()
    if _Debug:
        lg.args(_DebugLevel, sql=sql, params=params)


def update_conversations_with_new_local_key_id(old_id, new_id):
    sql = 'SELECT * FROM conversations'
    params = []
    modifications = {}
    for row in cur().execute(sql, params):
        conversation_id = row[0]
        new_conversation_id = conversation_id
        id1, _, id2 = conversation_id.partition('&')
        try:
            id1 = int(id1)
            id2 = int(id2)
        except:
            lg.exc()
            continue
        if id1 == old_id:
            new_conversation_id = '{}&{}'.format(new_id, id2)
        if id2 == old_id:
            new_conversation_id = '{}&{}'.format(id1, new_id)
        if conversation_id != new_conversation_id:
            modifications[conversation_id] = new_conversation_id
    if _Debug:
        lg.args(_DebugLevel, modifications=modifications)
    for old_conv_id, new_conv_id in modifications.items():
        sql = 'UPDATE conversations SET conversation_id=? WHERE conversation_id=?'
        params = [new_conv_id, old_conv_id, ]
        cur().execute(sql, params)
        db().commit()
        if _Debug:
            lg.args(_DebugLevel, sql=sql, params=params)



# def rebuild_conversations():    
#     cur().execute('SELECT count(name) FROM sqlite_master WHERE type="table" AND name="conversations"')
#     if cur().fetchone()[0]:
#         return
#     cur().execute('''CREATE TABLE IF NOT EXISTS "conversations" (
#         "conversation_id" TEXT,
#         "payload_type" INTEGER,
#         "started_time" INTEGER,
#         "last_updated_time" INTEGER,
#         "last_message_id" TEXT)''')
#     cur().execute('CREATE INDEX "conversation id" on conversations(conversation_id)')
#     db().commit()
#     for message_json in list(query_messages()):
#         payload_type = MESSAGE_TYPES.get(message_json['payload']['type'], 1)
#         recipient_local_key_id = my_keys.get_local_key_id(message_json['recipient']['glob_id'])
#         if payload_type in [3, 4, ]:
#             sender_local_key_id = recipient_local_key_id
#         else:
#             sender_local_key_id = my_keys.get_local_key_id(message_json['sender']['glob_id'])
#         update_conversation(
#             sender_local_key_id=sender_local_key_id,
#             recipient_local_key_id=recipient_local_key_id,
#             payload_type=payload_type,
#             payload_time=message_json['payload']['time'],
#             payload_message_id=message_json['payload']['message_id'],
#         )

#------------------------------------------------------------------------------

def on_key_registered(evt):
    new_key_id = evt.data['key_id']
    try:
        new_public_key = my_keys.get_public_key_raw(new_key_id)
    except:
        lg.exc()
        return
    try:
        new_local_key_id = my_keys.get_local_key_id(new_key_id)
    except:
        lg.exc()
        return
    if new_local_key_id is None:
        lg.err('did not found local_key_id for %r' % new_key_id)
        return
    sql = 'SELECT * FROM keys WHERE public_key=?'
    params = [new_public_key, ]
    found_public_keys = list(cur().execute(sql, params))
    if found_public_keys:
        key_id = found_public_keys[0][0]
        local_key_id = found_public_keys[0][1]
        if key_id != new_key_id:
            sql = 'UPDATE keys SET key_id=? WHERE public_key=?'
            params = [new_key_id, new_public_key, ]
            cur().execute(sql, params)
            db().commit()
            if _Debug:
                lg.args(_DebugLevel, sql=sql, params=params)
        if local_key_id != new_local_key_id:
            lg.warn('found new public key which is re-using already known key with different local key id: %r -> %r' % (
                local_key_id, new_local_key_id, ))
            update_history_with_new_local_key_id(local_key_id, new_local_key_id)
            update_conversations_with_new_local_key_id(local_key_id, new_local_key_id)
            sql = 'UPDATE keys SET local_key_id=? WHERE public_key=?'
            params = [new_local_key_id, new_public_key, ]
            cur().execute(sql, params)
            db().commit()
            if _Debug:
                lg.args(_DebugLevel, sql=sql, params=params)
    else:
        sql = 'INSERT INTO keys (key_id, local_key_id, public_key) VALUES (?, ?, ?)'
        params = [new_key_id, new_local_key_id, new_public_key, ]
        cur().execute(sql, params)
        db().commit()
        if _Debug:
            lg.args(_DebugLevel, sql=sql, params=params)

#------------------------------------------------------------------------------

def main():
    import pprint
    my_keys.init()
    init()
    pprint.pprint(list(query_messages(
        sender_id='',
        recipient_id='',
        offset=2,
        limit=3,
    )))
    pprint.pprint(list(list_conversations(
        # message_types=['group_message', ]
    )))
    shutdown()


if __name__ == "__main__":
    lg.set_debug_level(20)
    main()
