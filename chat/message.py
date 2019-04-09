#!/usr/bin/python
# message.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (message.py) is part of BitDust Software.
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
.. module:: message

"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

import sys
import time
import base64

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in message.py')

from twisted.internet.defer import fail
from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

from logs import lg

from p2p import commands
from p2p import online_status
from p2p import propagate

from lib import strng
from lib import packetid
from lib import utime
from lib import serialization

from crypt import signed
from crypt import key
from crypt import my_keys

from contacts import identitycache

from userid import my_id
from userid import global_id

from transport import gateway

#------------------------------------------------------------------------------

MAX_PENDING_MESSAGES_PER_CONSUMER = 100

#------------------------------------------------------------------------------

_ConsumersCallbacks = {}
_ReceivedMessagesIDs = set()

_IncomingMessageCallbacks = []
_OutgoingMessageCallbacks = []

_MessageQueuePerConsumer = {}

_LastUserPingTime = {}
_PingTrustIntervalSeconds = 60 * 2

#------------------------------------------------------------------------------


def init():
    lg.out(4, "message.init")
    AddIncomingMessageCallback(push_incoming_message)
    AddOutgoingMessageCallback(push_outgoing_message)


def shutdown():
    lg.out(4, "message.shutdown")
    RemoveOutgoingMessageCallback(push_outgoing_message)
    RemoveIncomingMessageCallback(push_incoming_message)

#------------------------------------------------------------------------------

def received_messages_ids():
    global _ReceivedMessagesIDs
    return _ReceivedMessagesIDs


def message_queue():
    global _MessageQueuePerConsumer
    return _MessageQueuePerConsumer


def consumers_callbacks():
    global _ConsumersCallbacks
    return _ConsumersCallbacks

#------------------------------------------------------------------------------

def ConnectCorrespondent(idurl):
    pass


def UniqueID():
    return str(int(time.time() * 100.0))

#------------------------------------------------------------------------------

def AddIncomingMessageCallback(cb):
    """
    Calling with: (packet_in_object, private_message_object, decrypted_message_body)
    """
    global _IncomingMessageCallbacks
    if cb not in _IncomingMessageCallbacks:
        _IncomingMessageCallbacks.append(cb)
    else:
        lg.warn('callback method already exist')


def RemoveIncomingMessageCallback(cb):
    """
    """
    global _IncomingMessageCallbacks
    if cb in _IncomingMessageCallbacks:
        _IncomingMessageCallbacks.remove(cb)
    else:
        lg.warn('callback method not exist')


def AddOutgoingMessageCallback(cb):
    """
    Calling with: (message_body, private_message_object, remote_identity, outpacket, packet_out_object)
    """
    global _OutgoingMessageCallbacks
    if cb not in _OutgoingMessageCallbacks:
        _OutgoingMessageCallbacks.append(cb)
    else:
        lg.warn('callback method already exist')


def RemoveOutgoingMessageCallback(cb):
    """
    """
    global _OutgoingMessageCallbacks
    if cb in _OutgoingMessageCallbacks:
        _OutgoingMessageCallbacks.remove(cb)
    else:
        lg.warn('callback method not exist')

#------------------------------------------------------------------------------

