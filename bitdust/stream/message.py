#!/usr/bin/python
# message.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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

_Debug = False
_DebugLevel = 8

#------------------------------------------------------------------------------

import time
import base64

#------------------------------------------------------------------------------

from twisted.internet.defer import fail
from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.main import config
from bitdust.main import settings

from bitdust.p2p import commands
from bitdust.p2p import online_status
from bitdust.p2p import p2p_service

from bitdust.lib import packetid
from bitdust.lib import utime
from bitdust.lib import serialization
from bitdust.lib import jsn
from bitdust.lib import strng

from bitdust.crypt import key
from bitdust.crypt import my_keys

from bitdust.contacts import identitycache

from bitdust.userid import id_url
from bitdust.userid import my_id
from bitdust.userid import global_id

#------------------------------------------------------------------------------

MAX_PENDING_MESSAGES_PER_CONSUMER = 100

#------------------------------------------------------------------------------

_ConsumersCallbacks = {}
_ReceivedMessagesIDs = []

_IncomingMessageCallbacks = []
_OutgoingMessageCallbacks = []

_MessageQueuePerConsumer = {}

_LastUserPingTime = {}
_PingTrustIntervalSeconds = 60*5

#------------------------------------------------------------------------------


def init():
    if _Debug:
        lg.out(_DebugLevel, 'message.init')
    AddIncomingMessageCallback(push_incoming_message)
    AddOutgoingMessageCallback(push_outgoing_message)


def shutdown():
    if _Debug:
        lg.out(_DebugLevel, 'message.shutdown')
    RemoveOutgoingMessageCallback(push_outgoing_message)
    RemoveIncomingMessageCallback(push_incoming_message)


#------------------------------------------------------------------------------


def received_messages_ids(erase_old_records=False):
    global _ReceivedMessagesIDs
    if erase_old_records:
        _ReceivedMessagesIDs = _ReceivedMessagesIDs[50:]
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
    return str(int(time.time()*100.0))


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


def InsertIncomingMessageCallback(cb):
    """
    Calling with: (packet_in_object, private_message_object, decrypted_message_body)
    """
    global _IncomingMessageCallbacks
    if cb not in _IncomingMessageCallbacks:
        _IncomingMessageCallbacks.insert(0, cb)
    else:
        lg.warn('callback method already exist')


