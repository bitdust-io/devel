#!/usr/bin/python
# key_ring.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 4

#------------------------------------------------------------------------------

import os
import sys
import base64

from twisted.internet.defer import Deferred, fail

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg

from lib import strng
from lib import serialization

from main import settings

from contacts import identitycache

from p2p import online_status
from p2p import p2p_service
from p2p import commands

from crypt import key
from crypt import my_keys
from crypt import encrypted

from userid import global_id
from userid import my_id

from interface import api

#------------------------------------------------------------------------------

_MyKeysInSync = False

#------------------------------------------------------------------------------

def init():
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'key_ring.init')
    check_rename_my_keys()


def shutdown():
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'key_ring.shutdown')


#------------------------------------------------------------------------------

def _do_request_service_keys_registry(key_id, idurl, include_private, timeout, result):
    p2p_service.SendRequestService(idurl, 'service_keys_registry', callbacks={
        commands.Ack(): lambda response, info:
            _on_service_keys_registry_response(response, info, key_id, idurl, include_private, result, timeout),
        commands.Fail(): lambda response, info:
            result.errback(Exception('"service_keys_registry" not started on remote node')),
        None: lambda pkt_out: result.errback(Exception('timeout')),
    })
    return result


def _on_service_keys_registry_response(response, info, key_id, idurl, include_private, result, timeout):
    if not strng.to_text(response.Payload).startswith('accepted'):
        result.errback(Exception('request for "service_keys_registry" refused by remote node'))
        return None
    d = transfer_key(
        key_id,
        trusted_idurl=idurl,
        include_private=include_private,
        timeout=timeout,
        result=result,
    )
    d.addErrback(lambda *a: lg.err('transfer key failed: %s' % str(*a)))
    return None


def _on_transfer_key_response(response, info, key_id, result):
    if not response or not info:
        result.errback(Exception('timeout'))
        if _Debug:
            lg.warn('transfer failed, response timeout')
        return None
    if response.Command == commands.Ack():
        result.callback(response)
        if _Debug:
            lg.info('key %s transfer success to %s' % (key_id, response.OwnerID))
        return None
    if response.Command == commands.Fail():
        err_msg = strng.to_text(response.Payload, errors='ignore')
        if err_msg.count('key already registered'):
            # it is okay to have "Fail()" response in that case
            result.callback(response)
            if _Debug:
                lg.warn('key %s already registered on %s' % (key_id, response.OwnerID))
            return None
    result.errback(Exception(response.Payload))
    if _Debug:
        lg.warn('key transfer failed: %s' % response.Payload)
    return None


def transfer_key(key_id, trusted_idurl, include_private=False, timeout=10, result=None):
    """
    Actually sending given key to remote user.
    """
    if _Debug:
        lg.out(_DebugLevel, 'key_ring.transfer_key  %s -> %s' % (key_id, trusted_idurl))
    if not result:
        result = Deferred()
    recipient_id_obj = identitycache.FromCache(trusted_idurl)
    if not recipient_id_obj:
        lg.warn('not found "%s" in identity cache' % trusted_idurl)
        result.errback(Exception('not found "%s" in identity cache' % trusted_idurl))
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
    key_object = my_keys.key_obj(key_id)
    try:
        key_json = my_keys.make_key_info(key_object, key_id=key_id, include_private=include_private)
    except Exception as exc:
        lg.exc()
        result.errback(exc)
        return result
    key_data = serialization.DictToBytes(key_json, values_to_text=True)
    block = encrypted.Block(
        BackupID=key_id,
        Data=key_data,
        SessionKey=key.NewSessionKey(session_key_type=key.SessionKeyType()),
        SessionKeyType=key.SessionKeyType(),
        # encrypt data using public key of recipient
        EncryptKey=lambda inp: recipient_id_obj.encrypt(inp),
    )
    encrypted_key_data = block.Serialize()
    p2p_service.SendKey(
        remote_idurl=recipient_id_obj.getIDURL(),
        encrypted_key_data=encrypted_key_data,
        packet_id=key_id,
        callbacks={
            commands.Ack(): lambda response, info: _on_transfer_key_response(response, info, key_id, result),
            commands.Fail(): lambda response, info: _on_transfer_key_response(response, info, key_id, result),
            None: lambda pkt_out: _on_transfer_key_response(None, None, key_id, result),
        },
        timeout=timeout,
    )
    return result


