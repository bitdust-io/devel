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

_Debug = False
_DebugLevel = 10

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

from bitdust.logs import lg

from bitdust.lib import utime
from bitdust.lib import strng

from bitdust.main import settings
from bitdust.main import listeners

from bitdust.crypt import my_keys

from bitdust.access import group_participant

from bitdust.p2p import online_status

from bitdust.userid import global_id
from bitdust.userid import id_url
from bitdust.userid import my_id

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

        _HistoryCursor.execute(
            '''CREATE TABLE IF NOT EXISTS "history" (
            "sender_local_key_id" INTEGER,
            "sender_id" TEXT,
            "recipient_local_key_id" INTEGER,
            "recipient_id" TEXT,
            "direction" INTEGER,
            "payload_type" INTEGER,
            "payload_time" INTEGER,
            "payload_message_id" TEXT,
            "payload_body" JSON)''',
        )
        _HistoryCursor.execute('CREATE INDEX "sender local key id" on history(sender_local_key_id)')
        _HistoryCursor.execute('CREATE INDEX "recipient local key id" on history(recipient_local_key_id)')

        _HistoryCursor.execute(
            '''CREATE TABLE IF NOT EXISTS "conversations" (
            "conversation_id" TEXT,
            "payload_type" INTEGER,
            "started_time" INTEGER,
            "last_updated_time" INTEGER,
            "last_message_id" TEXT)''',
        )
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

    check_create_keys()


def shutdown():
    global _HistoryDB
    global _HistoryCursor
    if _Debug:
        lg.dbg(_DebugLevel, '')

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


def get_conversation_id(sender_local_key_id, recipient_local_key_id, payload_type):
    conversation_id = None
    if payload_type in [3, 4]:
        conversation_id = '{}&{}'.format(recipient_local_key_id, recipient_local_key_id)
    elif payload_type == 2:
        if recipient_local_key_id < sender_local_key_id:
            conversation_id = '{}&{}'.format(recipient_local_key_id, sender_local_key_id)
        else:
            conversation_id = '{}&{}'.format(sender_local_key_id, recipient_local_key_id)
    else:
        lg.err('unexpected message type: %r' % payload_type)
        return None
    return conversation_id


#------------------------------------------------------------------------------


def build_json_message(data, message_id, message_time=None, sender=None, recipient=None, message_type=None, direction=None, conversation_id=None):
    if not sender:
        sender = my_id.getGlobalID(key_alias='master')
    if not recipient:
        recipient = my_id.getGlobalID(key_alias='master')
    if direction is None:
        if message_type in ['private_message', None]:
            direction = 'out' if sender == my_id.getGlobalID(key_alias='master') else 'in'
        else:
            direction = 'in'
    else:
        direction = direction.replace('incoming', 'in').replace('outgoing', 'out')
    new_json = {
        'payload': {
            'msg_type': message_type or 'message',
            'message_id': strng.to_text(message_id),
            'time': message_time or utime.utcnow_to_sec1970(),
            'data': data,
        },
        'sender': {
            'glob_id': sender,
        },
        'recipient': {
            'glob_id': recipient,
        },
        'direction': direction,
        'conversation_id': conversation_id,
    }
    return new_json