def RemoveIncomingMessageCallback(cb):
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

    def __init__(self, recipient, sender=None, encrypted_session=None, encrypted_body=None):
        self.sender = strng.to_text(sender or my_id.getGlobalID(key_alias='master'))
        self.recipient = strng.to_text(recipient)
        self.encrypted_session = encrypted_session
        self.encrypted_body = encrypted_body

    def __str__(self):
        return 'PrivateMessage(%s->%s)' % (
            self.sender,
            self.recipient,
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
        if _Debug:
            lg.args(_DebugLevel, encrypt_session_func=encrypt_session_func, recipient=self.recipient)
        new_sessionkey = key.NewSessionKey(session_key_type=key.SessionKeyType())
        if not encrypt_session_func:
            if my_keys.is_key_registered(self.recipient):
                if _Debug:
                    lg.dbg(_DebugLevel, 'with registered key %r' % self.recipient)
                encrypt_session_func = lambda inp: my_keys.encrypt(self.recipient, inp)
        if not encrypt_session_func:
            glob_id = global_id.NormalizeGlobalID(self.recipient)
            if glob_id['key_alias'] == 'master':
                if glob_id['idurl'] == my_id.getIDURL():
                    lg.warn('making encrypted message addressed to me ?')
                    encrypt_session_func = lambda inp: my_keys.encrypt('master', inp)
                else:
                    remote_identity = identitycache.FromCache(glob_id['idurl'])
                    if not remote_identity:
                        raise Exception('remote identity is not cached yet, not able to encrypt the message')
                    if _Debug:
                        lg.dbg(_DebugLevel, 'with remote identity public key %r' % glob_id['idurl'])
                    encrypt_session_func = remote_identity.encrypt
            else:
                own_key = global_id.MakeGlobalID(idurl=my_id.getIDURL(), key_alias=glob_id['key_alias'])
                if my_keys.is_key_registered(own_key):
                    if _Debug:
                        lg.dbg(_DebugLevel, 'with registered key (found by alias) %r' % own_key)
                    encrypt_session_func = lambda inp: my_keys.encrypt(own_key, inp)
        if not encrypt_session_func:
            raise Exception('can not find key for given recipient')
        self.encrypted_session = encrypt_session_func(new_sessionkey)
        self.encrypted_body = key.EncryptWithSessionKey(new_sessionkey, message_body, session_key_type=key.SessionKeyType())
        return self.encrypted_session, self.encrypted_body

    def decrypt(self, decrypt_session_func=None):
        if _Debug:
            lg.args(_DebugLevel, decrypt_session_func=decrypt_session_func, recipient=self.recipient)
        if not decrypt_session_func:
            if my_keys.is_key_registered(self.recipient):
                if _Debug:
                    lg.dbg(_DebugLevel, 'decrypt with registered key %r' % self.recipient)
                decrypt_session_func = lambda inp: my_keys.decrypt(self.recipient, inp)
        if not decrypt_session_func:
            glob_id = global_id.NormalizeGlobalID(self.recipient)
            if glob_id['idurl'] == my_id.getIDURL():
                if glob_id['key_alias'] == 'master':
                    if _Debug:
                        lg.dbg(_DebugLevel, 'decrypt with my master key %r' % self.recipient)
                    decrypt_session_func = lambda inp: my_keys.decrypt('master', inp)
        if not decrypt_session_func:
            raise Exception('can not find key for given recipient: %s' % self.recipient)
        decrypted_sessionkey = decrypt_session_func(self.encrypted_session)
        return key.DecryptWithSessionKey(decrypted_sessionkey, self.encrypted_body, session_key_type=key.SessionKeyType())

    def serialize(self):
        dct = {
            'r': self.recipient,
            's': self.sender,
            'k': strng.to_text(base64.b64encode(strng.to_bin(self.encrypted_session))),
            'p': self.encrypted_body,
        }
        return serialization.DictToBytes(dct, encoding='utf-8')

    @classmethod
    def deserialize(cls, input_string):
        try:
            dct = serialization.BytesToDict(input_string, keys_to_text=True, encoding='utf-8')
            message_obj = cls(
                recipient=strng.to_text(dct['r']),
                sender=strng.to_text(dct['s']),
                encrypted_session=base64.b64decode(strng.to_bin(dct['k'])),
                encrypted_body=dct['p'],
            )
        except:
            lg.exc()
            return None
        return message_obj


#------------------------------------------------------------------------------


class GroupMessage(PrivateMessage):

    def __str__(self):
        return 'GroupMessage(%s->%s)' % (
            self.sender,
            self.recipient,
        )


#------------------------------------------------------------------------------


def on_incoming_message(request, info, status, error_message):
    """
    Message came in for us
    """
    global _IncomingMessageCallbacks
    if _Debug:
        lg.out(_DebugLevel, 'message.on_incoming_message new PrivateMessage %r from %s' % (request.PacketID, request.OwnerID))
    private_message_object = PrivateMessage.deserialize(request.Payload)
    if private_message_object is None:
        lg.err('PrivateMessage deserialize failed, can not extract message from request payload of %d bytes' % len(request.Payload))
        return False
    try:
        decrypted_message = private_message_object.decrypt()
        json_message = serialization.BytesToDict(
            decrypted_message,
            unpack_types=True,
            encoding='utf-8',
        )
        json_message = jsn.dict_keys_to_text(jsn.dict_values_to_text(json_message))
    except Exception as exc:
        lg.err('decrypt %r failed: %r' % (private_message_object, exc))
        return False
    if request.PacketID in received_messages_ids():
        lg.warn('skip incoming message %s because found in recent history' % request.PacketID)
        return False
    received_messages_ids().append(request.PacketID)
    if len(received_messages_ids()) > 100:
        received_messages_ids(True)
    handled = False
    try:
        for cb in _IncomingMessageCallbacks:
            handled = cb(request, private_message_object, json_message)
            if _Debug:
                lg.args(_DebugLevel, cb=cb, packet_id=request.PacketID, handled=handled)
            if handled:
                break
    except:
        lg.exc()
    if _Debug:
        lg.args(_DebugLevel, msg_len=len(decrypted_message), handled=handled)
    if handled:
        return True
    if config.conf().getBool('services/private-messages/acknowledge-unread-messages-enabled'):
        p2p_service.SendAckNoRequest(request.OwnerID, request.PacketID, response='unread')
    return True


def on_ping_success(ok, idurl):
    global _LastUserPingTime
    idurl = id_url.to_bin(idurl)
    _LastUserPingTime[idurl] = time.time()
    lg.info('shake up hands %r before sending a message : %s' % (idurl, ok))
    return ok


def on_message_delivered(idurl, json_data, recipient_global_id, packet_id, response, info, result_defer=None):
    global _LastUserPingTime
    idurl = id_url.to_bin(idurl)
    if _Debug:
        lg.args(_DebugLevel, packet_id=packet_id, recipient_global_id=recipient_global_id)
    _LastUserPingTime[idurl] = time.time()
    if result_defer and not result_defer.called:
        result_defer.callback(response)


def on_message_failed(idurl, json_data, recipient_global_id, packet_id, response, info, result_defer=None, error=None):
    global _LastUserPingTime
    idurl = id_url.to_bin(idurl)
    lg.err('message %s failed sending to %s in %s because : %r' % (packet_id, recipient_global_id, response, error))
    if idurl in _LastUserPingTime:
        _LastUserPingTime[idurl] = 0
    if result_defer and not result_defer.called:
        err = Exception(response) if response else (error if not strng.is_string(error) else Exception(error))
        if _Debug:
            lg.args(_DebugLevel, err=err, i=idurl, r=recipient_global_id, pid=packet_id, j=json_data)
        result_defer.errback(err)
    return None


#------------------------------------------------------------------------------


def do_send_message(json_data, recipient_global_id, packet_id, message_ack_timeout, result_defer=None, fire_callbacks=True):
    global _OutgoingMessageCallbacks
    remote_idurl = global_id.GlobalUserToIDURL(recipient_global_id, as_field=False)
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
    if _Debug:
        lg.out(_DebugLevel, 'message.do_send_message to %s with %d bytes message ack_timeout=%s pid:%s' % (recipient_global_id, len(message_body), message_ack_timeout, packet_id))
    try:
        private_message_object = PrivateMessage(recipient=recipient_global_id)
        private_message_object.encrypt(message_body)
    except:
        lg.exc()
        raise Exception('message encryption failed')
    payload = private_message_object.serialize()
    if _Debug:
        lg.out(_DebugLevel, '        payload is %d bytes, remote idurl is %s' % (len(payload), remote_idurl))
    callbacks = {}
    if message_ack_timeout:
        callbacks = {
            commands.Ack(): lambda response, info: on_message_delivered(
                remote_idurl,
                json_data,
                recipient_global_id,
                packet_id,
                response,
                info,
                result_defer,
            ),
            commands.Fail(): lambda response, info: on_message_failed(remote_idurl, json_data, recipient_global_id, packet_id, response, info, result_defer=result_defer, error='fail received'),
            None: lambda pkt_out: on_message_failed(
                remote_idurl,
                json_data,
                recipient_global_id,
                packet_id,
                None,
                None,
                result_defer=result_defer,
                error='timeout',
            ),
            'timeout': lambda pkt_out, errmsg: on_message_failed(
                remote_idurl,
                json_data,
                recipient_global_id,
                packet_id,
                None,
                None,
                result_defer=result_defer,
                error=errmsg,
            ),
            'failed': lambda pkt_out, errmsg: on_message_failed(
                remote_idurl,
                json_data,
                recipient_global_id,
                packet_id,
                None,
                None,
                result_defer=result_defer,
                error=errmsg,
            ),
        }
    result, outpacket = p2p_service.SendMessage(
        remote_idurl=remote_idurl,
        packet_id=packet_id,
        payload=payload,
        callbacks=callbacks,
        response_timeout=message_ack_timeout,
    )
    if fire_callbacks:
        try:
            for cp in _OutgoingMessageCallbacks:
                cp(json_data, private_message_object, remote_identity, outpacket, result)
        except:
            lg.exc()
            raise Exception('failed sending message')
    return result


def send_message(json_data, recipient_global_id, packet_id=None, message_ack_timeout=None, ping_timeout=None, ping_retries=0, skip_handshake=False, fire_callbacks=True, require_handshake=False):
    """
    Send command.Message() packet to remote peer. Returns Deferred object.
    """
    global _LastUserPingTime
    global _PingTrustIntervalSeconds
    if not packet_id:
        packet_id = packetid.UniqueID()
    if ping_timeout is None:
        ping_timeout = settings.P2PTimeOut()
    if message_ack_timeout is None:
        message_ack_timeout = settings.P2PTimeOut()
    if _Debug:
        lg.out(_DebugLevel, 'message.send_message to %s with PacketID=%s timeout=%d ack_timeout=%r retries=%d' % (recipient_global_id, packet_id, ping_timeout, message_ack_timeout, ping_retries))
    remote_idurl = global_id.GlobalUserToIDURL(recipient_global_id, as_field=False)
    if not remote_idurl:
        lg.warn('invalid recipient')
        return fail(Exception('invalid recipient'))
    ret = Deferred()
    ret.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='message.send_message')
    if remote_idurl not in _LastUserPingTime:
        is_ping_expired = True
    else:
        is_ping_expired = time.time() - _LastUserPingTime[remote_idurl] > _PingTrustIntervalSeconds
    remote_identity = identitycache.FromCache(remote_idurl)
    is_online = online_status.isOnline(remote_idurl)
    if _Debug:
        lg.out(_DebugLevel, '    is_ping_expired=%r  remote_identity=%r  is_online=%r  skip_handshake=%r' % (is_ping_expired, bool(remote_identity), is_online, skip_handshake))
    if require_handshake or remote_identity is None or ((is_ping_expired or not is_online) and not skip_handshake):
        d = online_status.handshake(
            idurl=remote_idurl,
            ack_timeout=ping_timeout,
            ping_retries=ping_retries,
            channel='send_message',
            keep_alive=True,
        )
        d.addCallback(lambda ok: on_ping_success(ok, remote_idurl))
        d.addCallback(lambda _: do_send_message(
            json_data=json_data,
            recipient_global_id=recipient_global_id,
            packet_id=packet_id,
            message_ack_timeout=message_ack_timeout,
            result_defer=ret,
            fire_callbacks=fire_callbacks,
        ))
        d.addErrback(lambda err: on_message_failed(remote_idurl, json_data, recipient_global_id, packet_id, None, None, result_defer=ret, error=err))
        return ret
    try:
        do_send_message(
            json_data=json_data,
            recipient_global_id=recipient_global_id,
            packet_id=packet_id,
            message_ack_timeout=message_ack_timeout,
            result_defer=ret,
            fire_callbacks=fire_callbacks,
        )
    except Exception as exc:
        lg.warn(str(exc))
        on_message_failed(remote_idurl, json_data, recipient_global_id, packet_id, None, None, error=exc)
        ret.errback(exc)
    return ret


