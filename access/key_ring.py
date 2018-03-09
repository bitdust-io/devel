#!/usr/bin/python
# key_ring.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
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

_Debug = True
_DebugLevel = 4

#------------------------------------------------------------------------------

import sys
import json
import base64

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

def _do_request_service_keys_registry(key_id, idurl, include_private):
    result = Deferred()
    p2p_service.SendRequestService(idurl, 'service_keys_registry', callbacks={
        commands.Ack(): lambda response, indo:
            _on_service_keys_registry_response(response, indo, key_id, idurl, include_private, result),
        commands.Fail(): lambda response, indo:
            result.errback(Exception('"service_keys_registry" not started on remote node'))
    })
    return result


def _on_service_keys_registry_response(response, info, key_id, idurl, include_private, result):
    if not response.Payload.startswith('accepted'):
        result.errback(Exception('request for "service_keys_registry" refused by remote node'))
        return
    _do_transfer_key(key_id, idurl, include_private=include_private).addCallbacks(
        callback=result.callback,
        errback=result.errback
    )


def _do_transfer_key(key_id, idurl, include_private=False):
    if _Debug:
        lg.out(_DebugLevel, 'key_ring.transfer_key  %s -> %s' % (key_id, idurl))
    result = Deferred()
    recipient_id_obj = identitycache.FromCache(idurl)
    if not recipient_id_obj:
        lg.warn('not found "%s" in identity cache' % idurl)
        result.errback(Exception('not found "%s" in identity cache' % idurl))
        return result
    key_alias, creator_idurl = my_keys.split_key_id(key_id)
    if not key_alias or not creator_idurl:
        lg.warn('wrong key_id')
        result.errback(Exception('wrong key_id'))
        return result
    key_object = my_keys.known_keys().get(key_id)
    if key_object is None:
        lg.warn('unknown key: "%s"' % key_id)
        result.errback(Exception('unknown key: "%s"' % key_id))
        return result
    try:
        key_json = my_keys.make_key_info(key_object, key_id=key_id, include_private=include_private)
    except Exception as exc:
        lg.exc()
        result.errback(exc)
        return result
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


def share_key(key_id, trusted_idurl, include_private=False, timeout=10):
    """
    Returns deferred, callback will be fired with response Ack() packet argument.
    """
    result = Deferred()
    d = propagate.PingContact(trusted_idurl, timeout=timeout)
    d.addCallback(
        lambda resp: _do_request_service_keys_registry(
            key_id, trusted_idurl, include_private,
        ).addCallbacks(
            callback=result.callback,
            errback=result.errback
        )
    )
    d.addErrback(result.errback)
    return result

#------------------------------------------------------------------------------

def _on_audit_public_key_response(response, info, key_id, untrusted_idurl, test_sample, result):
    orig_sample = my_keys.encrypt(key_id, test_sample)
    response_sample = base64.b64decode(response.Payload)
    if response_sample == orig_sample:
        if _Debug:
            lg.out(_DebugLevel, 'key_ring._on_audit_public_key_response : %s on %s is OK!' % (key_id, untrusted_idurl, ))
        result.callback(True)
        return True
    lg.warn('key %s on %s is not OK' % (key_id, untrusted_idurl, ))
    result.callback(False)
    return False


def audit_public_key(key_id, untrusted_idurl, timeout=10):
    """
    Be sure remote user posses given public key.
    I also need to posses that public key in order to do such audit.
    I will send him a random string, he needs to encrypt it and send me back.
    I can compare his encrypted output with mine.
    Returns Deferred object.
    """
    if _Debug:
        lg.out(_DebugLevel, 'key_ring.audit_public_key   testing %s from %s' % (key_id, untrusted_idurl))
    result = Deferred()
    recipient_id_obj = identitycache.FromCache(untrusted_idurl)
    if not recipient_id_obj:
        lg.warn('not found "%s" in identity cache' % untrusted_idurl)
        result.errback(Exception('not found "%s" in identity cache' % untrusted_idurl))
        return result
    key_alias, creator_idurl = my_keys.split_key_id(key_id)
    if not key_alias or not creator_idurl:
        lg.warn('wrong key_id')
        result.errback(Exception('wrong key_id'))
        return result
    if not my_keys.is_key_registered(key_id):
        lg.warn('unknown key: "%s"' % key_id)
        result.errback(Exception('unknown key: "%s"' % key_id))
        return result
    public_test_sample = key.NewSessionKey()
    json_payload = {
        'key_id': key_id,
        'audit': {
            'public_sample': base64.b64encode(public_test_sample),
            'private_sample': '',
        }
    }
    raw_payload = json.dumps(json_payload)
    block = encrypted.Block(
        BackupID=key_id,
        Data=raw_payload,
        SessionKey=key.NewSessionKey(),
        # encrypt data using public key of recipient
        EncryptKey=lambda inp: recipient_id_obj.encrypt(inp),
    )
    encrypted_payload = block.Serialize()
    p2p_service.SendAuditKey(
        remote_idurl=recipient_id_obj.getIDURL(),
        encrypted_payload=encrypted_payload,
        packet_id=key_id,
        callbacks={
            commands.Ack(): lambda response, info:
                _on_audit_public_key_response(response, info, key_id, untrusted_idurl, public_test_sample, result),
            commands.Fail(): lambda response, info: result.errback(Exception(response)),
        },
    )
    return result