def build_json_conversation(**record):
    conv = {
        'key_id': '',
        'label': '',
        'state': 'DISCONNECTED',
        'index': None,
        'id': None,
        'name': None,
        'events': None,
    }
    conv.update(record)
    if conv['type'] == 'private_message':
        local_key_id1, _, local_key_id2 = conv['conversation_id'].partition('&')
        try:
            local_key_id1 = int(local_key_id1)
            local_key_id2 = int(local_key_id2)
        except:
            lg.exc()
            return None
        usr1 = my_keys.get_local_key(local_key_id1)
        usr2 = my_keys.get_local_key(local_key_id2)
        if not usr1 or not usr2:
            # lg.warn('%r %r : not found sender or recipient key_id for %r' % (usr1, usr2, conv, ))
            return None
        usr1 = usr1.replace('master$', '')
        usr2 = usr2.replace('master$', '')
        idurl1 = global_id.glob2idurl(usr1, as_field=True)
        idurl2 = global_id.glob2idurl(usr2, as_field=True)
        conv_key_id = None
        conv_label = None
        user_idurl = None
        if (id_url.is_cached(idurl1) and idurl1 == my_id.getIDURL()) or usr1.split('@')[0] == my_id.getIDName():
            user_idurl = idurl2
            conv_key_id = global_id.UrlToGlobalID(idurl2, include_key=True)
            conv_label = conv_key_id.replace('master$', '').split('@')[0]
        if (id_url.is_cached(idurl2) and idurl2 == my_id.getIDURL()) or usr2.split('@')[0] == my_id.getIDName():
            user_idurl = idurl1
            conv_key_id = global_id.UrlToGlobalID(idurl1, include_key=True)
            conv_label = conv_key_id.replace('master$', '').split('@')[0]
        if conv_key_id:
            conv['key_id'] = conv_key_id
        if conv_label:
            conv['label'] = conv_label
        else:
            conv['label'] = conv_key_id
        if user_idurl:
            on_st = online_status.getInstance(user_idurl, autocreate=False)
            if on_st:
                conv.update(on_st.to_json())
    elif conv['type'] == 'group_message' or conv['type'] == 'personal_message':
        local_key_id, _, _ = conv['conversation_id'].partition('&')
        try:
            local_key_id = int(local_key_id)
        except:
            lg.exc()
            return None
        key_id = my_keys.get_local_key(local_key_id)
        if not key_id:
            # lg.warn('key_id was not found for %r' % conv)
            return None
        conv['key_id'] = key_id
        conv['label'] = my_keys.get_label(key_id) or key_id
        g_part = group_participant.get_active_group_participant(key_id)
        if g_part:
            conv.update(g_part.to_json())
    return conv


#------------------------------------------------------------------------------