#------------------------------------------------------------------------------


def consume_messages(consumer_callback_id, callback=None, direction=None, message_types=None, reset_callback=False):
    """
    Register a new callback method or Deferred object to wait and receive messages from the stream.

    If message was passed thru the stream but there were no callbacks registered to listen - the message is just ignored.
    When callback is registered any new message (if they match to specified criteria) will trigger callback to be executed.
    If callback is a Deferred object - the message will fire a callback() method of it so consumer can receive it.
    Right after receiving the message via callback() method consumer must call `consume_messages()` again to be able
    to receive the next message. This is very similar to a long polling technique.

    Stream also takes care of next messages that are not consumed yet by Deferred() callback in between of that calls to that method.
    If there are some messages that was not consumed by Deferred() - next call to that method will immediately fire
    callback() method of the Deferred() object with the list of messages.

    If input parameter `callback` is None Deferred() object will be automatically created and returned back as result.
    If input parameter `callback` is a callable method it will not be released like Deferred object - it will be fired
    for every message passed thru the stream.

    Parameter `direction` can be "incoming", "outgoing" or None (for both directions).

    Parameter `message_types` can be None (no filtering) or a list of desired types:
        "private_message", "group_message", "queue_message", "queue_message_replica"

    If `reset_callback` is True - previously registered Deferred object will be cleaned
    with `clear_consumer_callbacks()` method.
    """
    if consumer_callback_id in consumers_callbacks():
        if not reset_callback:
            raise Exception('consumer callback already exists')
        clear_consumer_callbacks(consumer_callback_id, reason='reset')
    cb = callback or Deferred()
    consumers_callbacks()[consumer_callback_id] = {
        'callback': cb,
        'direction': direction,
        'message_types': message_types,
    }
    if _Debug:
        lg.out(_DebugLevel, 'message.consume_messages added callback for consumer %r' % consumer_callback_id)
    do_read()
    return cb


