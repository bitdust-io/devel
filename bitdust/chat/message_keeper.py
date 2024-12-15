#!/usr/bin/python
# message_keeper.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (message_keeper.py) is part of BitDust Software.
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
.. module:: message_keeper

"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.interface import api_web_socket
from bitdust.interface import api_device

from bitdust.crypt import my_keys

from bitdust.contacts import identitycache

from bitdust.stream import message

from bitdust.chat import message_database

from bitdust.userid import global_id

#------------------------------------------------------------------------------


def init():
    if _Debug:
        lg.out(_DebugLevel, 'message_keeper.init')
    message.consume_messages(
        consumer_callback_id='message_keeper',
        callback=on_consume_user_messages,
        direction=None,
        message_types=[
            'private_message',
            'group_message',
        ],
        reset_callback=False,
    )


def shutdown():
    if _Debug:
        lg.out(_DebugLevel, 'message_keeper.shutdown')
    message.clear_consumer_callbacks(consumer_callback_id='message_keeper')


#------------------------------------------------------------------------------


def on_consume_user_messages(json_messages):
    for json_message in json_messages:
        try:
            msg_type = json_message.get('type', '')
            packet_id = json_message['packet_id']
            sender_id = json_message['from']
            recipient_id = json_message['to']
            direction = json_message['dir']
            msg_data = json_message['data']
        except:
            lg.exc()
            continue
        cache_message(
            data=msg_data,
            message_id=packet_id,
            sender_id=sender_id,
            recipient_id=recipient_id,
            message_type=msg_type,
            direction=direction,
        )
    return False


#------------------------------------------------------------------------------


def cache_message(data, message_id, sender_id, recipient_id, message_type=None, direction=None):
    if _Debug:
        lg.args(_DebugLevel, message_id=message_id, sender_id=sender_id, recipient_id=recipient_id, message_type=message_type)
    if message_type == 'private_message':
        if not my_keys.is_key_registered(sender_id):
            sender_idurl = global_id.glob2idurl(sender_id)
            known_ident = identitycache.FromCache(sender_idurl)
            if not known_ident:
                lg.warn('sender identity %r was not cached, not possible to store message locally' % sender_idurl)
                return False
            if not my_keys.register_key(sender_id, known_ident.getPublicKey()):
                lg.err('failed to register known public key of the sender: %r' % sender_id)
                return False
        if not my_keys.is_key_registered(recipient_id):
            recipient_idurl = global_id.glob2idurl(recipient_id)
            known_ident = identitycache.FromCache(recipient_idurl)
            if not known_ident:
                lg.warn('recipient identity %r was not cached, not possible to store message locally' % recipient_idurl)
                return False
            if not my_keys.register_key(recipient_id, known_ident.getPublicKey()):
                lg.err('failed to register known public key of the recipient: %r' % recipient_id)
                return False
        return store_message(data, message_id, sender_id, recipient_id, message_type, direction)

    if message_type == 'group_message' or message_type == 'personal_message':
        if not my_keys.is_key_registered(recipient_id):
            lg.err('failed to cache %r because recipient key %r was not registered' % (message_type, recipient_id))
            return False
        return store_message(data, message_id, sender_id, recipient_id, message_type, direction)

    raise Exception('unexpected message type: %r' % message_type)


#------------------------------------------------------------------------------


def store_message(data, message_id, sender_id, recipient_id, message_type=None, direction=None):
    message_json = message_database.insert_message(
        data=data,
        message_id=message_id,
        sender=sender_id,
        recipient=recipient_id,
        message_type=message_type,
        direction=direction,
    )
    if not message_json:
        lg.warn('message %r was not stored' % message_id)
        return message_json
    api_web_socket.on_stream_message(message_json)
    api_device.on_stream_message(message_json)
    if _Debug:
        lg.out(_DebugLevel, 'message_keeper.store_message [%s]:%s from %r to %r' % (message_type, message_id, sender_id, recipient_id))
    return message_json