def insert_message(data, message_id, message_time=None, sender=None, recipient=None, message_type=None, direction=None):
    """
    Writes JSON message to the message database.
    """
    payload_time = message_time or utime.utcnow_to_sec1970()
    payload_message_id = strng.to_text(message_id)
    payload_type = MESSAGE_TYPES.get(message_type, 1)
    if not sender:
        sender = my_id.getGlobalID(key_alias='master')
    if not recipient:
        recipient = my_id.getGlobalID(key_alias='master')
    if direction is None:
        if message_type in ['private_message', None]:
            direction = 'out' if sender == my_id.getGlobalID(key_alias='master') else 'in'
        else:
            direction = 'in'
    else:
        direction = direction.replace('incoming', 'in').replace('outgoing', 'out')
    if _Debug:
        lg.args(_DebugLevel, sender=sender, recipient=recipient, typ=payload_type, dir=direction, message_id=payload_message_id)
    recipient_local_key_id = my_keys.get_local_key_id(recipient)
    if payload_type in [3, 4]:
        sender_local_key_id = recipient_local_key_id
    else:
        sender_local_key_id = my_keys.get_local_key_id(sender)
    if sender_local_key_id is None or recipient_local_key_id is None:
        lg.err('failed to store message because local_key_id is not found, sender=%r recipient=%r' % (sender_local_key_id, recipient_local_key_id))
        return None
    cur().execute(
        '''INSERT INTO history (
            sender_local_key_id,
            sender_id,
            recipient_local_key_id,
            recipient_id,
            direction,
            payload_type,
            payload_time,
            payload_message_id,
            payload_body
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
            sender_local_key_id,
            sender,
            recipient_local_key_id,
            recipient,
            0 if direction == 'in' else 1,
            payload_type,
            payload_time,
            payload_message_id,
            data,
        )
    )
    db().commit()
    conversation_id = update_conversation(sender_local_key_id, recipient_local_key_id, payload_type, payload_time, payload_message_id)
    snap_id = '{}/{}'.format(conversation_id, payload_message_id)
    message_json = build_json_message(
        sender=sender,
        recipient=recipient,
        direction=direction,
        conversation_id=conversation_id,
        message_type=MESSAGE_TYPE_CODES.get(int(payload_type), 'private_message'),
        message_time=payload_time,
        message_id=payload_message_id,
        data=data,
    )
    listeners.push_snapshot('message', snap_id=snap_id, created=payload_time, data=message_json)
    return message_json


def update_conversation(sender_local_key_id, recipient_local_key_id, payload_type, payload_time, payload_message_id):
    conversation_id = get_conversation_id(sender_local_key_id, recipient_local_key_id, payload_type)
    if conversation_id is None:
        lg.err('failed to update conversation, local_key_id was not found')
        return None
    sql = 'SELECT * FROM conversations WHERE conversation_id=?'
    params = [
        conversation_id,
    ]
    found_conversation = list(cur().execute(sql, params))
    if found_conversation:
        sql = 'UPDATE conversations SET last_updated_time=?, last_message_id=? WHERE conversation_id=?'
        params = [
            payload_time,
            payload_message_id,
            conversation_id,
        ]
    else:
        sql = 'INSERT INTO conversations (conversation_id, payload_type, started_time, last_updated_time, last_message_id) VALUES (?, ?, ?, ?, ?)'
        params = [
            conversation_id,
            payload_type,
            payload_time,
            payload_time,
            payload_message_id,
        ]
    if _Debug:
        lg.args(_DebugLevel, conversation_id=conversation_id, found_conversation=len(found_conversation), params=params)
    cur().execute(sql, params)
    db().commit()
    if not found_conversation:
        snapshot = build_json_conversation(
            conversation_id=conversation_id,
            type=MESSAGE_TYPE_CODES.get(int(payload_type), 'private_message'),
            started=payload_time,
            last_updated=payload_time,
            last_message_id=payload_message_id,
        )
        listeners.push_snapshot('conversation', snap_id=conversation_id, data=snapshot)
    return conversation_id


def query_messages(sender_id=None, recipient_id=None, bidirectional=True, order_by_id=True, order_by_time=False, message_types=[], sequence_head=None, sequence_tail=None, offset=None, limit=None, raw_results=False):
    sql = 'SELECT * FROM history'
    q = ''
    params = []
    if bidirectional and sender_id and recipient_id:
        recipient_local_key_id = my_keys.get_local_key_id(recipient_id)
        sender_local_key_id = my_keys.get_local_key_id(sender_id)
        if recipient_local_key_id is None or sender_local_key_id is None:
            lg.warn('local_key_id was not found, recipient_local_key_id=%r sender_local_key_id=%r' % (recipient_local_key_id, sender_local_key_id))
            return []
        q += ' sender_local_key_id IN (?, ?) AND recipient_local_key_id IN (?, ?)'
        params += [
            sender_local_key_id,
            recipient_local_key_id,
            sender_local_key_id,
            recipient_local_key_id,
        ]
    else:
        if sender_id:
            sender_local_key_id = my_keys.get_local_key_id(sender_id)
            if sender_local_key_id is None:
                lg.warn('local_key_id was not found for sender %r' % sender_id)
                return []
            q += ' sender_local_key_id=?'
            params.append(sender_local_key_id)
        if recipient_id:
            recipient_local_key_id = my_keys.get_local_key_id(recipient_id)
            if recipient_local_key_id is None:
                lg.warn('local_key_id was not found for recipient %r' % recipient_id)
                return []
            q += ' recipient_local_key_id=?'
            params.append(recipient_local_key_id)
    if message_types:
        if params:
            q += ' AND payload_type IN (%s)' % (','.join([
                '?',
            ]*len(message_types)))
        else:
            q += ' payload_type IN (%s)' % (','.join([
                '?',
            ]*len(message_types)))
        params.extend([MESSAGE_TYPES.get(mt, 1) for mt in message_types])
    if sequence_head is not None:
        if params:
            q += ' AND payload_message_id>=?'
        else:
            q += ' payload_message_id>=?'
        params.append(sequence_head)
    if sequence_tail is not None:
        if params:
            q += ' AND payload_message_id<=?'
        else:
            q += ' payload_message_id<=?'
        params.append(sequence_tail)
    if q:
        sql += ' WHERE %s' % q
    if order_by_id:
        sql += ' ORDER BY payload_message_id DESC'
    else:
        if order_by_time:
            sql += ' ORDER BY payload_time DESC'
    if limit is not None:
        sql += ' LIMIT ?'
        params.append(limit)
    if offset is not None:
        sql += ' OFFSET ?'
        params.append(offset)
    if _Debug:
        lg.args(_DebugLevel, sql=sql, params=params)
    results = []
    local_key_ids = {}
    for row in cur().execute(sql, params):
        sender_local_key_id = row[0]
        sender_id_recorded = row[1]
        recipient_local_key_id = row[2]
        recipient_id_recorded = row[3]
        if sender_local_key_id not in local_key_ids:
            local_key_ids[sender_local_key_id] = my_keys.get_local_key(sender_local_key_id)
        if recipient_local_key_id not in local_key_ids:
            local_key_ids[recipient_local_key_id] = my_keys.get_local_key(recipient_local_key_id)
        if not local_key_ids.get(sender_local_key_id) or not local_key_ids.get(recipient_local_key_id):
            # lg.warn('unknown sender or recipient local key_id')
            continue
        if raw_results:
            if order_by_time:
                results.insert(0, row)
            else:
                results.append(row)
            continue
        json_msg = build_json_message(
            sender=sender_id_recorded,
            recipient=recipient_id_recorded,
            direction='in' if row[4] == 0 else 'out',
            conversation_id=get_conversation_id(sender_local_key_id, recipient_local_key_id, int(row[5])),
            message_type=MESSAGE_TYPE_CODES.get(int(row[5]), 'private_message'),
            message_time=row[6],
            message_id=row[7],
            data=json.loads(row[8]),
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
        q += ' payload_type IN (%s)' % (','.join([
            '?',
        ]*len(message_types)))
        params.extend([MESSAGE_TYPES.get(mt, 1) for mt in message_types])
    if q:
        sql += ' WHERE %s' % q
    if order_by_time:
        sql += ' ORDER BY last_updated_time DESC'
    if limit is not None:
        sql += ' LIMIT ?'
        params += [
            limit,
        ]
    if offset is not None:
        sql += ' OFFSET ?'
        params += [
            offset,
        ]
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
    params = [
        new_id,
        old_id,
    ]
    cur().execute(sql, params)
    db().commit()
    if _Debug:
        lg.args(_DebugLevel, sql=sql, params=params)
    sql = 'UPDATE history SET recipient_local_key_id=? WHERE recipient_local_key_id=?'
    params = [
        new_id,
        old_id,
    ]
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
        params = [new_conv_id, old_conv_id]
        cur().execute(sql, params)
        db().commit()
        if _Debug:
            lg.args(_DebugLevel, sql=sql, params=params)


def rebuild_conversations():
    cur().execute('SELECT count(name) FROM sqlite_master WHERE type="table" AND name="conversations"')
    if cur().fetchone()[0]:
        return
    cur().execute('''CREATE TABLE IF NOT EXISTS "conversations" (
        "conversation_id" TEXT,
        "payload_type" INTEGER,
        "started_time" INTEGER,
        "last_updated_time" INTEGER,
        "last_message_id" TEXT)''')
    cur().execute('CREATE INDEX "conversation id" on conversations(conversation_id)')
    db().commit()
    for message_json in list(query_messages()):
        msg_typ = message_json['payload'].get('msg_type') or message_json['payload'].get('type')
        payload_type = MESSAGE_TYPES.get(msg_typ, 1)
        recipient_local_key_id = my_keys.get_local_key_id(message_json['recipient']['glob_id'])
        if payload_type in [3, 4]:
            sender_local_key_id = recipient_local_key_id
        else:
            sender_local_key_id = my_keys.get_local_key_id(message_json['sender']['glob_id'])
        update_conversation(
            sender_local_key_id=sender_local_key_id,
            recipient_local_key_id=recipient_local_key_id,
            payload_type=payload_type,
            payload_time=message_json['payload']['time'],
            payload_message_id=message_json['payload']['message_id'],
        )


#------------------------------------------------------------------------------


def check_create_keys():
    to_be_opened = []
    to_be_cached = []
    for key_id in my_keys.known_keys():
        if not key_id.startswith('group_'):
            continue
        if not my_keys.is_key_private(key_id):
            continue
        if not my_keys.is_active(key_id):
            continue
        _, customer_idurl = my_keys.split_key_id(key_id)
        if not id_url.is_cached(customer_idurl):
            to_be_cached.append(customer_idurl)
        else:
            to_be_opened.append(key_id)
    if to_be_cached:
        lg.warn('still see %d not cached identities, not able to process those customers: %r' % (len(to_be_cached), to_be_cached))
    if _Debug:
        lg.args(_DebugLevel, to_be_opened=to_be_opened, to_be_cached=to_be_cached)
    for key_id in to_be_opened:
        check_create_rename_key(new_key_id=key_id)


def check_create_rename_key(new_key_id):
    try:
        new_public_key = my_keys.get_public_key_raw(new_key_id)
    except:
        lg.exc()
        return False
    try:
        new_local_key_id = my_keys.get_local_key_id(new_key_id)
    except:
        lg.exc()
        return False
    if new_local_key_id is None:
        lg.err('did not found local_key_id for %r' % new_key_id)
        return False
    conversation_type = None
    if new_key_id.startswith('group_'):
        conversation_type = 'group_message'
    elif new_key_id.startswith('person_'):
        conversation_type = 'personal_message'
    elif new_key_id.startswith('master$'):
        conversation_type = 'private_message'
    if conversation_type is None:
        return False
    sql = 'SELECT * FROM keys WHERE public_key=?'
    params = [
        new_public_key,
    ]
    found_public_keys = list(cur().execute(sql, params))
    if _Debug:
        lg.args(_DebugLevel, found_public_keys=found_public_keys)
    if found_public_keys:
        if len(found_public_keys) > 1:
            raise Exception('found multiple records for same public key: %r' % found_public_keys)
        key_id = found_public_keys[0][0]
        local_key_id = found_public_keys[0][1]
        changed = False
        if key_id != new_key_id:
            changed = True
            sql = 'UPDATE keys SET key_id=? WHERE public_key=?'
            params = [
                new_key_id,
                new_public_key,
            ]
            cur().execute(sql, params)
            db().commit()
            if _Debug:
                lg.args(_DebugLevel, sql=sql, params=params)
        if local_key_id != new_local_key_id:
            changed = True
            lg.warn('found new public key which is re-using already known key with different local key id: %r -> %r' % (local_key_id, new_local_key_id))
            update_history_with_new_local_key_id(local_key_id, new_local_key_id)
            update_conversations_with_new_local_key_id(local_key_id, new_local_key_id)
            sql = 'UPDATE keys SET local_key_id=? WHERE public_key=?'
            params = [
                new_local_key_id,
                new_public_key,
            ]
            cur().execute(sql, params)
            db().commit()
            if _Debug:
                lg.args(_DebugLevel, sql=sql, params=params)
        return changed
    # new key will be registered in the "keys" table
    # also new conversation record can be created if that was a group type
    # unlike groups, private messages suppose to record a new conversation only when a first message appears and delivered between two
    sql = 'INSERT INTO keys (key_id, local_key_id, public_key) VALUES (?, ?, ?)'
    params = [
        new_key_id,
        new_local_key_id,
        new_public_key,
    ]
    cur().execute(sql, params)
    db().commit()
    if _Debug:
        lg.args(_DebugLevel, sql=sql, params=params)
    if conversation_type in ['group_message', 'personal_message']:
        update_conversation(
            sender_local_key_id=new_local_key_id,
            recipient_local_key_id=new_local_key_id,
            payload_type=MESSAGE_TYPES.get(conversation_type, 1),
            payload_time=utime.utcnow_to_sec1970(),
            payload_message_id='',
        )
    return True


#------------------------------------------------------------------------------


def fetch_conversations(order_by_time=True, message_types=[], offset=None, limit=None):
    conversations = []
    for conv_record in list(list_conversations(
        order_by_time=order_by_time,
        message_types=message_types,
        offset=offset,
        limit=limit,
    ), ):
        conv = build_json_conversation(**conv_record)
        if conv:
            if conv['key_id']:
                conversations.append(conv)
            else:
                lg.warn('unknown key_id for %r' % conv)
    return conversations


def populate_conversations(message_types=[], offset=0, limit=100, order_by_time=True):
    for conv in fetch_conversations(
        order_by_time=order_by_time,
        message_types=message_types,
        offset=offset,
        limit=limit,
    ):
        listeners.push_snapshot('conversation', snap_id=conv['conversation_id'], data=conv)


def populate_messages(recipient_id=None, sender_id=None, message_types=[], offset=0, limit=100):
    if recipient_id:
        if not recipient_id.count('@'):
            from bitdust.contacts import contactsdb
            recipient_idurl = contactsdb.find_correspondent_by_nickname(recipient_id)
            if not recipient_idurl:
                lg.err('recipient %r was not found' % recipient_id)
                return
            recipient_id = global_id.UrlToGlobalID(recipient_idurl)
        recipient_glob_id = global_id.ParseGlobalID(recipient_id)
        if not recipient_glob_id['idurl']:
            lg.err('wrong recipient_id')
            return
        recipient_id = global_id.MakeGlobalID(**recipient_glob_id)
        if not my_keys.is_valid_key_id(recipient_id):
            lg.err('invalid recipient_id: %s' % recipient_id)
            return
    if sender_id:
        sender_local_key_id = my_keys.get_local_key_id(sender_id)
        if sender_local_key_id is None:
            return
    if recipient_id:
        recipient_local_key_id = my_keys.get_local_key_id(recipient_id)
        if recipient_local_key_id is None:
            lg.warn('recipient %r local key id was not registered' % recipient_id)
            return
    for row in query_messages(
        sender_id=sender_id,
        recipient_id=recipient_id,
        bidirectional=False,
        message_types=message_types,
        offset=offset,
        limit=limit,
        raw_results=True,
    ):
        conversation_id = get_conversation_id(row[0], row[2], int(row[5]))
        if conversation_id is None:
            continue
        snap_id = '{}/{}'.format(conversation_id, row[7])
        snapshot = build_json_message(
            sender=row[1],
            recipient=row[3],
            direction='in' if row[4] == 0 else 'out',
            conversation_id=conversation_id,
            message_type=MESSAGE_TYPE_CODES.get(int(row[5]), 'private_message'),
            message_time=row[6],
            message_id=row[7],
            data=json.loads(row[8]),
        )
        listeners.push_snapshot('message', snap_id=snap_id, created=row[6], data=snapshot)


#------------------------------------------------------------------------------


def notify_group_conversation(oldstate, newstate, group_json_info):
    sender_recipient_local_key_id = my_keys.get_local_key_id(group_json_info['group_key_id'])
    if sender_recipient_local_key_id is None:
        return
    conversation_id = get_conversation_id(sender_recipient_local_key_id, sender_recipient_local_key_id, 3)
    if conversation_id is None:
        return
    snapshot = dict(
        conversation_id=conversation_id,
        type=MESSAGE_TYPE_CODES[3],
        started=None,
        last_updated=None,
        last_message_id=group_json_info['sequence_tail'],
        key_id=group_json_info['group_key_id'],
        old_state=oldstate,
    )
    snapshot.update(group_json_info)
    listeners.push_snapshot('conversation', snap_id=conversation_id, data=snapshot)


#------------------------------------------------------------------------------


def main():
    import pprint
    my_keys.init()
    init()
    pprint.pprint(list(query_messages(
        # sender_id='',
        recipient_id='group_96b1fa942b556e2e0dbccdcc9eeed84a$veselibro@seed.bitdust.io',
        # offset=2,
        # limit=3,
        message_types=[
            'group_message',
        ],
    )))
    # pprint.pprint(list(list_conversations(
    # message_types=['group_message', ]
    # )))
    shutdown()


if __name__ == '__main__':
    lg.set_debug_level(20)
    main()