def clear_consumer_callbacks(consumer_callback_id, reason=None):
    if consumer_callback_id not in consumers_callbacks().keys():
        if _Debug:
            lg.dbg(_DebugLevel, 'consumer callback %r not regisered' % consumer_callback_id)
        return True
    cb_info = consumers_callbacks().pop(consumer_callback_id)
    if isinstance(cb_info['callback'], Deferred):
        if _Debug:
            lg.args(_DebugLevel, consumer_callback_id=consumer_callback_id, cb=cb_info['callback'], called=cb_info['callback'].called)
        if not cb_info['callback'].called:
            cb_info['callback'].errback(Exception(str(reason)))
            cb_info['callback'] = None
    else:
        if _Debug:
            lg.args(_DebugLevel, consumer_callback_id=consumer_callback_id, cb=cb_info['callback'])
    return True


#------------------------------------------------------------------------------


def push_message(direction, msg_type, recipient_id, sender_id, packet_id, owner_idurl, json_message, run_consumers=True):
    for consumers_callback_id in consumers_callbacks().keys():
        if consumers_callback_id not in message_queue():
            message_queue()[consumers_callback_id] = []
        message_queue()[consumers_callback_id].append(
            {
                'type': msg_type,
                'dir': direction,
                'to': recipient_id,
                'from': sender_id,
                'data': json_message,
                'packet_id': packet_id,
                'owner_idurl': owner_idurl,
                'time': utime.utcnow_to_sec1970(),
            }
        )
        if _Debug:
            lg.args(_DebugLevel, dir=direction, msg_type=msg_type, to_id=recipient_id, from_id=sender_id, cb=consumers_callback_id, pending=len(message_queue()[consumers_callback_id]))
    if not run_consumers:
        return 0
    total_consumed = do_read()
    return total_consumed > 0