class PrivateMessage(object):
    """
    A class to represent a message.

    We always encrypt messages with a session key so we need to package
    with encrypted body.
    """

    def __init__(self, recipient_global_id, sender=None, encrypted_session=None, encrypted_body=None):
        self.sender = sender or my_id.getGlobalID(key_alias='master')
        self.recipient = recipient_global_id
        self.encrypted_session = encrypted_session
        self.encrypted_body = encrypted_body
        if _Debug:
            lg.out(_DebugLevel, 'message.%s created' % self)

    def __str__(self):
        return 'PrivateMessage (%r->%r) : %r %r' % (
            self.sender,
            self.recipient,
            type(self.encrypted_session),
            type(self.encrypted_body),
        )

    def sender_id(self):
        return self.sender

    def recipient_id(self):
        return self.recipient

    def session_key(self):
        return self.encrypted_session

    def body(self):
        return self.encrypted_body

    def encrypt(self, message_body, encrypt_session_func=None):
        new_sessionkey = key.NewSessionKey()
        if not encrypt_session_func:
            if my_keys.is_key_registered(self.recipient):
                if _Debug:
                    lg.out(_DebugLevel, 'message.PrivateMessage.encrypt with "%s" key' % self.recipient)
                encrypt_session_func = lambda inp: my_keys.encrypt(self.recipient, inp)
        if not encrypt_session_func:
            glob_id = global_id.ParseGlobalID(self.recipient)
            if glob_id['key_alias'] == 'master':
                if glob_id['idurl'] == my_id.getLocalID():
                    lg.warn('making private message addressed to me ???')
                    if _Debug:
                        lg.out(_DebugLevel, 'message.PrivateMessage.encrypt with "master" key')
                    encrypt_session_func = lambda inp: my_keys.encrypt('master', inp)
                else:
                    remote_identity = identitycache.FromCache(glob_id['idurl'])
                    if not remote_identity:
                        raise Exception('remote identity is not cached yet, not able to encrypt the message')
                    if _Debug:
                        lg.out(_DebugLevel, 'message.PrivateMessage.encrypt with remote identity public key')
                    encrypt_session_func = remote_identity.encrypt
            else:
                own_key = global_id.MakeGlobalID(idurl=my_id.getLocalID(), key_alias=glob_id['key_alias'])
                if my_keys.is_key_registered(own_key):
                    if _Debug:
                        lg.out(_DebugLevel, 'message.PrivateMessage.encrypt with "%s" key' % own_key)
                    encrypt_session_func = lambda inp: my_keys.encrypt(own_key, inp)
        if not encrypt_session_func:
            raise Exception('can not find key for given recipient')
        self.encrypted_session = encrypt_session_func(new_sessionkey)
        self.encrypted_body = key.EncryptWithSessionKey(new_sessionkey, message_body)
        return self.encrypted_session, self.encrypted_body

    def decrypt(self, decrypt_session_func=None):
        if not decrypt_session_func:
            if my_keys.is_key_registered(self.recipient):
                if _Debug:
                    lg.out(_DebugLevel, 'message.PrivateMessage.decrypt with "%s" key' % self.recipient)
                decrypt_session_func = lambda inp: my_keys.decrypt(self.recipient, inp)
        if not decrypt_session_func:
            glob_id = global_id.ParseGlobalID(self.recipient)
            if glob_id['idurl'] == my_id.getLocalID():
                if glob_id['key_alias'] == 'master':
                    if _Debug:
                        lg.out(_DebugLevel, 'message.PrivateMessage.decrypt with "master" key')
                    decrypt_session_func = lambda inp: my_keys.decrypt('master', inp)
        if not decrypt_session_func:
            raise Exception('can not find key for given recipient: %s' % self.recipient)
        decrypted_sessionkey = decrypt_session_func(self.encrypted_session)
        return key.DecryptWithSessionKey(decrypted_sessionkey, self.encrypted_body)

    def serialize(self):
        dct = {
            'r': self.recipient,
            's': self.sender,
            'k': strng.to_text(base64.b64encode(strng.to_bin(self.encrypted_session))),
            'p': self.encrypted_body,
        }
        return serialization.DictToBytes(dct, encoding='utf-8')

    @staticmethod
    def deserialize(input_string):
        try:
            dct = serialization.BytesToDict(input_string, keys_to_text=True, encoding='utf-8')
            _recipient = dct['r']
            _sender = dct['s']
            _encrypted_session_key=base64.b64decode(strng.to_bin(dct['k']))
            _encrypted_body = dct['p']
            message_obj = PrivateMessage(
                recipient_global_id=_recipient,
                sender=_sender,
                encrypted_session=_encrypted_session_key,
                encrypted_body=_encrypted_body,
            )
        except:
            lg.exc()
            return None
        return message_obj


