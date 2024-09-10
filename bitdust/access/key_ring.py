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

_Debug = False
_DebugLevel = 8

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

from bitdust.logs import lg

from bitdust.lib import strng
from bitdust.lib import serialization

from bitdust.main import settings

from bitdust.contacts import identitycache
from bitdust.contacts import contactsdb

from bitdust.p2p import online_status
from bitdust.p2p import p2p_service
from bitdust.p2p import commands

from bitdust.crypt import key
from bitdust.crypt import my_keys
from bitdust.crypt import encrypted

from bitdust.storage import backup_matrix

from bitdust.interface import api

from bitdust.userid import global_id
from bitdust.userid import my_id

#------------------------------------------------------------------------------

_MyKeysInSync = False

#------------------------------------------------------------------------------


def init():
    if _Debug:
        lg.out(_DebugLevel, 'key_ring.init')
    my_keys.check_rename_my_keys()


def shutdown():
    if _Debug:
        lg.out(_DebugLevel, 'key_ring.shutdown')


#------------------------------------------------------------------------------


def _do_request_service_keys_registry(key_id, idurl, include_private, include_signature, timeout, result):
    p2p_service.SendRequestService(
        idurl,
        'service_keys_registry',
        timeout=timeout,
        callbacks={
            commands.Ack(): lambda response, info: _on_service_keys_registry_response(response, info, key_id, idurl, include_private, include_signature, result, timeout),
            commands.Fail(): lambda response, info: result.errback(Exception('"service_keys_registry" not started on remote node')),
            None: lambda pkt_out: result.errback(Exception('timeout')),
        },
    )
    return result


def _on_service_keys_registry_response(response, info, key_id, idurl, include_private, include_signature, result, timeout):
    if not strng.to_text(response.Payload).startswith('accepted'):
        if not result.called:
            result.errback(Exception('request for "service_keys_registry" refused by remote node'))
        return None
    d = transfer_key(
        key_id,
        trusted_idurl=idurl,
        include_private=include_private,
        include_signature=include_signature,
        timeout=timeout,
        result=result,
    )
    d.addErrback(lambda *a: lg.err('transfer key failed: %s' % str(*a)))
    return None


def _on_transfer_key_response(response, info, key_id, result):
    if not response or not info:
        if not result.called:
            result.errback(Exception('timeout'))
        if _Debug:
            lg.warn('transfer failed, response timeout')
        return None
    if response.Command == commands.Ack():
        if not result.called:
            result.callback(response)
        if _Debug:
            lg.info('key %s transfer success to %s' % (key_id, response.OwnerID))
        return None
    if response.Command == commands.Fail():
        err_msg = strng.to_text(response.Payload, errors='ignore')
        if err_msg.count('key already registered'):
            # it is okay to have "Fail()" response in that case
            if not result.called:
                result.callback(response)
            if _Debug:
                lg.warn('key %s already registered on %s' % (key_id, response.OwnerID))
            return None
    if not result.called:
        result.errback(Exception(response.Payload))
    if _Debug:
        lg.warn('key transfer failed: %s' % response.Payload)
    return None


def transfer_key(key_id, trusted_idurl, include_private=False, include_signature=False, timeout=None, result=None):
    """
    Actually sending given key to remote user.
    """
    if _Debug:
        lg.out(_DebugLevel, 'key_ring.transfer_key  %s -> %s' % (key_id, trusted_idurl))
    if not timeout:
        timeout = settings.P2PTimeOut()
    key_id = my_keys.latest_key_id(key_id)
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
        key_json = my_keys.make_key_info(
            key_object,
            key_id=key_id,
            include_private=include_private,
            generate_signature=include_signature,
        )
    except Exception as exc:
        lg.exc()
        result.errback(exc)
        return result
    if include_signature and not my_keys.verify_key_info_signature(key_json):
        lg.err('signature verification failed after making key info: %r' % key_json)
        result.errback(Exception('signature verification failed after making key info: "%s"' % key_id))
        return result
    if _Debug:
        lg.args(_DebugLevel, key_json=key_json)
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


