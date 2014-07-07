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

This is sort of email that has solved the spam problem. 
Could spread to general messaging use.

Users have list of identities that can send them messages 
without paying ("correspondents" list or "friends and family").

User specifies postage price for incoming mail delivery from someone not on their list in identity.
If incoming mail is not on ID list and does not have enough payment, it is dropped.
Spam gone.

If incoming mail needs to be paid for we look and see if that ID has a high enough balance.
In identity.py we need to have spam-price published.
Ok to put IDURL on web pages because can't get junk mail without making money.

Message body is always encrypted with key of destination.
We learn of payments when we get deposit receipt from either sender or accounts.datahaven.net.
We credit that contact.

When message comes in we check if they have enough credit or if they are on the correspondent list.
If so we:
- send it to gui
- send back an ack letting sender know user can look at it

Can also have a black list where we take there money and still toss the message.

Bit worried about the potential for a customer or supplier to threaten a contact.
Probably need to have GUI explain that contacts from customers/suppliers are not normal and
anything strange should be reason to fire that customer/supplier right away.

Contacts needs to have 3 types now.  
And possible for some contact to be 2 or 3 types.  
The types are:  
- suppliers
- customers
- correspondents
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


from twisted.internet.defer import Deferred


import lib.dhnio as dhnio
import lib.misc as misc
import lib.dhnpacket as dhnpacket
import lib.contacts as contacts
import lib.commands as commands
##import lib.eccmap as eccmap
import lib.settings as settings
# import lib.transport_control as transport_control
import lib.packetid as packetid
import lib.dhncrypto as dhncrypto
import lib.nameurl as nameurl

import userid.identity as identity
import userid.identitycache as identitycache

import transport.gate as gate

import p2p_service

#------------------------------------------------------------------------------ 

OnIncommingMessageFunc = None

#------------------------------------------------------------------------------ 


def init():
    dhnio.Dprint(4,"message.init")
##    guimessage.UpdateCorrespondents()

def ConnectCorrespondent(idurl):
    pass

def UniqueID():
    return str(int(time.time()*100.0))

class MessageClass:
    """
    A class to represent a message.
    We always encrypt messages with a session key so we need to package with encrypted body.
    """
    def __init__(self, destinationidentity, messagebody):
        dhnio.Dprint(8, "message.MessageClass making message ")
        sessionkey = dhncrypto.NewSessionKey()
        keystring = destinationidentity.publickey
        self.encryptedKey = dhncrypto.EncryptStringPK(keystring, sessionkey)
        self.encryptedMessage = dhncrypto.EncryptWithSessionKey(sessionkey, messagebody)
        
    def ClearBody(self):
        sessionkey = dhncrypto.DecryptLocalPK(self.encryptedKey)
        # we only decrypt with LocalIdentity
        return dhncrypto.DecryptWithSessionKey(sessionkey, self.encryptedMessage)

def Message(request):
    """
    Message came in for us so we:    
        1) check that it is a correspondent
        2) decrypt message body
        3) save on local HDD
        4) call the GUI
        5) send an "Ack" back to sender
    """
    global OnIncommingMessageFunc
    dhnio.Dprint(6, "message.Message from " + str(request.OwnerID))
    senderidentity = contacts.getCorrespondent(request.OwnerID)
    if not senderidentity:
        dhnio.Dprint(4,"message.Message WARNING had sender not in correspondents list " + request.OwnerID)
        return
    Amessage = misc.StringToObject(request.Payload)
    if Amessage is None:
        dhnio.Dprint(4,"message.Message WARNING wrong Payload, can not extract message from request")
        return
    clearmessage = Amessage.ClearBody()
    SaveMessage(clearmessage)
    if OnIncommingMessageFunc is not None:
        OnIncommingMessageFunc(request, SplitMessage(clearmessage))
    # transport_control.SendAck(request)
    p2p_service.SendAck(request)

