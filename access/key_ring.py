#!/usr/bin/python
# key_ring.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (key_ring.py) is part of BitDust Software.
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

"""
.. module:: key_ring

"""

#------------------------------------------------------------------------------

import sys
import json

from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg

from contacts import identitycache

from userid import my_id

from p2p import propagate
from p2p import p2p_service
from p2p import commands

from crypt import key
from crypt import my_keys
from crypt import encrypted

#------------------------------------------------------------------------------

def init():
    """
    """
    lg.out(4, 'key_ring.init')


def shutdown():
    lg.out(4, 'key_ring.shutdown')

#-------------------------------------------------------------------------------

def share_private_key(key_id, idurl, timeout=10):
    result = Deferred()
    d = propagate.PingContact(idurl, timeout=timeout)
    d.addCallback(
        lambda resp: request_service_keys_registry(
            key_id, idurl,
        ).addCallbacks(
            callback=result.callback,
            errback=result.errback
        )
    )
    d.addErrback(result.errback)
    return result


def request_service_keys_registry(key_id, idurl):
    result = Deferred()
    p2p_service.SendRequestService(idurl, 'service_keys_registry', callbacks={
        commands.Ack(): lambda response, indo:
            on_service_keys_registry_response(response, indo, key_id, idurl, result),
        commands.Fail(): lambda response, indo:
            result.errback(Exception('"service_keys_registry" not started on remote node'))
    })
    return result


def on_service_keys_registry_response(response, info, key_id, idurl, result):
    if not response.Payload.startswith('accepted'):
        result.errback(Exception('request for "service_keys_registry" refused by remote node'))
        return
    transfer_private_key(key_id, idurl).addCallbacks(
        callback=result.callback,
        errback=result.errback
    )


def transfer_private_key(key_id, idurl):
    result = Deferred()
    recipient_id_obj = identitycache.FromCache(idurl)
    if not recipient_id_obj:
        result.errback(Exception(idurl))
        return result
    key_alias, creator_idurl = my_keys.split_key_id(key_id)
    if not key_alias or not creator_idurl:
        result.errback(Exception(key_id))
        return result
    key_object = my_keys.known_keys().get(key_id)
    if key_object is None:
        result.errback(Exception(key_id))
        return result
    key_json = {
        'key_id': key_id,
        'alias': key_alias,
        'creator': creator_idurl,
        'fingerprint': str(key_object.fingerprint()),
        'type': str(key_object.type()),
        'ssh_type': str(key_object.sshType()),
        'size': str(key_object.size()),
        'public': str(key_object.public().toString('openssh')),
        'private': str(key_object.toString('openssh')),
    }
    key_data = json.dumps(key_json)
    block = encrypted.Block(
        BackupID=key_id,
        Data=key_data,
        SessionKey=key.NewSessionKey(),
        # encrypt data using public key of recipient
        EncryptKey=lambda inp: recipient_id_obj.encrypt(inp),
    )
    encrypted_key_data = block.Serialize()
    p2p_service.SendKey(
        remote_idurl=recipient_id_obj.getIDURL(),
        encrypted_key_data=encrypted_key_data,
        packet_id=key_id,
        callbacks={
            commands.Ack(): lambda response, info: result.callback(response),
            commands.Fail(): lambda response, info: result.errback(Exception(response)),
        },
    )
    return result


def on_private_key_received(newpacket, info, status, error_message):
    block = encrypted.Unserialize(newpacket.Payload)
    if block is None:
        lg.out(2, 'key_ring.received_private_key ERROR reading data from %s' % newpacket.RemoteID)
        return False
    try:
        key_data = block.Data()
        key_json = json.loads(key_data)
        key_id = str(key_json['key_id'])
        # key_alias = key_json['alias']
        # key_creator = key_json['creator']
        # key_owner = key_json['owner']
        private_key_string = str(key_json['private'])
    except:
        lg.exc()
        return False
    if my_keys.is_key_registered(key_id):
        return False
    key_object = my_keys.register_key(key_id, private_key_string)
    if not key_object:
        return False
    p2p_service.SendAck(newpacket)
    return True