def share_key(key_id, trusted_idurl, include_private=False, timeout=20):
    """
    Method to be used to send given key to one trusted user.
    Make sure remote user is identified and connected.
    Returns deferred, callback will be fired with response Ack() packet argument.
    """
    result = Deferred()
    d = online_status.ping(
        idurl=trusted_idurl,
        ack_timeout=timeout,
        channel='share_key',
        keep_alive=False,
    )
    d.addCallback(lambda ok: _do_request_service_keys_registry(
        key_id, trusted_idurl, include_private, timeout, result,
    ))
    d.addErrback(result.errback)
    return result

#------------------------------------------------------------------------------

def _on_audit_public_key_response(response, info, key_id, untrusted_idurl, test_sample, result):
    try:
        response_sample = base64.b64decode(response.Payload)
    except:
        lg.exc()
        result.callback(False)
        return False
    key_alias, creator_idurl = my_keys.split_key_id(key_id)
    if creator_idurl == untrusted_idurl and key_alias == 'master':
        recipient_id_obj = identitycache.FromCache(creator_idurl)
        if not recipient_id_obj:
            lg.warn('not found "%s" in identity cache' % creator_idurl)
            result.errback(Exception('not found "%s" in identity cache' % creator_idurl))
            return result
        orig_sample = recipient_id_obj.encrypt(test_sample)
    else:
        orig_sample = my_keys.encrypt(key_id, test_sample)
    if response_sample == orig_sample:
        if _Debug:
            lg.out(_DebugLevel, 'key_ring._on_audit_public_key_response : %s on %s' % (key_id, untrusted_idurl, ))
        result.callback(True)
        return True
    lg.warn('key %s on %s is not OK' % (key_id, untrusted_idurl, ))
    result.callback(False)
    return False


