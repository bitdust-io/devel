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
We learn of payments when we get deposit receipt from sender.
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

from logs import lg

from lib import bpio
from lib import misc
from lib import contacts
from lib import commands
from lib import settings
from lib import packetid
from lib import nameurl

from crypt import signed
from crypt import key

from userid import identitycache

from transport import gateway

import p2p_service

#------------------------------------------------------------------------------ 

OnIncomingMessageFunc = None

#------------------------------------------------------------------------------ 


def init():
    lg.out(4,"message.init")
##    guimessage.UpdateCorrespondents()

#------------------------------------------------------------------------------ 

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
        lg.out(8, "message.MessageClass making message ")
        sessionkey = key.NewSessionKey()
        keystring = destinationidentity.publickey
        self.encryptedKey = key.EncryptStringPK(keystring, sessionkey)
        self.encryptedMessage = key.EncryptWithSessionKey(sessionkey, messagebody)
        
    def ClearBody(self):
        sessionkey = key.DecryptLocalPK(self.encryptedKey)
        # we only decrypt with LocalIdentity
        return key.DecryptWithSessionKey(sessionkey, self.encryptedMessage)

def Message(request):
    """
    Message came in for us so we:    
        1) check that it is a correspondent
        2) decrypt message body
        3) save on local HDD
        4) call the GUI
        5) send an "Ack" back to sender
    """
    global OnIncomingMessageFunc
    lg.out(6, "message.Message from " + str(request.OwnerID))
    senderidentity = contacts.getCorrespondent(request.OwnerID)
    if not senderidentity:
        lg.warn("had sender not in correspondents list " + request.OwnerID)
        # return
        contacts.addCorrespondent(request.OwnerID, nameurl.GetName(request.OwnerID))
    Amessage = misc.StringToObject(request.Payload)
    if Amessage is None:
        lg.warn("wrong Payload, can not extract message from request")
        return
    clearmessage = Amessage.ClearBody()
    SaveMessage(clearmessage)
    if OnIncomingMessageFunc is not None:
        OnIncomingMessageFunc(request, SplitMessage(clearmessage))
    p2p_service.SendAck(request)

def MakeMessage(to, subj, body, 
                dt=datetime.datetime.now().strftime("%Y/%m/%d %I:%M:%S %p")):
    lg.out(6, "message.MakeMessage to " + to)
    msg = ( misc.getLocalID(), to, subj, dt, body )
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
    lg.out(6, "message.SaveMessage %s" % msguid)
    msgfilename = os.path.join(settings.getMessagesDir(),  msguid+'.message')
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
    msgpath = os.path.join(settings.getMessagesDir(), messageuid + '.message')
    if not os.path.exists(msgpath):
        return None
    return LoadMessage(msgpath)

def DeleteMessage(messageuid):
    msgpath = os.path.join(settings.getMessagesDir(), messageuid + '.message')
    if not os.path.exists(msgpath):
        return False
    try:
        os.remove(msgpath)
    except:
        lg.exc()
        return False
    lg.out(6, "message.DeleteMessage %s" % messageuid)
    return True

def DoSendMessage(RemoteIdentity, messagebody, PacketID):
    Amessage = MessageClass(RemoteIdentity, messagebody)
    MyID = misc.getLocalID()
    if PacketID == "":
        PacketID = packetid.UniqueID()
    Payload = misc.ObjectToString(Amessage)
    lg.out(6, "message.SendMessage  about to send to " + RemoteIdentity.getIDURL())
    result = signed.Packet(commands.Message(),  MyID, MyID, PacketID, Payload, RemoteIdentity.getIDURL())
    gateway.outbox(result)

def SendMessage(RemoteID, messagebody, PacketID=""):
    """
    PREPRO:
    We should probably check that we have a recent copy of the remote identity in the ``identitycache``.
    Or else transport gate needs to be able to fetch identities again 
    when it needs to do more than X retries.
    GUI calls this to send the message.
    """
    lg.out(6, "message.SendMessage to: " + str(RemoteID) )
    #TODO ERROR HERE (return Defer)
    # if not identitycache.scheduleForCaching(RemoteID):
    #     lg.out(2, "message.SendMessage ERROR. Can't find identity: " + str(RemoteID))
    #     return
    RemoteIdentity = identitycache.FromCache(RemoteID)
    if not RemoteIdentity:
        d = identitycache.immediatelyCaching(RemoteID)
        d.addCallback(lambda src: DoSendMessage(
            identitycache.FromCache(RemoteID), messagebody, PacketID))
        d.addErrback(lambda err: lg.warn('Can\'t retreive identity ' + RemoteID))
        return
    DoSendMessage(RemoteIdentity, messagebody, PacketID)

def ListAllMessages():
    """
    Return a list of tuples:
        (messageID, sender, to, datetime, subject) 
    """
    mlist = []
    i = 0
    for filename in os.listdir(settings.getMessagesDir()):
        if not filename.endswith('.message'):
            continue
        msgpath = os.path.join(settings.getMessagesDir(), filename)
        if not os.path.exists(msgpath):
            continue
        msg = LoadMessage(msgpath)
        msgtupple = (filename.split('.')[0], msg[0], msg[1], msg[3], msg[2])
        mlist.append(msgtupple)
        i += 1
    return mlist

def DictAllConversations():
    """
    Return a dict of tuples by string:
        "<recipient> <subject>" -> (messageID, datetime, sender, to)
    """
    cdict = {}
    for filename in os.listdir(settings.getMessagesDir()):
        if not filename.endswith('.message'):
            continue
        msgpath = os.path.join(settings.getMessagesDir(), filename)
        if not os.path.exists(msgpath):
            continue
        msg = LoadMessage(msgpath) # (sender, to, subject, datetime, body)
        recipient = msg[0] if msg[0] != misc.getLocalID() else msg[1]
        key = recipient + ' ' + msg[2]  
        if not cdict.has_key(key):
            cdict[key] = []
        # dt = time.mktime(time.strptime(msg[3], "%Y/%m/%d %I:%M:%S %p"))
        msgtupple = (filename.split('.')[0], msg[3], msg[0], msg[1])
        cdict[key].append(msgtupple)
    return cdict

def ReadConversation(recipient, subject, index=None, limit=None):
    """
    Return a list of tuples:
        (messageID, datetime, sender, to, body)
    """
    result = []
    i = 0
    for filename in os.listdir(settings.getMessagesDir()):
        if not filename.endswith('.message'):
            continue
        msgpath = os.path.join(settings.getMessagesDir(), filename)
        if not os.path.exists(msgpath):
            continue
        msg = LoadMessage(msgpath) # (sender, to, subject, datetime, body)
        if recipient != msg[0] and recipient != msg[1]:
            continue
        if subject != msg[2]:
            continue
        i += 1
        if index is not None and i <= index:
            continue
        if limit is not None and len(result) > limit:
            continue
        msgtupple = (filename.split('.')[0], msg[3], msg[0], msg[1], msg[4])
        result.append(msgtupple)
    return result

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

