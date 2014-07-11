#!/usr/bin/python
#contact_status.py
#
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: contact_status

.. raw:: html

    <a href="http://bitpie.net/automats/contact_status/contact_status.png" target="_blank">
    <img src="http://bitpie.net/automats/contact_status/contact_status.png" style="max-width:100%;">
    </a>
    
A state machine and several extra methods to keep track of current users's online state.
To do p2p communications need to know who is available and who is not.

This simple state machine is used to detect connection status with remote user.
The situation when remote user replies to a packet sent to him 
means that he is currently available over the network.   

A one instance of ``contact_status()`` machine is created for every remote contact and monitor his status.


EVENTS:
    * :red:`file-sent`
    * :red:`inbox-packet`
    * :red:`outbox-packet`
    * :red:`sent-done`
    * :red:`sent-failed`
    * :red:`timer-20sec`

"""

import os
import sys
import time

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in contact_status.py')
    

import lib.dhnio as dhnio
import lib.nameurl as nameurl
import lib.contacts as contacts
import lib.automat as automat
import lib.settings as settings
import lib.commands as commands

import userid.identitycache as identitycache
import transport.callback as callback

import ratings


_ContactsStatusDict = {}
_ShutdownFlag = False

#------------------------------------------------------------------------------ 


def init():
    """
    Needs to be called before other methods here.
    """
    dhnio.Dprint(4, 'contact_status.init')
    callback.add_inbox_callback(Inbox)
    callback.add_outbox_callback(Outbox)
    callback.add_queue_item_status_callback(OutboxStatus)
    
#    transport_control.AddInboxCallback(Inbox)
#    transport_control.AddOutboxCallback(Outbox)
#    transport_control.AddOutboxPacketStatusFunc(OutboxStatus)
#    transport_control.AddWorkItemSentCallbackFunc(FileSent)
#    if transport_control._TransportCSpaceEnable:
#        transport_cspace.SetContactStatusNotifyFunc(CSpaceContactStatus)
#    if transport_control._TransportUDPEnable:
#        transport_udp_session.SetStateChangedCallbackFunc(TransportUDPSessionStateChanged)


def shutdown():
    """
    Called from top level code when the software is finishing.
    """
    dhnio.Dprint(4, 'contact_status.shutdown')
    global _ShutdownFlag
    global _ContactsStatusDict
    for A in _ContactsStatusDict.values():
        automat.clear_object(A.index)
    _ContactsStatusDict.clear()
    _ShutdownFlag = True
    

def isOnline(idurl):
    """
    Return True if given contact's state is ONLINE.
    """
    global _ShutdownFlag
    if _ShutdownFlag:
        return False
    if idurl in [None, 'None', '']:
        return False
    global _ContactsStatusDict
    if idurl not in _ContactsStatusDict.keys():
        dhnio.Dprint(6, 'contact_status.isOnline contact %s is not found, made a new instance' % idurl)
    return A(idurl).state == 'CONNECTED'


def isOffline(idurl):
    """
    Return True if given contact's state is OFFLINE.
    """
    global _ShutdownFlag
    if _ShutdownFlag:
        return True
    if idurl in [None, 'None', '']:
        return True
    global _ContactsStatusDict
    if idurl not in _ContactsStatusDict.keys():
        dhnio.Dprint(6, 'contact_status.isOffline contact %s is not found, made a new instance' % idurl)
    return A(idurl).state == 'OFFLINE'


def hasOfflineSuppliers():
    """
    Loops all suppliers and check their state, return True if at least one is OFFLINE.
    """
    for idurl in contacts.getSupplierIDs():
        if isOffline(idurl):
            return True
    return False


def countOfflineAmong(idurls_list):
    """
    Loops all IDs in ``idurls_list`` and count how many is OFFLINE.
    """
    num = 0
    for idurl in idurls_list:
        if isOffline(idurl):
            num += 1
    return num

def countOnlineAmong(idurls_list):
    """
    Loops all IDs in ``idurls_list`` and count how many is ONLINE.
    """
    num = 0
    for idurl in idurls_list:
        if idurl:
            if isOnline(idurl):
                num += 1
    return num

#------------------------------------------------------------------------------ 

def A(idurl, event=None, arg=None):
    """
    Access method to interact with a state machine created for given contact.
    """
    global _ShutdownFlag
    global _ContactsStatusDict
    if not _ContactsStatusDict.has_key(idurl):
        if _ShutdownFlag:
            return None
        _ContactsStatusDict[idurl] = ContactStatus(idurl, 'status_%s' % nameurl.GetName(idurl), 'OFFLINE', 10)
    if event is not None:
        _ContactsStatusDict[idurl].automat(event, arg)
    return _ContactsStatusDict[idurl]
      

class ContactStatus(automat.Automat):
    """
    A class to keep track of user's online status.
    """
    
    timers = {
        'timer-20sec': (20.0, ['PING','ACK?']),
        }
    
    def __init__(self, idurl, name, state, debug_level):
        self.idurl = idurl
        self.time_connected = None
        automat.Automat.__init__(self, name, state, debug_level)
        dhnio.Dprint(10, 'contact_status.ContactStatus %s %s %s' % (name, state, idurl))
        
    def state_changed(self, oldstate, newstate):
        dhnio.Dprint(6, '%s : [%s]->[%s]' % (nameurl.GetName(self.idurl), oldstate.lower(), newstate.lower()))
        
    def A(self, event, arg):
        #---CONNECTED---
        if self.state == 'CONNECTED':
            if event == 'outbox-packet' and self.isPingPacket(arg) :
                self.state = 'PING'
                self.AckCounter=0
                self.doRepaint(arg)
            elif event == 'sent-failed' and self.isDataPacket(arg) :
                self.state = 'OFFLINE'
                self.doRepaint(arg)
        #---OFFLINE---
        elif self.state == 'OFFLINE':
            if event == 'outbox-packet' and self.isPingPacket(arg) :
                self.state = 'PING'
                self.AckCounter=0
                self.doRepaint(arg)
            elif event == 'inbox-packet' :
                self.state = 'CONNECTED'
                self.doRememberTime(arg)
                self.doRepaint(arg)
        #---PING---
        elif self.state == 'PING':
            if event == 'sent-done' :
                self.state = 'ACK?'
                self.AckCounter=0
            elif event == 'inbox-packet' :
                self.state = 'CONNECTED'
                self.doRememberTime(arg)
                self.doRepaint(arg)
            elif event == 'file-sent' :
                self.AckCounter+=1
            elif event == 'sent-failed' and self.AckCounter>1 :
                self.AckCounter-=1
            elif event == 'timer-20sec' or ( event == 'sent-failed' and self.AckCounter==1 ) :
                self.state = 'OFFLINE'
                self.doRepaint(arg)
        #---ACK?---
        elif self.state == 'ACK?':
            if event == 'inbox-packet' :
                self.state = 'CONNECTED'
                self.doRememberTime(arg)
                self.doRepaint(arg)
            elif event == 'timer-20sec' :
                self.state = 'OFFLINE'
            elif event == 'outbox-packet' and self.isPingPacket(arg) :
                self.state = 'PING'
                self.AckCounter=0
                self.doRepaint(arg)

    def isPingPacket(self, arg):
        pkt_out = arg
        return pkt_out.outpacket.Command == commands.Identity() and pkt_out.wide is True

    def isDataPacket(self, arg):
        outpacket, status, error = arg
        return outpacket.Command not in [commands.Identity(), commands.Ack()]

    def doRememberTime(self, arg):
        self.time_connected = time.time()
        
    def doRepaint(self, arg):
        """
        """
        try:
            import p2p.webcontrol
            p2p.webcontrol.OnAliveStateChanged(self.idurl)
        except:
            dhnio.DprintException()
        # if transport_control.GetContactAliveStateNotifierFunc() is not None:
        #     transport_control.GetContactAliveStateNotifierFunc()(self.idurl)
 
#------------------------------------------------------------------------------ 

def OutboxStatus(pkt_out, status, error=''):
    """
    This method is called from ``lib.transport_control`` when got a status report after 
    sending a packet to remote peer. If packet sent was failed - user seems to be OFFLINE.   
    """
    if status == 'finished':
        A(pkt_out.remote_idurl, 'sent-done', (pkt_out.outpacket, status, error))
    else:
        A(pkt_out.remote_idurl, 'sent-failed', (pkt_out.outpacket, status, error))


def Inbox(newpacket, info, status, message):
    """
    This is called when some ``dhnpacket`` was received from remote peer - user seems to be ONLINE.
    """
    A(newpacket.OwnerID, 'inbox-packet', (newpacket, info, status, message))
    ratings.remember_connected_time(newpacket.OwnerID)
    

def Outbox(pkt_out):
    """
    Called when some ``dhnpacket`` is placed in the sending queue.
    This packet can be our Identity packet - this is a sort of PING operation 
    to try to connect with that man.    
    """
    A(pkt_out.outpacket.RemoteID, 'outbox-packet', pkt_out)


def FileSent(workitem, args):
    """
    This is called when transport_control starts the file transfer to some peer.
    Used to count how many times you PING him.
    """
    A(workitem.remoteid, 'file-sent', (workitem, args))


def PacketSendingTimeout(remoteID, packetID):
    """
    Called from ``p2p.io_throttle`` when some packet is timed out.
    Right now this do nothing, state machine ignores that event.
    """
    # dhnio.Dprint(6, 'contact_status.PacketSendingTimeout ' + remoteID)
    A(remoteID, 'sent-timeout', packetID)

