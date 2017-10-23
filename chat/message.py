#!/usr/bin/python
# message.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
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
..

module:: message
"""

import os
import sys
import datetime
import time
import StringIO

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in message.py')

from twisted.internet.defer import fail

#------------------------------------------------------------------------------

from logs import lg

from p2p import commands

from lib import packetid

from lib import misc

from crypt import signed
from crypt import key
from crypt import my_keys

from contacts import identitycache

from userid import my_id
from userid import global_id

from transport import gateway

#------------------------------------------------------------------------------

_IncomingMessageCallbacks = []
_OutgoingMessageCallback = None
_InboxHistory = []

#------------------------------------------------------------------------------


def init():
    global _InboxHistory
    lg.out(4, "message.init")
    _InboxHistory = []


def shutdown():
    global _InboxHistory
    lg.out(4, "message.shutdown")
    _InboxHistory = []

#------------------------------------------------------------------------------


def ConnectCorrespondent(idurl):
    pass


def UniqueID():
    return str(int(time.time() * 100.0))


def inbox_history():
    global _InboxHistory
    return _InboxHistory

#------------------------------------------------------------------------------


class PrivateMessage:
    """
    A class to represent a message.

    We always encrypt messages with a session key so we need to package
    with encrypted body.
    """

    def __init__(self, recipient_global_id):
        self.recipient = recipient_global_id
        self.encrypted_session = None
        self.encrypted_body = None

    def _which_key(self):
        if my_keys.is_key_registered(self.recipient):
            return self.recipient
        glob_id = global_id.ParseGlobalID(self.recipient)
        own_key = global_id.MakeGlobalID(idurl=my_id.getLocalID(), key_id=glob_id['key_id'])
        if my_keys.is_key_registered(own_key):
            return own_key
        raise Exception('can not find key for given recipient')

    def encrypt_body(self, message_body):
        target_key_id = self._which_key()
        lg.out(8, "message.PrivateMessage will ENCRYPT message of %d bytes for %s" % (
            len(message_body), target_key_id))
        sessionkey = key.NewSessionKey()
        self.encrypted_session = my_keys.encrypt(target_key_id, sessionkey)
        self.encrypted_body = key.EncryptWithSessionKey(sessionkey, message_body)
        return self.encrypted_session, self.encrypted_body

    def decrypt_body(self):
        target_key_id = self._which_key()
        lg.out(8, "message.PrivateMessage will DECRYPT message from %d encrypted bytes with %s key" % (
            len(self.encrypted_body), target_key_id))
        sessionkey = my_keys.decrypt(target_key_id, self.encrypted_session)
        return key.DecryptWithSessionKey(sessionkey, self.encrypted_body)

#------------------------------------------------------------------------------


def Message(request):
    """
    Message came in for us so we: 1) check that it is a correspondent 2)
    decrypt message body 3) save on local HDD 4) call the GUI 5) send an "Ack"
    back to sender.
    """
    global _IncomingMessageCallbacks
    lg.out(6, "message.Message from " + str(request.OwnerID))
    try:
        Amessage = misc.StringToObject(request.Payload)
        if Amessage is None:
            raise Exception("wrong Payload, can not extract message from request")
        clear_message = Amessage.decrypt_body()
    except:
        lg.exc()
        return False
    for old_id, old_message in inbox_history():
        if old_id == request.PacketID:
            lg.out(6, "message.Message SKIP, message %s found in history" % old_message)
            return False
    inbox_history().append((request.PacketID, Amessage))
    from p2p import p2p_service
    p2p_service.SendAck(request)
    for cb in _IncomingMessageCallbacks:
        cb(request, clear_message)
    return True

#------------------------------------------------------------------------------


def SendMessage(message_body, recipient_global_id, packet_id=None):
    """
    Send command.Message() packet to remote peer.
    Returns Deferred (if remote_idurl was not cached yet) or outbox packet object.
    """
    global _OutgoingMessageCallback
    if not packet_id:
        packet_id = packetid.UniqueID()
    remote_idurl = global_id.GlobalUserToIDURL(recipient_global_id)
    remote_identity = identitycache.FromCache(remote_idurl)
    if remote_identity is None:
        d = identitycache.immediatelyCaching(remote_idurl, timeout=10)
        d.addCallback(lambda src: SendMessage(
            message_body, recipient_global_id, packet_id))
        d.addErrback(lambda err: lg.warn('failed to retrieve %s : %s' (remote_idurl, err)))
        return d
    try:
        Amessage = PrivateMessage(recipient_global_id=recipient_global_id)
        Amessage.encrypt_body(message_body)
    except Exception as exc:
        return fail(exc)
    Payload = misc.ObjectToString(Amessage)
    lg.out(6, "message.SendMessage to %s with %d bytes" % (remote_idurl, len(Payload)))
    outpacket = signed.Packet(
        commands.Message(),
        my_id.getLocalID(),
        my_id.getLocalID(),
        packet_id,
        Payload,
        remote_idurl,
    )
    result = gateway.outbox(outpacket, wide=True)
    if _OutgoingMessageCallback:
        _OutgoingMessageCallback(result, Amessage, remote_identity, packet_id)
    return result

#------------------------------------------------------------------------------


def SortMessagesList(mlist, sort_by_column):
    order = {}
    i = 0
    for msg in mlist:
        order[msg[sort_by_column]] = i
        i += 1
    keys = sorted(order.keys())
    msorted = []
    for key in keys:
        msorted.append(order[key])
    return msorted

#------------------------------------------------------------------------------


def AddIncomingMessageCallback(cb):
    global _IncomingMessageCallbacks
    if cb not in _IncomingMessageCallbacks:
        _IncomingMessageCallbacks.append(cb)


def RemoveIncomingMessageCallback(cb):
    global _IncomingMessageCallbacks
    if cb in _IncomingMessageCallbacks:
        _IncomingMessageCallbacks.remove(cb)

#------------------------------------------------------------------------------


if __name__ == "__main__":
    init()
    reactor.run()