#------------------------------------------------------------------------------

def on_incoming_message(request, info, status, error_message):
    """
    Message came in for us
    """
    global _IncomingMessageCallbacks
    if _Debug:
        lg.out(_DebugLevel, "message.Message from " + str(request.OwnerID))
    private_message_object = PrivateMessage.deserialize(request.Payload)
    if private_message_object is None:
        lg.warn("PrivateMessage deserialize failed, can not extract message from request payload of %d bytes" % len(request.Payload))
    try:
        decrypted_message = private_message_object.decrypt()
        json_message = serialization.BytesToDict(
            decrypted_message,
            unpack_types=True,
            encoding='utf-8',
        )
    except:
        lg.exc()
        return False
    for known_id in received_messages_ids():
        if known_id == request.PacketID:
            if _Debug:
                lg.out(_DebugLevel, "message.Message SKIP, message %s found in history" % known_id)
            return False
    received_messages_ids().add(request.PacketID)
    from p2p import p2p_service
    p2p_service.SendAck(request)
    try:
        for cb in _IncomingMessageCallbacks:
            cb(request, private_message_object, json_message)
    except:
        lg.exc()
    if _Debug:
        lg.out(_DebugLevel, '        %s' % json_message)
    return True


def on_ping_success(response_tuple, idurl):
    global _LastUserPingTime
    _LastUserPingTime[idurl] = time.time()
    lg.info('node %s replied with Ack : %s' % (idurl, response_tuple, ))


def on_message_delivered(idurl, json_data, recipient_global_id, packet_id, response, info, result_defer=None):
    global _LastUserPingTime
    lg.info('message %s delivered to %s : %s with %s' % (packet_id, recipient_global_id, response, info, ))
    _LastUserPingTime[idurl] = time.time()
    if result_defer and not result_defer.called:
        result_defer.callback(response)


def on_message_failed(idurl, json_data, recipient_global_id, packet_id, response, info, result_defer=None, error=None):
    global _LastUserPingTime
    lg.err('message %s failed sending to %s in %s / %s because %r' % (
        packet_id, recipient_global_id, response, info, error, ))
    if idurl in _LastUserPingTime:
        _LastUserPingTime[idurl] = 0
    if result_defer and not result_defer.called:
        result_defer.errback(Exception(response or str(error)))

#------------------------------------------------------------------------------

def do_send_message(json_data, recipient_global_id, packet_id, timeout, result_defer=None):
    global _OutgoingMessageCallbacks
    remote_idurl = global_id.GlobalUserToIDURL(recipient_global_id)
    if not remote_idurl:
        raise Exception('invalid recipient')
    remote_identity = identitycache.FromCache(remote_idurl)
    if not remote_identity:
        raise Exception('remote identity object not exist in cache')
    message_body = serialization.DictToBytes(
        json_data,
        pack_types=True,
        encoding='utf-8',
    )
    lg.out(4, "message.do_send_message to %s with %d bytes message" % (recipient_global_id, len(message_body)))
    try:
        private_message_object = PrivateMessage(recipient_global_id=recipient_global_id)
        private_message_object.encrypt(message_body)
    except Exception as exc:
        lg.exc()
        raise Exception('message encryption failed')
    Payload = private_message_object.serialize()
    lg.out(4, "        payload is %d bytes, remote idurl is %s" % (len(Payload), remote_idurl))
    outpacket = signed.Packet(
        commands.Message(),
        my_id.getLocalID(),
        my_id.getLocalID(),
        packet_id,
        Payload,
        remote_idurl,
    )
    result = gateway.outbox(outpacket, wide=True, response_timeout=timeout, callbacks={
        commands.Ack(): lambda response, info: on_message_delivered(
            remote_idurl, json_data, recipient_global_id, packet_id, response, info, result_defer, ),
        commands.Fail(): lambda response, info: on_message_failed(
            remote_idurl, json_data, recipient_global_id, packet_id, response, info,
            result_defer=result_defer, error='fail received'),
        None: lambda pkt_out: on_message_failed(
            remote_idurl, json_data, recipient_global_id, packet_id, None, None,
            result_defer=result_defer, error='timeout', ),  # timeout
    })
    try:
        for cp in _OutgoingMessageCallbacks:
            cp(json_data, private_message_object, remote_identity, outpacket, result)
    except:
        lg.exc()
        raise Exception('failed sending message')
    return result