def MakeMessage(to, subj, body, dt=datetime.datetime.now().strftime("%Y/%m/%d %I:%M:%S %p")):
    dhnio.Dprint(6, "message.MakeMessage to " + to)
    msg = ( misc.getLocalID(),
            to,
            subj,
            dt,
            body)
    return '\n'.join(msg)

def SplitMessage(clearmessage):
    fin = StringIO.StringIO(clearmessage)
    sender = fin.readline().strip()
    to = fin.readline().strip()
    subject = fin.readline().strip()
    datetime = fin.readline().strip()
    body = fin.read()
    return (sender, to, subject, datetime, body)

def SaveMessage(clearmessage):
    msguid = UniqueID()
    dhnio.Dprint(6, "message.SaveMessage %s" % msguid)
    msgfilename = os.path.join(settings.getMessagesDir(),  msguid+'.dhnmessage')
    msgfile = file(msgfilename, 'w')
    msgfile.write(str(clearmessage))
    msgfile.close()
    return msguid

def LoadMessage(msgpath):
    fin = open(msgpath, 'r')
    clearmessage = fin.read()
    fin.close()
    return SplitMessage(clearmessage) 

def ReadMessage(messageuid):
    msgpath = os.path.join(settings.getMessagesDir(), messageuid + '.dhnmessage')
    # msgpath = settings.getMessagesDir() + os.sep + messageuid + '.dhnmessage'
    if not os.path.exists(msgpath):
        return None
    return LoadMessage(msgpath)

def DeleteMessage(messageuid):
    msgpath = os.path.join(settings.getMessagesDir(), messageuid + '.dhnmessage')
    if not os.path.exists(msgpath):
        return False
    try:
        os.remove(msgpath)
    except:
        dhnio.DprintException()
        return False
    dhnio.Dprint(6, "message.DeleteMessage %s" % messageuid)
    return True

def SendMessage(RemoteID, messagebody, PacketID=""):
    """
    PREPRO:
    We should probably check that we have a recent copy of the remote identity in ``identitycache``.
    Or else transport_control needs to be able to fetch identities again 
    when it needs to do more than X retries.
    GUI calls this to send the message.
    """
    dhnio.Dprint(6, "message.SendMessage to: " + str(RemoteID) )
    #TODO ERROR HERE (return Defer)
    if not identitycache.scheduleForCaching(RemoteID):
        dhnio.Dprint(1, "message.SendMessage ERROR. Can't find identity: " + str(RemoteID))
        return
    RemoteIdentity=identitycache.FromCache(RemoteID)
    if RemoteIdentity == '':
        dhnio.Dprint(1, "message.SendMessage ERROR. Can't retreive identity: " + str(RemoteID))
        return
    Amessage = MessageClass(RemoteIdentity, messagebody)
    MyID = misc.getLocalID()
    if PacketID == "":
        PacketID = packetid.UniqueID()
    Payload = misc.ObjectToString(Amessage)
    dhnio.Dprint(6, "message.SendMessage  about to send to " + RemoteID)
    result = dhnpacket.dhnpacket(commands.Message(),  MyID, MyID, PacketID, Payload, RemoteID)
    # transport_control.outboxAck(result)
    gate.outbox(result, False)

def ListAllMessages():
    mlist = []
    i = 0
    for filename in os.listdir(settings.getMessagesDir()):
        if not filename.endswith('.dhnmessage'):
            continue
        msgpath = os.path.join(settings.getMessagesDir(), filename)
        # msgpath = settings.getMessagesDir() + os.sep + filename
        if not os.path.exists(msgpath):
            continue
        msg = LoadMessage(msgpath)
        messageuid = filename.split('.')[0]
        msgtupple = (messageuid, nameurl.GetName(msg[0]), nameurl.GetName(msg[1]), msg[3], msg[2])
        mlist.append(msgtupple)
        i += 1
    return mlist

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


if __name__ == "__main__":
    init()
    reactor.run()