def share_key(key_id, trusted_idurl, include_private=False, include_signature=False, timeout=None):
    """
    Method to be used to send given key to one trusted user.
    Make sure remote user is identified and connected.
    Returns deferred, callback will be fired with response Ack() packet argument.
    """
    if _Debug:
        lg.args(_DebugLevel, key_id=key_id, trusted_idurl=trusted_idurl)
    if timeout is None:
        timeout = settings.P2PTimeOut()
    key_id = my_keys.latest_key_id(key_id)
    result = Deferred()
    d = online_status.ping(
        idurl=trusted_idurl,
        ack_timeout=timeout,
        channel='share_key',
        keep_alive=False,
    )
    d.addCallback(lambda ok: _do_request_service_keys_registry(
        key_id,
        trusted_idurl,
        include_private,
        include_signature,
        timeout,
        result,
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
            lg.out(_DebugLevel, 'key_ring._on_audit_public_key_response : %s on %s' % (key_id, untrusted_idurl))
        result.callback(True)
        return True
    lg.warn('key %s on %s is not OK' % (key_id, untrusted_idurl))
    result.callback(False)
    return False


def audit_public_key(key_id, untrusted_idurl, timeout=None):
    """
    Be sure remote user stores given public key.
    I also need to stores that public key in order to do such audit.
    I will send him a random string, he needs to encrypt it and send me back.
    I can compare his encrypted output with mine.
    Returns Deferred object.
    """
    if _Debug:
        lg.out(_DebugLevel, 'key_ring.audit_public_key   testing %s from %s' % (key_id, untrusted_idurl))
    if not timeout:
        timeout = settings.P2PTimeOut()
    key_id = my_keys.latest_key_id(key_id)
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
        },
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
            commands.Ack(): lambda response, info: _on_audit_public_key_response(response, info, key_id, untrusted_idurl, public_test_sample, result),
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
            lg.out(_DebugLevel, 'key_ring._on_audit_private_key_response : %s on %s' % (key_id, untrusted_idurl))
        result.callback(True)
        return True
    lg.warn('key %s on %s is not OK' % (key_id, untrusted_idurl))
    result.callback(False)
    return False


def audit_private_key(key_id, untrusted_idurl, timeout=None):
    """
    Be sure remote user possess given private key.
    I need to possess the public key to be able to audit.
    I will generate a random string, encrypt it with given key public key and send encrypted string to him.
    He will decrypt and send me back original string.
    Returns Deferred object.
    """
    if _Debug:
        lg.out(_DebugLevel, 'key_ring.audit_private_key   testing %s from %s' % (key_id, untrusted_idurl))
    if not timeout:
        timeout = settings.P2PTimeOut()
    key_id = my_keys.latest_key_id(key_id)
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
    remote_idurl = recipient_id_obj.getIDURL()
    private_test_sample = key.NewSessionKey(session_key_type=key.SessionKeyType())
    if untrusted_idurl == creator_idurl and key_alias == 'master':
        lg.info('doing audit of master key %r for remote user %r' % (key_id, remote_idurl))
        private_test_encrypted_sample = recipient_id_obj.encrypt(private_test_sample)
    else:
        if not my_keys.is_key_registered(key_id):
            lg.warn('unknown key: "%s"' % key_id)
            result.errback(Exception('unknown key: "%s"' % key_id))
            return result
        lg.info('doing audit of private key %r for remote user %r' % (key_id, remote_idurl))
        private_test_encrypted_sample = my_keys.encrypt(key_id, private_test_sample)
    json_payload = {
        'key_id': key_id,
        'audit': {
            'public_sample': '',
            'private_sample': base64.b64encode(private_test_encrypted_sample),
        },
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
        remote_idurl=remote_idurl,
        encrypted_payload=encrypted_payload,
        packet_id=key_id,
        timeout=timeout,
        callbacks={
            commands.Ack(): lambda response, info: _on_audit_private_key_response(response, info, key_id, untrusted_idurl, private_test_sample, result),
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
        lg.err('failed reading key info from %s' % newpacket.RemoteID)
        return False
    try:
        key_data = block.Data()
        key_json = serialization.BytesToDict(key_data, keys_to_text=True, values_to_text=True)
        # key_id = strng.to_text(key_json['key_id'])
        key_label = strng.to_text(key_json.get('label', ''))
        key_id, key_object = my_keys.read_key_info(key_json)
        if key_object.isSigned():
            if not my_keys.verify_key_info_signature(key_json):
                raise Exception('received key signature verification failed: %r' % key_json)
            # TODO: must also compare "signature_pubkey" with pub key of the creator of the key!
        if key_object.isPublic():
            # received key is a public key
            if my_keys.is_key_registered(key_id):
                # but we already have a key with that ID
                if my_keys.is_key_private(key_id):
                    # we should not overwrite existing private key
                    # TODO: check other scenarios
                    lg.warn('received public key, but private key is already registered %r' % key_id)
                    p2p_service.SendAck(newpacket)
                    return True
                if my_keys.get_public_key_raw(key_id) != key_object.toPublicString():
                    my_keys.erase_key(key_id)
                    if not my_keys.register_key(key_id, key_object, label=key_label):
                        raise Exception('key register failed')
                    else:
                        lg.info('replaced existing key %s, is_public=%s' % (key_id, key_object.isPublic()))
                    # normally should not overwrite existing public key
                    # TODO: look more if need to add some extra checks
                    # for example need to be able to overwrite or erase remotely some keys to cleanup
                    # raise Exception('another public key already registered with %r and new key is not matching' % key_id)
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
                    raise Exception('private key already registered and it is not matching with received copy')
                # this is the same private key
                p2p_service.SendAck(newpacket)
                lg.warn('received again an exact copy of already existing private key: %s, skip' % key_id)
                return True
            # but we have a public key with same ID already
            # if my_keys.get_public_key_raw(key_id) != key_object.toPublicString():
            #     # and we should not overwrite existing public key as well
            #     raise Exception('another public key already registered with that ID and it is not matching with private key')
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
        p2p_service.SendFail(newpacket, strng.to_text(exc))
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
        key_id = my_keys.latest_key_id(json_payload['key_id'])
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


def do_backup_key(key_id, keys_folder=None):
    """
    Send given key to my suppliers to store it remotely.
    This will make a regular backup copy of that key file - encrypted with my master key.
    """
    key_id = my_keys.latest_key_id(key_id)
    if _Debug:
        lg.out(_DebugLevel, 'key_ring.do_backup_key     key_id=%r' % key_id)
    if key_id == my_id.getGlobalID(key_alias='master') or key_id == 'master':
        lg.err('master key must never leave local host')
        return fail(Exception('master key must never leave local host'))
    if not my_keys.is_key_registered(key_id):
        lg.err('unknown key: "%s"' % key_id)
        return fail(Exception('unknown key: "%s"' % key_id))
    if not keys_folder:
        keys_folder = settings.KeyStoreDir()
    if my_keys.is_key_private(key_id):
        local_key_filepath = os.path.join(keys_folder, '%s.private' % key_id)
        remote_path_for_key = '.keys/%s.private' % key_id
    else:
        local_key_filepath = os.path.join(keys_folder, '%s.public' % key_id)
        remote_path_for_key = '.keys/%s.public' % key_id
    global_key_path = global_id.MakeGlobalID(key_alias='master', customer=my_id.getGlobalID(), path=remote_path_for_key)
    res = api.file_exists(global_key_path)
    if res['status'] == 'OK' and res['result'] and res['result'].get('exist'):
        from bitdust.storage import backup_control
        lg.warn('key %s already exists in catalog' % global_key_path)
        global_key_path_id = res['result'].get('path_id')
        if global_key_path_id and backup_control.IsPathInProcess(global_key_path_id):
            lg.warn('skip, another backup for key already started: %s' % global_key_path_id)
            backup_id_list = backup_control.FindRunningBackup(global_key_path_id)
            if backup_id_list:
                backup_id = backup_id_list[0]
                backup_job = backup_control.GetRunningBackupObject(backup_id)
                if backup_job:
                    backup_result = Deferred()
                    backup_job.resultDefer.addCallback(lambda resp: backup_result.callback(True) if resp == 'done' else backup_result.errback(Exception('failed to upload key "%s", task was not started: %r' % (global_key_path, resp))))
                    backup_job.resultDefer.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='key_ring.do_backup_key')
                    backup_job.resultDefer.addErrback(backup_result.errback)
                    if _Debug:
                        lg.args(_DebugLevel, backup_id=backup_id, global_key_path_id=global_key_path_id)
                    return backup_result
                else:
                    lg.warn('did not found running backup job: %r' % backup_id)
            else:
                lg.warn('did not found running backup id for path: %r' % global_key_path_id)
    else:
        res = api.file_create(global_key_path)
        if res['status'] != 'OK':
            lg.err('failed to create path "%s" in the catalog: %r' % (global_key_path, res))
            return fail(Exception('failed to create path "%s" in the catalog: %r' % (global_key_path, res)))
    res = api.file_upload_start(
        local_path=local_key_filepath,
        remote_path=global_key_path,
        wait_result=True,
    )
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
            lg.args(_DebugLevel, key_id=key_id, upload_response_status=resp['status'])
        if resp['status'] != 'OK':
            backup_result.errback(Exception('failed to upload key "%s", task was not started: %r' % (global_key_path, resp)))
            return None
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
        lg.out(_DebugLevel, 'key_ring.do_restore_key     key_id=%r    is_private=%r' % (key_id, is_private))
    key_id = my_keys.latest_key_id(key_id)
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
    global_key_path = global_id.MakeGlobalID(key_alias='master', customer=my_id.getGlobalID(), path=remote_path_for_key)
    ret = api.file_download_start(
        remote_path=global_key_path,
        destination_path=keys_folder,
        wait_result=True,
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
    global_key_path = global_id.MakeGlobalID(key_alias='master', customer=my_id.getGlobalID(), path=remote_path_for_key)
    res = api.file_delete(global_key_path)
    if res['status'] != 'OK':
        lg.err('failed to delete key "%s": %r' % (global_key_path, res))
        return False
    if _Debug:
        lg.out(_DebugLevel, 'key_ring.do_delete_key key_id=%s  is_private=%r : %r' % (key_id, is_private, res))
    return True


#------------------------------------------------------------------------------


def on_files_received(newpacket, info):
    list_files_global_id = global_id.ParseGlobalID(newpacket.PacketID)
    if not list_files_global_id['idurl']:
        lg.warn('invalid PacketID: %s' % newpacket.PacketID)
        return False
    incoming_key_id = list_files_global_id['key_id']
    if not my_keys.is_valid_key_id(incoming_key_id):
        lg.warn('ignore, invalid key id in packet %s' % newpacket)
        return False
    if list_files_global_id['key_alias'] == 'master':
        if _Debug:
            lg.dbg(_DebugLevel, 'ignore %s packet which seems to came from my own supplier' % newpacket)
        # only process list Files() from other customers who granted me access to their files
        return False
    if not my_keys.is_key_private(incoming_key_id):
        lg.warn('private key is not registered : %s' % incoming_key_id)
        p2p_service.SendFail(newpacket, 'private key is not registered')
        return False
    if list_files_global_id['key_alias'].startswith('share_'):
        from bitdust.access import shared_access_coordinator
        return shared_access_coordinator.on_list_files_verified(newpacket, list_files_global_id)
    # for other shared files that are not controlled by shared_access_coordinator(): message archive keys are starting with "group_"
    try:
        block = encrypted.Unserialize(newpacket.Payload, decrypt_key=incoming_key_id)
    except:
        lg.exc(newpacket.Payload)
        return False
    if block is None:
        lg.warn('failed reading data from %s' % newpacket.RemoteID)
        return False
    try:
        raw_files = block.Data()
    except:
        lg.exc()
        return False
    from bitdust.storage import index_synchronizer
    from bitdust.storage import backup_control
    from bitdust.storage import backup_fs
    # otherwise this must be an external supplier sending us a files he stores for trusted customer
    external_supplier_idurl = block.CreatorID
    try:
        supplier_raw_list_files = backup_control.UnpackListFiles(raw_files, settings.ListFilesFormat())
    except:
        lg.exc()
        return False
    # need to detect supplier position from the list of packets
    # and place that supplier on the correct position in contactsdb
    supplier_pos = backup_matrix.DetectSupplierPosition(supplier_raw_list_files)
    trusted_customer_idurl = list_files_global_id['idurl']
    known_supplier_pos = contactsdb.supplier_position(external_supplier_idurl, trusted_customer_idurl)
    if known_supplier_pos < 0:
        lg.warn('received %r from an unknown node %r which is not a supplier of %r' % (newpacket, external_supplier_idurl, trusted_customer_idurl))
        return False
    if _Debug:
        lg.args(_DebugLevel, sz=len(supplier_raw_list_files), s=external_supplier_idurl, pos=supplier_pos, known_pos=known_supplier_pos, pid=newpacket.PacketID)
    if supplier_pos >= 0:
        if known_supplier_pos != supplier_pos:
            lg.err('known external supplier %r position %d is not matching with received list files position %d for customer %s' % (external_supplier_idurl, known_supplier_pos, supplier_pos, trusted_customer_idurl))
            return False
    else:
        lg.warn('not possible to detect external supplier position for customer %s from received list files, known position is %s' % (trusted_customer_idurl, known_supplier_pos))
        supplier_pos = known_supplier_pos
    is_in_sync = index_synchronizer.is_synchronized() and backup_fs.revision() > 0
    remote_files_changed, _, _, _ = backup_matrix.process_raw_list_files(
        supplier_num=supplier_pos,
        list_files_text_body=supplier_raw_list_files,
        customer_idurl=trusted_customer_idurl,
        is_in_sync=is_in_sync,
    )
    if remote_files_changed:
        backup_matrix.SaveLatestRawListFiles(
            supplier_idurl=external_supplier_idurl,
            raw_data=supplier_raw_list_files,
            customer_idurl=trusted_customer_idurl,
        )
    # finally sending Ack() packet back
    p2p_service.SendAck(newpacket)
    if remote_files_changed:
        lg.info('received updated list of files from external supplier %s for customer %s' % (external_supplier_idurl, trusted_customer_idurl))
    return True
