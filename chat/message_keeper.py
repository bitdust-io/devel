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

from logs import lg

from interface import api_web_socket

# from userid import my_id
# from userid import global_id

from stream import message

from chat import message_database

#------------------------------------------------------------------------------

def init():
    if _Debug:
        lg.out(_DebugLevel, "message_keeper.init")
    message.consume_messages(
        consumer_callback_id='message_keeper',
        callback=on_consume_user_messages,
        direction=None,
        message_types=['private_message', 'group_message', ],
        reset_callback=False,
    )

def shutdown():
    if _Debug:
        lg.out(_DebugLevel, "message_keeper.shutdown")
    message.clear_consumer_callbacks(consumer_callback_id='message_keeper')

#------------------------------------------------------------------------------

# def messages_key_id():
#     """
#     """
#     return global_id.MakeGlobalID(key_alias='messages', customer=my_id.getGlobalID())

#------------------------------------------------------------------------------

def on_consume_user_messages(json_messages):
    """
    """
    for json_message in json_messages:
        try:
            msg_type = json_message.get('type', '')
            packet_id = json_message['packet_id']
            sender_id = json_message['from']
            recipient_id = json_message['to']
            msg_data = json_message['data']
        except:
            lg.exc()
            continue
        cache_message(
            data=msg_data,
            message_id=packet_id,
            sender=sender_id,
            recipient=recipient_id,
            message_type=msg_type,
        )
    return True

#------------------------------------------------------------------------------

def cache_message(data, message_id, sender, recipient, message_type=None):
    """
    """
    message_json = message_database.build_json_message(
        data=data,
        message_id=message_id,
        sender=sender,
        recipient=recipient,
        message_type=message_type,
    )
    message_database.insert(message_json)
    api_web_socket.on_stream_message(message_json)
    if _Debug:
        lg.out(_DebugLevel, 'message_keeper.cache_message [%s]:%s from %r to %r' % (message_type, message_id, sender, recipient, ))
