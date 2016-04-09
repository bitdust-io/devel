#!/usr/bin/python
#message.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: message

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

#------------------------------------------------------------------------------ 

from logs import lg

from main import settings

from p2p import commands

from lib import packetid
from lib import nameurl

from lib import misc

from crypt import signed
from crypt import key

from contacts import identitycache
from contacts import contactsdb
from userid import my_id

from transport import gateway

#------------------------------------------------------------------------------ 

_IncomingMessageCallback = None
_OutgoingMessageCallback = None

#------------------------------------------------------------------------------ 


def init():
    lg.out(4,"message.init")
##    guimessage.UpdateCorrespondents()

def shutdown():
    lg.out(4,"message.shutdown")

#------------------------------------------------------------------------------ 

def ConnectCorrespondent(idurl):
    pass


def UniqueID():
    return str(int(time.time()*100.0))

#------------------------------------------------------------------------------ 

class MessageClass:
    """
    A class to represent a message.
    We always encrypt messages with a session key so we need to package with encrypted body.
    """
    def __init__(self, destinationidentity, messagebody):
        lg.out(8, "message.MessageClass making message of %d bytes" % len(messagebody))
        sessionkey = key.NewSessionKey()
        keystring = destinationidentity.publickey
        self.encryptedKey = key.EncryptStringPK(keystring, sessionkey)
        self.encryptedMessage = key.EncryptWithSessionKey(sessionkey, messagebody)
        
    def ClearBody(self):
        sessionkey = key.DecryptLocalPK(self.encryptedKey)
        # we only decrypt with LocalIdentity
        return key.DecryptWithSessionKey(sessionkey, self.encryptedMessage)

#------------------------------------------------------------------------------ 

def Message(request):
    """
    Message came in for us so we:    
        1) check that it is a correspondent
        2) decrypt message body
        3) save on local HDD
        4) call the GUI
        5) send an "Ack" back to sender
    """
    global _IncomingMessageCallback
    lg.out(6, "message.Message from " + str(request.OwnerID))
#    senderidentity = contactsdb.get_correspondent_identity(request.OwnerID)
#    if not senderidentity:
#        lg.warn("had sender not in correspondents list " + request.OwnerID)
#        # return
#        contactsdb.add_correspondent(request.OwnerID, nameurl.GetName(request.OwnerID))
#        contactsdb.save_correspondents()
    Amessage = misc.StringToObject(request.Payload)
    if Amessage is None:
        lg.warn("wrong Payload, can not extract message from request")
        return
    clearmessage = Amessage.ClearBody()
    # SaveMessage(clearmessage)
    from p2p import p2p_service
    p2p_service.SendAck(request)
    if _IncomingMessageCallback is not None:
        _IncomingMessageCallback(request, clearmessage)

#------------------------------------------------------------------------------ 

def SendMessage(remote_idurl, messagebody, packet_id=None):
    """
    Send command.Message() packet to remote peer.
    """
    global _OutgoingMessageCallback
    if not packet_id:
        packet_id = packetid.UniqueID()
    remote_identity = identitycache.FromCache(remote_idurl)
    if remote_identity is None:
        d = identitycache.immediatelyCaching(remote_idurl, 20)
        d.addCallback(lambda src: SendMessage(
            remote_idurl, messagebody, packet_id))
        d.addErrback(lambda err: lg.warn('failed to retrieve ' + remote_idurl))
        return d
    Amessage = MessageClass(remote_identity, messagebody)
    Payload = misc.ObjectToString(Amessage)
    lg.out(6, "message.SendMessage to %s with %d bytes" % (remote_idurl, len(Payload)))
    outpacket = signed.Packet(
        commands.Message(),
        my_id.getLocalID(),
        my_id.getLocalID(),
        packet_id,
        Payload,
        remote_idurl)
    result = gateway.outbox(outpacket)
    if _OutgoingMessageCallback:
        _OutgoingMessageCallback(result, messagebody, remote_identity, packet_id)
    return result

#------------------------------------------------------------------------------ 

def SortMessagesList(mlist, sort_by_column):
    order = {}
    i = 0
    for msg in mlist:
        order[msg[sort_by_column]] = i
        i += 1
    keys = order.keys()
    keys.sort()
    sorted = []
    for key in keys:
        sorted.append(order[key])
    return sorted

#------------------------------------------------------------------------------ 

def SetIncomingMessageCallback(cb):
    global _IncomingMessageCallback
    _IncomingMessageCallback = cb

#------------------------------------------------------------------------------ 

if __name__ == "__main__":
    init()
    reactor.run()

