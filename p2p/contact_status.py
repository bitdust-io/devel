#!/usr/bin/python
# contact_status.py
#
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (contact_status.py) is part of BitDust Software.
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
.. module:: contact_status

.. raw:: html

    <a href="http://bitdust.io/automats/contact_status/contact_status.png" target="_blank">
    <img src="http://bitdust.io/automats/contact_status/contact_status.png" style="max-width:100%;">
    </a>

A state machine and several extra methods to keep track of current users's online state.
To do p2p communications need to know who is available and who is not at the moment.

This simple state machine is used to detect connection status with remote user.
The situation when remote user replies to a packet sent to him
means that he is currently available over the network.

A one instance of ``contact_status()`` machine is created for
every remote contact and monitor his status.


EVENTS:
    * :red:`file-sent`
    * :red:`inbox-packet`
    * :red:`outbox-packet`
    * :red:`sent-done`
    * :red:`sent-failed`
    * :red:`timer-20sec`

"""

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

import os
import sys
import time

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in contact_status.py')

#------------------------------------------------------------------------------

from logs import lg

from lib import nameurl

from main import settings

from contacts import contactsdb

from automats import automat

from p2p import commands

from transport import callback

import ratings

from userid import my_id

#------------------------------------------------------------------------------

_StatusLabels = {
    'CONNECTED': 'online',
    'ACK?': 'responding',
    'PING': 'checking',
    'OFFLINE': 'offline',
}

_StatusIcons = {
    'CONNECTED': 'icons/online-user01.png',
    'ACK?': 'icons/ackwait-user01.png',
    'PING': 'icons/ping-user01.png',
    'OFFLINE': 'icons/offline-user01.png',
}

#------------------------------------------------------------------------------

_ContactsStatusDict = {}
_ShutdownFlag = False

#------------------------------------------------------------------------------


def init():
    """
    Needs to be called before other methods here.
    """
    lg.out(4, 'contact_status.init')
    callback.insert_inbox_callback(-1, Inbox)
    callback.add_outbox_callback(Outbox)
    callback.add_queue_item_status_callback(OutboxStatus)


def shutdown():
    """
    Called from top level code when the software is finishing.
    """
    lg.out(4, 'contact_status.shutdown')
    global _ShutdownFlag
    global _ContactsStatusDict
    for A in _ContactsStatusDict.values():
        A.destroy()
    _ContactsStatusDict.clear()
    _ShutdownFlag = True


def isKnown(idurl):
    """
    Return `True` if state machine contact_status() already exists for this user.
    """
    if idurl in [None, 'None', '']:
        return False
    global _ContactsStatusDict
    return idurl in _ContactsStatusDict.keys()


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
        A(idurl)
        if _Debug:
            lg.out(
                _DebugLevel,
                'contact_status.isOnline contact %s is not found, made a new instance' %
                idurl)
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
        A(idurl)
        if _Debug:
            lg.out(
                _DebugLevel,
                'contact_status.isOffline contact %s is not found, made a new instance' %
                idurl)
    return A(idurl).state == 'OFFLINE'


def isCheckingNow(idurl):
    """
    Return True if given contact's state is PING or ACK?.
    """
    global _ShutdownFlag
    if _ShutdownFlag:
        return False
    if idurl in [None, 'None', '']:
        return False
    global _ContactsStatusDict
    if idurl not in _ContactsStatusDict.keys():
        A(idurl)
        if _Debug:
            lg.out(
                _DebugLevel,
                'contact_status.isCheckingNow contact %s is not found, made a new instance' %
                idurl)
    st = A(idurl).state
    return st == 'PING' or st == 'ACK?'


def getStatusLabel(idurl):
    """
    Return some text description about the current state of that user.
    """
    global _ShutdownFlag
    if _ShutdownFlag:
        return '?'
    if idurl in [None, 'None', '']:
        return '?'
    global _ContactsStatusDict
    if idurl not in _ContactsStatusDict.keys():
        A(idurl)
        if _Debug:
            lg.out(
                _DebugLevel,
                'contact_status.getStatusLabel contact %s is not found, made a new instance' %
                idurl)
    global _StatusLabels
    return _StatusLabels.get(A(idurl).state, '?')


def getStatusIcon(idurl):
    """
    Return an icon name depending on current state of that user.
    """
    global _ShutdownFlag
    if _ShutdownFlag:
        return '?'
    if idurl in [None, 'None', '']:
        return '?'
    global _ContactsStatusDict
    if idurl not in _ContactsStatusDict.keys():
        A(idurl)
        if _Debug:
            lg.out(
                _DebugLevel,
                'contact_status.getStatusIcon contact %s is not found, made a new instance' %
                idurl)
    global _StatusIcons
    return _StatusIcons.get(A(idurl).state, '?')


def listOfflineSuppliers():
    """
    Loops all suppliers and check their state, return a list of those with state OFFLINE.
    """
    result = []
    for idurl in contactsdb.suppliers():
        if not idurl:
            result.append(idurl)
        elif isOffline(idurl):
            result.append(idurl)
    return result


def listOfflineCustomers():
    """
    Loops all customers and check their state, return a list of those with state OFFLINE.
    """
    result = []
    for idurl in contactsdb.customers():
        if not idurl:
            result.append(idurl)
        elif isOffline(idurl):
            result.append(idurl)
    return result


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
    if idurl not in _ContactsStatusDict:
        if _ShutdownFlag:
            return None
        _ContactsStatusDict[idurl] = ContactStatus(
            idurl, 'status_%s' % nameurl.GetName(idurl), 'OFFLINE', 8)
    if event is not None:
        _ContactsStatusDict[idurl].automat(event, arg)
    return _ContactsStatusDict[idurl]


class ContactStatus(automat.Automat):
    """
    A class to keep track of user's online status.
    """

    fast = True

    timers = {
        'timer-20sec': (20.0, ['PING', 'ACK?']),
    }

    def __init__(self, idurl, name, state, debug_level):
        self.idurl = idurl
        self.time_connected = None
        automat.Automat.__init__(self, name, state, debug_level)
        if _Debug:
            lg.out(
                _DebugLevel + 2, 'contact_status.ContactStatus %s %s %s' %
                (name, state, idurl))

    def state_changed(self, oldstate, newstate, event, arg):
        if _Debug:
            lg.out(
                _DebugLevel -
                2,
                '%s : [%s]->[%s]' %
                (nameurl.GetName(
                    self.idurl),
                    oldstate.lower(),
                    newstate.lower()))

    def A(self, event, arg):
        #---CONNECTED---
        if self.state == 'CONNECTED':
            if event == 'sent-failed' and self.Fails >= 3 and self.isDataPacket(
                    arg):
                self.state = 'OFFLINE'
                self.doRepaint(arg)
            elif event == 'sent-failed' and self.isDataPacket(arg) and self.Fails < 3:
                self.Fails += 1
        #---OFFLINE---
        elif self.state == 'OFFLINE':
            if event == 'outbox-packet' and self.isPingPacket(arg):
                self.state = 'PING'
                self.AckCounter = 0
                self.doRepaint(arg)
            elif event == 'inbox-packet':
                self.state = 'CONNECTED'
                self.Fails = 0
                self.doRememberTime(arg)
                self.doRepaint(arg)
        #---PING---
        elif self.state == 'PING':
            if event == 'sent-done':
                self.state = 'ACK?'
                self.AckCounter = 0
            elif event == 'inbox-packet':
                self.state = 'CONNECTED'
                self.Fails = 0
                self.doRememberTime(arg)
                self.doRepaint(arg)
            elif event == 'file-sent':
                self.AckCounter += 1
            elif event == 'sent-failed' and self.AckCounter > 1:
                self.AckCounter -= 1
            elif event == 'timer-20sec' or (event == 'sent-failed' and self.AckCounter == 1):
                self.state = 'OFFLINE'
                self.doRepaint(arg)
        #---ACK?---
        elif self.state == 'ACK?':
            if event == 'inbox-packet':
                self.state = 'CONNECTED'
                self.Fails = 0
                self.doRememberTime(arg)
                self.doRepaint(arg)
            elif event == 'timer-20sec':
                self.state = 'OFFLINE'
            elif event == 'outbox-packet' and self.isPingPacket(arg):
                self.state = 'PING'
                self.AckCounter = 0
                self.doRepaint(arg)
        return None

    def isPingPacket(self, arg):
        """
        Condition method.
        """
        pkt_out = arg
        return pkt_out.outpacket and pkt_out.outpacket.Command == commands.Identity(
        ) and pkt_out.wide is True

    def isDataPacket(self, arg):
        """
        Condition method.
        """
        pkt_out, status, error = arg
        return pkt_out.outpacket.Command not in [
            commands.Identity(), commands.Ack()]

    def doRememberTime(self, arg):
        """
        Action method.
        """
        self.time_connected = time.time()

    def doRepaint(self, arg):
        """
        Action method.
        """
        if not settings.NewWebGUI():
            from web import webcontrol
            webcontrol.OnAliveStateChanged(self.idurl)
        else:
            from web import control
            control.request_update([('contact', self.idurl)])

#------------------------------------------------------------------------------


def OutboxStatus(pkt_out, status, error=''):
    """
    This method is called when raised a status report after
    sending a packet to remote peer.
    If packet sending was failed - user seems to be OFFLINE.
    """
    if pkt_out.remote_idurl == my_id.getLocalID():
        return False
    if pkt_out.outpacket.CreatorID != my_id.getLocalID():
        return False
    if status == 'finished':
        A(pkt_out.remote_idurl, 'sent-done', (pkt_out, status, error))
    else:
        if _Debug:
            lg.out(
                _DebugLevel, 'contact_status.OutboxStatus %s: [%s] with %s' %
                (status, pkt_out, pkt_out.outpacket))
        A(pkt_out.remote_idurl, 'sent-failed', (pkt_out, status, error))
    return False


def Inbox(newpacket, info, status, message):
    """
    This is called when some ``packet`` was received from remote peer - user seems to be ONLINE.
    """
    if newpacket.OwnerID == my_id.getLocalID():
        return False
    if newpacket.RemoteID != my_id.getLocalID():
        return False
    A(newpacket.OwnerID, 'inbox-packet', (newpacket, info, status, message))
    ratings.remember_connected_time(newpacket.OwnerID)
    return False


def Outbox(pkt_out):
    """
    Called when some ``packet`` is placed in the sending queue.
    This packet can be our Identity packet - this is a sort of PING operation
    to try to connect with that man.
    """
    if pkt_out.outpacket.RemoteID == my_id.getLocalID():
        return False
    if pkt_out.outpacket.CreatorID != my_id.getLocalID():
        return False
    A(pkt_out.outpacket.RemoteID, 'outbox-packet', pkt_out)
    return False


def FileSent(workitem, args):
    """
    This is called when transport_control starts the file transfer to some peer.
    Used to count how many times you PING him.
    """
    if workitem.remoteid == my_id.getLocalID():
        return
    A(workitem.remoteid, 'file-sent', (workitem, args))


def PacketSendingTimeout(remoteID, packetID):
    """
    Called from ``p2p.io_throttle`` when some packet is timed out.
    Right now this do nothing, state machine ignores that event.
    """
    if remoteID == my_id.getLocalID():
        return
    A(remoteID, 'sent-timeout', packetID)