def send_message(json_data, recipient_global_id, packet_id=None, timeout=None):
    """
    Send command.Message() packet to remote peer.
    Returns Deferred (if remote_idurl was not cached yet) or outbox packet object.
    """
    global _LastUserPingTime
    global _PingTrustIntervalSeconds
    if not packet_id:
        packet_id = packetid.UniqueID()
    lg.out(4, "message.send_message to %s with PackteID=%s" % (recipient_global_id, packet_id))
    remote_idurl = global_id.GlobalUserToIDURL(recipient_global_id)
    if not remote_idurl:
        return fail(Exception('invalid recipient'))
    ret = Deferred()
    if remote_idurl not in _LastUserPingTime:
        is_expired = True
    else:
        is_expired = time.time() - _LastUserPingTime[remote_idurl] > _PingTrustIntervalSeconds
    remote_identity = identitycache.FromCache(remote_idurl)
    is_online = online_status.isOnline(remote_idurl)
    lg.out(4, "    is_expired=%r  remote_identity=%r  is_online=%r" % (
        is_expired, bool(remote_identity), is_online, ))
    if is_expired or remote_identity is None or not is_online:
        d = propagate.PingContact(remote_idurl, timeout=timeout or 5)
        d.addCallback(lambda response_tuple: on_ping_success(response_tuple, remote_idurl))
        d.addCallback(lambda response_tuple: do_send_message(
            json_data, recipient_global_id, packet_id, timeout, result_defer=ret))
        d.addErrback(lambda err: on_message_failed(
            remote_idurl, json_data, recipient_global_id, packet_id, None, None, result_defer=ret, error=err))
        return ret
    try:
        do_send_message(json_data, recipient_global_id, packet_id, timeout, ret)
    except Exception as exc:
        lg.warn(str(exc))
        on_message_failed(remote_idurl, json_data, recipient_global_id, packet_id, None, None, error=exc)
        ret.errback(exc)
    return ret

#------------------------------------------------------------------------------

def consume_messages(consumer_id):
    """
    """
    if consumer_id not in consumers_callbacks():
        consumers_callbacks()[consumer_id] = []
    d = Deferred()
    consumers_callbacks()[consumer_id].append(d)
    if _Debug:
        lg.out(_DebugLevel, 'message.consume_messages added callback for consumer "%s", %d total callbacks' % (
            consumer_id, len(consumers_callbacks()[consumer_id])))
    reactor.callLater(0, pop_messages)  # @UndefinedVariable
    return d


def push_incoming_message(request, private_message_object, json_message):
    """
    """
    for consumer_id in consumers_callbacks().keys():
        if consumer_id not in message_queue():
            message_queue()[consumer_id] = []
        message_queue()[consumer_id].append({
            'type': 'private_message',
            'dir': 'incoming',
            'to': private_message_object.recipient_id(),
            'from': private_message_object.sender_id(),
            'data': json_message,
            'id': request.PacketID,
            'time': utime.get_sec1970(),
        })
        if _Debug:
            lg.out(_DebugLevel, 'message.push_incoming_message "%s" for consumer "%s", %d pending messages' % (
                request.PacketID, consumer_id, len(message_queue()[consumer_id])))
    reactor.callLater(0, pop_messages)  # @UndefinedVariable