#------------------------------------------------------------------------------


def push_incoming_message(request, private_message_object, json_message):
    msg_type = None
    if request.PacketID.startswith('private_'):
        msg_type = 'private_message'
    if request.PacketID.startswith('queue_'):
        msg_type = 'queue_message'
    if msg_type is None:
        raise Exception('undefined message type detected in %r' % request)
    return push_message(
        direction='incoming',
        msg_type=msg_type,
        recipient_id=private_message_object.recipient_id(),
        sender_id=private_message_object.sender_id(),
        packet_id=request.PacketID,
        owner_idurl=request.OwnerID,
        json_message=json_message,
    )


def push_outgoing_message(json_message, private_message_object, remote_identity, request, result):
    msg_type = 'private_message'
    if request.PacketID.startswith('queue_'):
        msg_type = 'queue_message'
    return push_message(
        direction='outgoing',
        msg_type=msg_type,
        recipient_id=private_message_object.recipient_id(),
        sender_id=private_message_object.sender_id(),
        packet_id=request.PacketID,
        owner_idurl=request.OwnerID,
        json_message=json_message,
    )


def push_group_message(json_message, direction, group_key_id, producer_id, sequence_id):
    if _Debug:
        lg.args(_DebugLevel, group_key_id=group_key_id, producer_id=producer_id, sequence_id=sequence_id)
    return push_message(
        direction=direction,
        msg_type='group_message',
        recipient_id=group_key_id,
        sender_id=producer_id,
        packet_id=sequence_id,
        owner_idurl=None,
        json_message=json_message,
    )