#------------------------------------------------------------------------------

def _on_audit_private_key_response(response, info, key_id, untrusted_idurl, test_sample, result):
    response_sample = base64.b64decode(response.Payload)
    if response_sample == test_sample:
        if _Debug:
            lg.out(_DebugLevel, 'key_ring._on_audit_private_key_response : %s on %s is OK!' % (key_id, untrusted_idurl, ))
        result.callback(True)
        return True
    lg.warn('key %s on %s is not OK' % (key_id, untrusted_idurl, ))
    result.callback(False)
    return False


def audit_private_key(key_id, untrusted_idurl, timeout=10):
    """
    Be sure remote user posses given private key.
    I need to posses the public key to be able to audit.
    I will generate a random string, encrypt it with given key public key and send encrypted string to him.
    He will decrypt and send me back original string.
    Returns Deferred object.
    """
    if _Debug:
        lg.out(_DebugLevel, 'key_ring.audit_private_key   testing %s from %s' % (key_id, untrusted_idurl))
    result = Deferred()
    recipient_id_obj = identitycache.FromCache(untrusted_idurl)
    if not recipient_id_obj:
        lg.warn('not found "%s" in identity cache' % untrusted_idurl)
        result.errback(Exception('not found "%s" in identity cache' % untrusted_idurl))
        return result
    key_alias, creator_idurl = my_keys.split_key_id(key_id)
    if not key_alias or not creator_idurl:
        lg.warn('wrong key_id')
        result.errback(Exception('wrong key_id'))
        return result
    if not my_keys.is_key_registered(key_id):
        lg.warn('unknown key: "%s"' % key_id)
        result.errback(Exception('unknown key: "%s"' % key_id))
        return result
    private_test_sample = key.NewSessionKey()
    private_test_encrypted_sample = my_keys.encrypt(key_id, private_test_sample)
    json_payload = {
        'key_id': key_id,
        'audit': {
            'public_sample': '',
            'private_sample': base64.b64encode(private_test_encrypted_sample),
        }
    }
    raw_payload = json.dumps(json_payload)
    block = encrypted.Block(
        BackupID=key_id,
        Data=raw_payload,
        SessionKey=key.NewSessionKey(),
        # encrypt data using public key of recipient
        EncryptKey=lambda inp: recipient_id_obj.encrypt(inp),
    )
    encrypted_payload = block.Serialize()
    p2p_service.SendAuditKey(
        remote_idurl=recipient_id_obj.getIDURL(),
        encrypted_payload=encrypted_payload,
        packet_id=key_id,
        callbacks={
            commands.Ack(): lambda response, info:
                _on_audit_private_key_response(response, info, key_id, untrusted_idurl, private_test_sample, result),
            commands.Fail(): lambda response, info: result.errback(Exception(response)),
        },
    )
    return result

#------------------------------------------------------------------------------

def on_key_received(newpacket, info, status, error_message):
    block = encrypted.Unserialize(newpacket.Payload)
    if block is None:
        lg.out(2, 'key_ring.on_key_received ERROR reading data from %s' % newpacket.RemoteID)
        return False
    try:
        key_data = block.Data()
        key_json = json.loads(key_data)
        key_id = key_json['key_id']
        if my_keys.is_key_registered(key_id):
            raise Exception('key "%s" already registered' % key_id)
        key_id, key_object = my_keys.read_key_info(key_json)
        if not my_keys.register_key(key_id, key_object):
            raise Exception('failed to register key %s' % key_id)
    except Exception as exc:
        lg.exc()
        p2p_service.SendFail(newpacket, str(exc))
        return False
    p2p_service.SendAck(newpacket)
    return True


def on_audit_key_received(newpacket, info, status, error_message):
    block = encrypted.Unserialize(newpacket.Payload)
    if block is None:
        lg.out(2, 'key_ring.on_audit_key_received ERROR reading data from %s' % newpacket.RemoteID)
        return False
    try:
        raw_payload = block.Data()
        json_payload = json.loads(raw_payload)
        key_id = json_payload['key_id']
        json_payload['audit']
        public_sample = base64.b64decode(json_payload['audit']['public_sample'])
        private_sample = base64.b64decode(json_payload['audit']['private_sample'])
    except Exception as exc:
        lg.exc()
        p2p_service.SendFail(newpacket, str(exc))
        return False
    if not my_keys.is_valid_key_id(key_id):
        p2p_service.SendFail(newpacket, 'invalid key id')
        return False
    if not my_keys.is_key_registered(key_id, include_master=False):
        p2p_service.SendFail(newpacket, 'key not registered')
        return False
    if public_sample:
        response_payload = base64.b64encode(my_keys.encrypt(key_id, public_sample))
        p2p_service.SendAck(newpacket, response_payload)
        return True
    if private_sample:
        if not my_keys.is_key_private(key_id):
            p2p_service.SendFail(newpacket, 'private key not registered')
            return False
        response_payload = base64.b64encode(my_keys.decrypt(key_id, private_sample))
        p2p_service.SendAck(newpacket, response_payload)
        return True
    p2p_service.SendFail(newpacket, 'wrong audit request')
    return False