def push_outgoing_message(json_message, private_message_object, remote_identity, request, result):
    """
    """
    for consumer_id in consumers_callbacks().keys():
        if consumer_id not in message_queue():
            message_queue()[consumer_id] = []
        message_queue()[consumer_id].append({
            'type': 'private_message',
            'dir': 'outgoing',
            'to': private_message_object.recipient_id(),
            'from': private_message_object.sender_id(),
            'data': json_message,
            'id': request.PacketID,
            'time': utime.get_sec1970(),
        })
        if _Debug:
            lg.out(_DebugLevel, 'message.push_outgoing_message "%s" for consumer "%s", %d pending messages' % (
                request.PacketID, consumer_id, len(message_queue()[consumer_id])))
    reactor.callLater(0, pop_messages)  # @UndefinedVariable


def pop_messages():
    """
    """
    for consumer_id in consumers_callbacks().keys():
        if consumer_id not in message_queue() or len(message_queue()[consumer_id]) == 0:
            continue
        registered_callbacks = consumers_callbacks()[consumer_id]
        pending_messages = message_queue()[consumer_id]
        if len(registered_callbacks) == 0 and len(pending_messages) > MAX_PENDING_MESSAGES_PER_CONSUMER:
            consumers_callbacks().pop(consumer_id)
            message_queue().pop(consumer_id)
            if _Debug:
                lg.out(_DebugLevel, 'message.pop_message STOPPED consumer "%s", too much pending messages but no callbacks' % consumer_id)
            continue
        for consumer_callback in registered_callbacks:
            if not consumer_callback:
                if _Debug:
                    lg.out(_DebugLevel, 'message.pop_message %d messages waiting consuming by "%s", no callback yet' % (
                        len(message_queue()[consumer_id]), consumer_id))
                continue
            if consumer_callback.called:
                if _Debug:
                    lg.out(_DebugLevel, 'message.pop_message %d messages waiting consuming by "%s", callback state is "called"' % (
                        len(message_queue()[consumer_id]), consumer_id))
                continue
            consumer_callback.callback(pending_messages)
            message_queue()[consumer_id] = []
            if _Debug:
                lg.out(_DebugLevel, 'message.pop_message %d messages consumed by "%s"' % (len(pending_messages), consumer_id))
        consumers_callbacks()[consumer_id] = []

#------------------------------------------------------------------------------
# 
# def start_consuming(consumer_id):
#     """
#     """
#     if consumer_id in consumers_callbacks():
#         return False
#     if consumer_id not in consumers_callbacks():
#         consumers_callbacks()[consumer_id] = []
#     return True
# 
# 
# def stop_consuming(consumer_id):
#     """
#     """
#     if consumer_id not in consumers_callbacks():
#         return False
#     if len(consumers_callbacks()[consumer_id]) == 0:
#         return False
#     for consumers_callback in consumers_callbacks()[consumer_id]:
#         if consumers_callback:
#             if consumers_callbacks()[consumer_id].called:
#                 lg.warn('callback already called for consumer "%s"' % consumer_id)
#                 continue
#             consumers_callbacks()[consumer_id].callback([])
#     consumers_callbacks().pop(consumer_id, None)
#     message_queue().pop(consumer_id, None)
#     return True
# 
# 
# def consume_message(consumer_id):
#     """
#     """
#     if consumer_id not in consumers_callbacks():
#         return None
#     d = Deferred()
#     consumers_callbacks()[consumer_id].append(d)
#     if _Debug:
#         lg.out(_DebugLevel, 'message.consume_message added callback for consumer "%s", %d total callbacks' % (
#             consumer_id, len(consumers_callbacks()[consumer_id])))
#     reactor.callLater(0, pop_messages)
#     return d

#------------------------------------------------------------------------------