def audit_public_key(key_id, untrusted_idurl, timeout=10):
    """
    Be sure remote user stores given public key.
    I also need to stores that public key in order to do such audit.
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
    if untrusted_idurl == creator_idurl and key_alias == 'master':
        lg.info('doing audit of master key (public part) of remote user')
    else:
        if not my_keys.is_key_registered(key_id):
            lg.warn('unknown key: "%s"' % key_id)
            result.errback(Exception('unknown key: "%s"' % key_id))
            return result
    public_test_sample = key.NewSessionKey(session_key_type=key.SessionKeyType())
    json_payload = {
        'key_id': key_id,
        'audit': {
            'public_sample': base64.b64encode(public_test_sample),
            'private_sample': '',
        }
    }
    raw_payload = serialization.DictToBytes(json_payload, values_to_text=True)
    block = encrypted.Block(
        BackupID=key_id,
        Data=raw_payload,
        SessionKey=key.NewSessionKey(session_key_type=key.SessionKeyType()),
        SessionKeyType=key.SessionKeyType(),
        # encrypt data using public key of recipient
        EncryptKey=lambda inp: recipient_id_obj.encrypt(inp),
    )
    encrypted_payload = block.Serialize()
    p2p_service.SendAuditKey(
        remote_idurl=recipient_id_obj.getIDURL(),
        encrypted_payload=encrypted_payload,
        packet_id=key_id,
        timeout=timeout,
        callbacks={
            commands.Ack(): lambda response, info:
                _on_audit_public_key_response(response, info, key_id, untrusted_idurl, public_test_sample, result),
            commands.Fail(): lambda response, info: result.errback(Exception(response)),
            None: lambda pkt_out: result.errback(Exception('timeout')),  # timeout
        },
    )
    return result

#------------------------------------------------------------------------------

def _on_audit_private_key_response(response, info, key_id, untrusted_idurl, test_sample, result):
    try:
        response_sample = base64.b64decode(response.Payload)
    except:
        lg.exc()
        result.callback(False)
        return False
    if response_sample == test_sample:
        if _Debug:
            lg.out(_DebugLevel, 'key_ring._on_audit_private_key_response : %s on %s' % (key_id, untrusted_idurl, ))
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
    private_test_sample = key.NewSessionKey(session_key_type=key.SessionKeyType())
    if untrusted_idurl == creator_idurl and key_alias == 'master':
        lg.info('doing audit of master key (private part) of remote user')
        private_test_encrypted_sample = recipient_id_obj.encrypt(private_test_sample)
    else:
        if not my_keys.is_key_registered(key_id):
            lg.warn('unknown key: "%s"' % key_id)
            result.errback(Exception('unknown key: "%s"' % key_id))
            return result
        private_test_encrypted_sample = my_keys.encrypt(key_id, private_test_sample)
    json_payload = {
        'key_id': key_id,
        'audit': {
            'public_sample': '',
            'private_sample': base64.b64encode(private_test_encrypted_sample),
        }
    }
    raw_payload = serialization.DictToBytes(json_payload, values_to_text=True)
    block = encrypted.Block(
        BackupID=key_id,
        Data=raw_payload,
        SessionKey=key.NewSessionKey(session_key_type=key.SessionKeyType()),
        SessionKeyType=key.SessionKeyType(),
        # encrypt data using public key of recipient
        EncryptKey=lambda inp: recipient_id_obj.encrypt(inp),
    )
    encrypted_payload = block.Serialize()
    p2p_service.SendAuditKey(
        remote_idurl=recipient_id_obj.getIDURL(),
        encrypted_payload=encrypted_payload,
        packet_id=key_id,
        timeout=timeout,
        callbacks={
            commands.Ack(): lambda response, info:
                _on_audit_private_key_response(response, info, key_id, untrusted_idurl, private_test_sample, result),
            commands.Fail(): lambda response, info: result.errback(Exception(response)),
            None: lambda pkt_out: result.errback(Exception('timeout')),  # timeout
        },
    )
    return result

#------------------------------------------------------------------------------

def on_key_received(newpacket, info, status, error_message):
    """
    Callback will be executed when I receive a new key from one remote user.
    """
    block = encrypted.Unserialize(newpacket.Payload)
    if block is None:
        lg.out(2, 'key_ring.on_key_received ERROR reading data from %s' % newpacket.RemoteID)
        return False
    try:
        key_data = block.Data()
        key_json = serialization.BytesToDict(key_data, keys_to_text=True, values_to_text=True)
        key_id = key_json['key_id']
        key_label = key_json.get('label', '')
        key_id, key_object = my_keys.read_key_info(key_json)
        if key_object.isPublic():
            # received key is a public key
            if my_keys.is_key_registered(key_id):
                # but we already have a key with that ID
                if my_keys.is_key_private(key_id):
                    # we should not overwrite existing private key
                    raise Exception('private key already registered')
                if my_keys.get_public_key_raw(key_id) != key_object.toPublicString():
                    # and we should not overwrite existing public key as well
                    raise Exception('another public key already registered with that ID and it is not matching')
                p2p_service.SendAck(newpacket)
                lg.warn('received existing public key: %s, skip' % key_id)
                return True
            if not my_keys.register_key(key_id, key_object, label=key_label):
                raise Exception('key register failed')
            else:
                lg.info('added new key %s, is_public=%s' % (key_id, key_object.isPublic()))
            p2p_service.SendAck(newpacket)
            if _Debug:
                lg.info('received and stored locally a new key %s, include_private=%s' % (key_id, key_json.get('include_private')))
            return True
        # received key is a private key
        if my_keys.is_key_registered(key_id):
            # check if we already have that key
            if my_keys.is_key_private(key_id):
                # we have already private key with same ID!!!
                if my_keys.get_private_key_raw(key_id) != key_object.toPrivateString():
                    # and this is a new private key : we should not overwrite!
                    raise Exception('private key already registered and it is not matching')
                # this is the same private key
                p2p_service.SendAck(newpacket)
                lg.warn('received existing private key: %s, skip' % key_id)
                return True
            # but we have a public key with same ID already
            if my_keys.get_public_key_raw(key_id) != key_object.toPublicString():
                # and we should not overwrite existing public key as well
                raise Exception('another public key already registered with that ID and it is not matching with private key')
            lg.info('erasing public key %s' % key_id)
            my_keys.erase_key(key_id)
            if not my_keys.register_key(key_id, key_object, label=key_label):
                raise Exception('key register failed')
            lg.info('added new key %s, is_public=%s' % (key_id, key_object.isPublic()))
            p2p_service.SendAck(newpacket)
            return True
        # no private key with given ID was registered
        if not my_keys.register_key(key_id, key_object, label=key_label):
            raise Exception('key register failed')
        lg.info('added new key %s, is_public=%s' % (key_id, key_object.isPublic()))
        p2p_service.SendAck(newpacket)
        return True
    except Exception as exc:
        lg.exc()
        p2p_service.SendFail(newpacket, str(exc))
    return False


def on_audit_key_received(newpacket, info, status, error_message):
    """
    Callback will be executed when remote user would like to check if I poses given key locally.
    """
    block = encrypted.Unserialize(newpacket.Payload)
    if block is None:
        lg.out(2, 'key_ring.on_audit_key_received ERROR reading data from %s' % newpacket.RemoteID)
        return False
    try:
        raw_payload = block.Data()
        json_payload = serialization.BytesToDict(raw_payload, keys_to_text=True, values_to_text=True)
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
    if not my_keys.is_key_registered(key_id, include_master=True):
        p2p_service.SendFail(newpacket, 'key not registered')
        return False
    if public_sample:
        response_payload = base64.b64encode(my_keys.encrypt(key_id, public_sample))
        p2p_service.SendAck(newpacket, response_payload)
        if _Debug:
            lg.info('remote user %s requested audit of public key %s' % (newpacket.OwnerID, key_id))
        return True
    if private_sample:
        if not my_keys.is_key_private(key_id):
            p2p_service.SendFail(newpacket, 'private key not registered')
            return False
        response_payload = base64.b64encode(my_keys.decrypt(key_id, private_sample))
        p2p_service.SendAck(newpacket, response_payload)
        if _Debug:
            lg.info('remote user %s requested audit of private key %s' % (newpacket.OwnerID, key_id))
        return True
    p2p_service.SendFail(newpacket, 'wrong audit request')
    return False

#------------------------------------------------------------------------------

def check_rename_my_keys():
    """
    Make sure all my keys have correct names according to known latest identities I have cached.
    For every key checks corresponding IDURL info and decides to rename it if key owner's identity was rotated.
    """
    keys_to_be_renamed = {}
    for key_id in list(my_keys.known_keys().keys()):
        key_glob_id = global_id.ParseGlobalID(key_id)
        owner_idurl = key_glob_id['idurl']
        if not owner_idurl.is_latest():
            keys_to_be_renamed[key_id] = global_id.MakeGlobalID(
                idurl=owner_idurl.to_bin(),
                key_alias=key_glob_id['key_alias'],
            )
    for current_key_id, new_key_id in keys_to_be_renamed.items():
        my_keys.rename_key(current_key_id, new_key_id)

#------------------------------------------------------------------------------

def do_backup_key(key_id, keys_folder=None, wait_result=False):
    """
    Send given key to my suppliers to store it remotely.
    This will make a regular backup copy of that key file - encrypted with my master key.
    """
    if _Debug:
        lg.out(_DebugLevel, 'key_ring.do_backup_key     key_id=%r' % key_id)
    if key_id == my_id.getGlobalID(key_alias='master') or key_id == 'master':
        lg.err('master key must never leave local host')
        if wait_result:
            return fail(Exception('master key must never leave local host'))
        return False
    if not my_keys.is_key_registered(key_id):
        lg.err('unknown key: "%s"' % key_id)
        if wait_result:
            return fail(Exception('unknown key: "%s"' % key_id))
        return False
    if not keys_folder:
        keys_folder = settings.KeyStoreDir()
    if my_keys.is_key_private(key_id):
        local_key_filepath = os.path.join(keys_folder, '%s.private' % key_id)
        remote_path_for_key = '.keys/%s.private' % key_id
    else:
        local_key_filepath = os.path.join(keys_folder, '%s.public' % key_id)
        remote_path_for_key = '.keys/%s.public' % key_id
    global_key_path = global_id.MakeGlobalID(
        key_alias='master', customer=my_id.getGlobalID(), path=remote_path_for_key)
    res = api.file_exists(global_key_path)
    if res['status'] == 'OK' and res['result']:
        lg.warn('key %s already exists in catalog' % global_key_path)
    else:
        res = api.file_create(global_key_path)
        if res['status'] != 'OK':
            lg.err('failed to create path "%s" in the catalog: %r' % (global_key_path, res))
            if wait_result:
                return fail(Exception('failed to create path "%s" in the catalog: %r' % (global_key_path, res)))
            return False
    res = api.file_upload_start(
        local_path=local_key_filepath,
        remote_path=global_key_path,
        wait_result=wait_result,
        open_share=False,
    )
    if not wait_result:
        if res['status'] != 'OK':
            lg.err('failed to upload key "%s": %r' % (global_key_path, res))
            return False
        if _Debug:
            lg.out(_DebugLevel, 'key_ring.do_backup_key key_id=%s : %r' % (key_id, res))
        return True

    backup_result = Deferred()

    # TODO: put that code bellow into api.file_upload_start() method with additional parameter

    def _job_done(result):
        if _Debug:
            lg.args(_DebugLevel, key_id=key_id, result=result)
        if result == 'done':
            backup_result.callback(True)
        else:
            backup_result.errback(Exception('failed to upload key "%s", backup is %r' % (key_id, result)))
        return None

    def _task_started(resp):
        if _Debug:
            lg.args(_DebugLevel, key_id=key_id, response=resp)
        if resp['status'] != 'OK':
            backup_result.errback(Exception('failed to upload key "%s", task was not started: %r' % (global_key_path, resp)))
            return None
        from storage import backup_control
        backupObj = backup_control.jobs().get(resp['version'])
        if not backupObj:
            backup_result.errback(Exception('failed to upload key "%s", task %r failed to start' % (global_key_path, resp['version'])))
            return None
        backupObj.resultDefer.addCallback(_job_done)
        backupObj.resultDefer.addErrback(backup_result.errback)
        return None

    if not isinstance(res, Deferred):
        res_defer = Deferred()
        res_defer.callback(res)
        res = res_defer
    res.addCallback(_task_started)
    res.addErrback(backup_result.errback)
    return backup_result


def do_restore_key(key_id, is_private, keys_folder=None, wait_result=False):
    """
    Restore given key from my suppliers if I do not have it locally.
    """
    if _Debug:
        lg.out(_DebugLevel, 'key_ring.do_restore_key     key_id=%r    is_private=%r' % (key_id, is_private, ))
    if my_keys.is_key_registered(key_id):
        lg.err('local key already exist: "%s"' % key_id)
        if wait_result:
            return fail(Exception('local key already exist: "%s"' % key_id))
        return False
    if not keys_folder:
        keys_folder = settings.KeyStoreDir()
    if is_private:
        remote_path_for_key = '.keys/%s.private' % key_id
    else:
        remote_path_for_key = '.keys/%s.public' % key_id
    global_key_path = global_id.MakeGlobalID(
        key_alias='master', customer=my_id.getGlobalID(), path=remote_path_for_key)
    ret = api.file_download_start(
        remote_path=global_key_path,
        destination_path=keys_folder,
        wait_result=True,
        open_share=False,
    )
    if not isinstance(ret, Deferred):
        lg.err('failed to download key "%s": %s' % (key_id, ret))
        if wait_result:
            return fail(Exception('failed to download key "%s": %s' % (key_id, ret)))
        return False

    result = Deferred()

    def _on_result(res):
        if not isinstance(res, dict):
            lg.err('failed to download key "%s": %s' % (key_id, res))
            if wait_result:
                result.errback(Exception('failed to download key "%s": %s' % (key_id, res)))
            return None
        if res['status'] != 'OK':
            lg.err('failed to download key "%s": %r' % (key_id, res))
            if wait_result:
                result.errback(Exception('failed to download key "%s": %r' % (key_id, res)))
            return None
        if not my_keys.load_key(key_id, keys_folder):
            lg.err('failed to read key "%s" from local folder "%s"' % (key_id, keys_folder))
            if wait_result:
                result.errback(Exception('failed to read key "%s" from local folder "%s"' % (key_id, keys_folder)))
            return None
        if _Debug:
            lg.out(_DebugLevel, 'key_ring.do_restore_key._on_result key_id=%s  is_private=%r : %r' % (key_id, is_private, res))
        if wait_result:
            result.callback(res)
        return None

    ret.addBoth(_on_result)

    if not wait_result:
        return True
    return result


def do_delete_key(key_id, is_private):
    """
    Remove given key from my suppliers nodes.
    """
    if is_private:
        remote_path_for_key = '.keys/%s.private' % key_id
    else:
        remote_path_for_key = '.keys/%s.public' % key_id
    global_key_path = global_id.MakeGlobalID(
        key_alias='master', customer=my_id.getGlobalID(), path=remote_path_for_key)
    res = api.file_delete(global_key_path)
    if res['status'] != 'OK':
        lg.err('failed to delete key "%s": %r' % (global_key_path, res))
        return False
    if _Debug:
        lg.out(_DebugLevel, 'key_ring.do_delete_key key_id=%s  is_private=%r : %r' % (key_id, is_private, res))
    return True
