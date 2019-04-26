#!/usr/bin/python
# message_keeper.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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

import os

#------------------------------------------------------------------------------

from logs import lg

from system import bpio

from main import settings

from interface import api

from services import driver

from userid import my_id
from userid import global_id

from crypt import my_keys

from chat import message
from chat import message_db

#------------------------------------------------------------------------------

def init():
    lg.out(4, "message_keeper.init")
    message.AddIncomingMessageCallback(on_incoming_message)
    message.AddOutgoingMessageCallback(on_outgoing_message)


def shutdown():
    lg.out(4, "message_keeper.shutdown")
    message.RemoveIncomingMessageCallback(on_incoming_message)
    message.RemoveOutgoingMessageCallback(on_outgoing_message)

#------------------------------------------------------------------------------

def messages_key_id():
    """
    """
    return global_id.MakeGlobalID(key_alias='messages', customer=my_id.getGlobalID())

#------------------------------------------------------------------------------

def on_incoming_message(packet_in_object, private_message_object, json_message):
    """
    """
    cache_message(
        data=json_message,
        message_id=packet_in_object.PacketID,
        sender=private_message_object.sender,
        recipient=private_message_object.recipient,
    )
    # backup_incoming_message(private_message_object, packet_in_object.PacketID)


def on_outgoing_message(json_message, private_message_object, remote_identity, outpacket, packet_out_object):
    """
    """
    cache_message(
        data=json_message,
        message_id=outpacket.PacketID,
        sender=private_message_object.sender,
        recipient=private_message_object.recipient,
    )
    # backup_outgoing_message(private_message_object, outpacket.PacketID)

#------------------------------------------------------------------------------

def backup_incoming_message(private_message_object, message_id):
    """
    """
    if not driver.is_on('service_backups'):
        lg.warn('service_backups is not started')
        return False
    if not my_keys.is_key_registered(messages_key_id()):
        lg.warn('key to store messages was not found')
        return False
    serialized_message = private_message_object.serialize()
    local_msg_folder = os.path.join(settings.ChatChannelsDir(), private_message_object.recipient, 'in')
    if not bpio._dir_exist(local_msg_folder):
        bpio._dirs_make(local_msg_folder)
    local_msg_filename = os.path.join(local_msg_folder, message_id)
    if not bpio.WriteBinaryFile(local_msg_filename, serialized_message):
        lg.warn('failed writing incoming message locally')
        return False
    remote_path_for_message = os.path.join('.messages', 'in', private_message_object.recipient, message_id)
    global_message_path = global_id.MakeGlobalID(customer=messages_key_id(), path=remote_path_for_message)
    res = api.file_create(global_message_path)
    if res['status'] != 'OK':
        lg.warn('failed to create path "%s" in the catalog: %r' % (global_message_path, res))
        return False
    res = api.file_upload_start(local_msg_filename, global_message_path, wait_result=False)
    if res['status'] != 'OK':
        lg.warn('failed to upload message "%s": %r' % (global_message_path, res))
        return False
    return True


def backup_outgoing_message(private_message_object, message_id):
    """
    """
    if not driver.is_on('service_backups'):
        lg.warn('service_backups is not started')
        return False
    if not my_keys.is_key_registered(messages_key_id()):
        lg.warn('key to store messages was not found')
        return False
    serialized_message = private_message_object.serialize()
    local_msg_folder = os.path.join(settings.ChatChannelsDir(), private_message_object.recipient, 'out')
    if not bpio._dir_exist(local_msg_folder):
        bpio._dirs_make(local_msg_folder)
    local_msg_filename = os.path.join(local_msg_folder, message_id)
    if not bpio.WriteBinaryFile(local_msg_filename, serialized_message):
        lg.warn('failed writing outgoing message locally')
        return False
    remote_path_for_message = os.path.join('.messages', 'out', private_message_object.recipient, message_id)
    global_message_path = global_id.MakeGlobalID(customer=messages_key_id(), path=remote_path_for_message)
    res = api.file_create(global_message_path)
    if res['status'] != 'OK':
        lg.warn('failed to create path "%s" in the catalog: %r' % (global_message_path, res))
        return False
    res = api.file_upload_start(local_msg_filename, global_message_path, wait_result=False)
    if res['status'] != 'OK':
        lg.warn('failed to upload message "%s": %r' % (global_message_path, res))
        return False
    return True

#------------------------------------------------------------------------------

def cache_message(data, message_id, sender, recipient):
    """
    """
    message_json = message_db.build_json_message(
        data=data,
        message_id=message_id,
        sender=sender,
        recipient=recipient,
    )
    message_db.insert(message_json)
    if _Debug:
        lg.out(_DebugLevel, 'message_keeper.cache_message "%s"' % str(message_json))