#------------------------------------------------------------------------------


def do_read():
    known_consumers = list(message_queue().keys())
    total_handled = 0
    for consumer_id in known_consumers:
        if consumer_id not in message_queue() or len(message_queue()[consumer_id]) == 0:
            continue
        cb_info = consumers_callbacks().get(consumer_id)
        pending_messages = message_queue()[consumer_id]
        # no consumer or queue is growing too much -> stop consumer and queue
        if (not cb_info or not cb_info['callback']) or len(pending_messages) > MAX_PENDING_MESSAGES_PER_CONSUMER:
            consumers_callbacks().pop(consumer_id, None)
            message_queue().pop(consumer_id, None)
            lg.warn('stopped consumer "%s", pending_messages=%d' % (consumer_id, len(pending_messages)))
            continue
        # filter messages which consumer is not interested in
        if cb_info['direction']:
            consumer_messages = filter(lambda msg: msg['dir'] == cb_info['direction'], pending_messages)
        else:
            consumer_messages = filter(None, pending_messages)
        if cb_info['message_types']:
            consumer_messages = filter(lambda msg: msg['type'] in cb_info['message_types'], consumer_messages)
        consumer_messages = list(consumer_messages)
        if not consumer_messages:
            message_queue()[consumer_id] = []
            continue
        # callback is a one-time Deferred object, must call it now and release the callback
        if isinstance(cb_info['callback'], Deferred):
            if cb_info['callback'].called:
                if _Debug:
                    lg.out(_DebugLevel, 'message.do_read %d messages waiting consuming by "%s", callback state is "called"' % (len(message_queue()[consumer_id]), consumer_id))
                consumers_callbacks().pop(consumer_id, None)
                continue
            try:
                cb_result = cb_info['callback'].callback(consumer_messages)
            except:
                lg.exc()
                consumers_callbacks().pop(consumer_id, None)
                continue
            if _Debug:
                lg.args(_DebugLevel, consumer_id=consumer_id, cb_result=cb_result)
            consumers_callbacks().pop(consumer_id, None)
            message_queue()[consumer_id] = []
            total_handled += len(consumer_messages)
            continue
        # callback is a "callable" method which we must not release
        message_queue()[consumer_id] = []
        try:
            handled = cb_info['callback'](consumer_messages)
        except:
            lg.exc()
            consumers_callbacks().pop(consumer_id, None)
            # put back failed messages to the queue so consumer can re-try
            message_queue()[consumer_id] = pending_messages
            continue
        if _Debug:
            lg.args(_DebugLevel, handled=handled, cb_info=cb_info)
        if handled is None:
            lg.err('failed consuming messages by consumer %r' % consumer_id)
            consumers_callbacks().pop(consumer_id, None)
            # put back failed messages to the queue so consumer can re-try
            message_queue()[consumer_id] = pending_messages
            continue
        if handled:
            total_handled += len(consumer_messages)
    if _Debug:
        lg.args(_DebugLevel, total_handled=total_handled)
    return total_handled
