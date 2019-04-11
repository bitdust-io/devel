#!/usr/bin/python
# online_status.py
#
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (online_status.py) is part of BitDust Software.
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
.. module:: online_status
.. role:: red

BitDust online_status() Automat

    <a href="https://bitdust.io/automats/online_status/online_status.png" target="_blank">
    <img src="https://bitdust.io/automats/online_status/online_status.png" style="max-width:100%;">
    </a>

A state machine and several extra methods to keep track of current users's online state.
To do p2p communications need to know who is available and who is not at the moment.

This simple state machine is used to detect connection status with remote user.
The situation when remote user replies to a packet sent to him
means that he is currently available over the network.

A one instance of ``online_status()`` machine is created for
every remote contact and monitor his status.


EVENTS:
    * :red:`inbox-packet`
    * :red:`init`
    * :red:`offline-check`
    * :red:`ping-failed`
    * :red:`ping-now`
    * :red:`shutdown`
    * :red:`timer-15sec`
    * :red:`timer-1min`
"""


#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

import sys
import time

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in online_status.py')

from twisted.internet.task import LoopingCall

#------------------------------------------------------------------------------

from logs import lg

from lib import nameurl
from lib import strng

from contacts import contactsdb

from automats import automat

from p2p import ratings
from p2p import commands
from p2p import propagate

from transport import callback

from userid import my_id
from userid import global_id

#------------------------------------------------------------------------------

_StatusLabels = {
    'CONNECTED': 'online',
    'PING?': 'checking',
    'OFFLINE': 'offline',
}

#------------------------------------------------------------------------------

_OnlineStatusDict = {}
_ShutdownFlag = False
_OfflineCheckTask = None

#------------------------------------------------------------------------------


def init():
    """
    Needs to be called before other methods here.
    """
    global _OfflineCheckTask
    lg.out(4, 'online_status.init')
    callback.insert_inbox_callback(1, Inbox)  # try to not overwrite top callback in the list, but stay on top
    callback.add_queue_item_status_callback(OutboxStatus)
    _OfflineCheckTask = LoopingCall(RunOfflineChecks)
    _OfflineCheckTask.start(10, now=False)


def shutdown():
    """
    Called from top level code when the software is finishing.
    """
    global _OfflineCheckTask
    global _ShutdownFlag
    global _OnlineStatusDict
    lg.out(4, 'online_status.shutdown')
    _OfflineCheckTask.stop()
    del _OfflineCheckTask
    _OfflineCheckTask = None
    callback.remove_inbox_callback(Inbox)
    callback.remove_queue_item_status_callback(OutboxStatus)
    for o_status in list(_OnlineStatusDict.values()):
        o_status.automat('shutdown')
    _OnlineStatusDict.clear()
    _ShutdownFlag = True


#------------------------------------------------------------------------------

def check_create(idurl):
    """
    Creates new instance of online_status() state machine and send "init" event to it.
    """
    if idurl in [None, 'None', '', b'None', b'', ]:
        return False
    idurl = strng.to_bin(idurl)
    if idurl not in list(_OnlineStatusDict.keys()):
        A(idurl, 'init')
        lg.info('online_status() for %r was not found, made a new instance with state OFFLINE' % idurl)
    return True

#------------------------------------------------------------------------------

def isKnown(idurl):
    """
    Return `True` if state machine online_status() already exists for this
    user.
    """
    global _OnlineStatusDict
    global _ShutdownFlag
    if _ShutdownFlag:
        return False
    if idurl in [None, 'None', '', b'None', b'', ]:
        return False
    idurl = strng.to_bin(idurl)
    return idurl in list(_OnlineStatusDict.keys())


def isOnline(idurl):
    """
    Return True if given contact's state is ONLINE.
    """
    global _ShutdownFlag
    if _ShutdownFlag:
        return False
    if idurl in [None, 'None', '', b'None', b'', ]:
        return False
    idurl = strng.to_bin(idurl)
    if not isKnown(idurl):
        return False
    return A(idurl).state in ['CONNECTED', 'PING?', ]


def isOffline(idurl):
    """
    Return True if given contact's state is OFFLINE.
    """
    global _ShutdownFlag
    if _ShutdownFlag:
        return True
    if idurl in [None, 'None', '', b'None', b'', ]:
        return True
    idurl = strng.to_bin(idurl)
    if not isKnown(idurl):
        return True
    return A(idurl).state == 'OFFLINE'


def isCheckingNow(idurl):
    """
    Return True if given contact's state is PING or ACK?.
    """
    global _ShutdownFlag
    if _ShutdownFlag:
        return False
    if idurl in [None, 'None', '', b'None', b'', ]:
        return False
    idurl = strng.to_bin(idurl)
    if not isKnown(idurl):
        return False
    return A(idurl).state == 'PING'


def getInstance(idurl, autocreate=True):
    """
    """
    if _ShutdownFlag:
        return None
    if idurl in [None, 'None', '', b'None', b'', ]:
        return None
    idurl = strng.to_bin(idurl)
    if not isKnown(idurl) and not autocreate:
        return None
    check_create(idurl)
    return A(idurl)


def stateToLabel(state, default='?'):
    global _StatusLabels
    return _StatusLabels.get(state, default)


def getCurrentState(idurl):
    """
    Return the current state of that user or `None` if that contact is unknown.
    """
    global _ShutdownFlag
    if _ShutdownFlag:
        return None
    if idurl in [None, 'None', '', b'None', b'', ]:
        return None
    idurl = strng.to_bin(idurl)
    if not isKnown(idurl):
        return None
    return A(idurl).state


def getStatusLabel(idurl):
    """
    Return some text description about the current state of that user.
    """
    global _ShutdownFlag
    if _ShutdownFlag:
        return '?'
    if idurl in [None, 'None', '', b'None', b'', ]:
        return '?'
    idurl = strng.to_bin(idurl)
    if not isKnown(idurl):
        return '?'
    return stateToLabel(A(idurl).state)


def listOfflineSuppliers(customer_idurl=None):
    """
    Loops all suppliers and check their state, return a list of those with
    state OFFLINE.
    """
    result = []
    for idurl in contactsdb.suppliers(customer_idurl=customer_idurl):
        if not idurl:
            result.append(idurl)
        elif isOffline(idurl):
            result.append(idurl)
    return result


def listOfflineCustomers():
    """
    Loops all customers and check their state, return a list of those with
    state OFFLINE.
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

def add_online_status_listener_callback(idurl, callback_method, oldstate=None, newstate=None, callback_id=None):
    """
    Attach new listener callback to the corresponding ``online_contact()`` automat for node with ``idurl``.
    """
    online_status_instance = getInstance(idurl)
    if not online_status_instance:
        return False
    online_status_instance.addStateChangedCallback(
        callback_method,
        newstate=newstate,
        oldstate=oldstate,
        callback_id=callback_id,
    )
    return True


def remove_online_status_listener_callbackove_(idurl, callback_method=None, callback_id=None):
    """
    Release already added listener callback from the corresponding ``online_contact()`` automat.
    """
    online_status_instance = getInstance(idurl)
    if not online_status_instance:
        return False
    return online_status_instance.removeStateChangedCallback(cb=callback_method, callback_id=callback_id) > 0    

#------------------------------------------------------------------------------

def OutboxStatus(pkt_out, status, error=''):
    """
    This method is called when raised a status report after sending a packet to
    remote peer.

    If packet sending was failed - user seems to be OFFLINE.
    """
    global _ShutdownFlag
    if _ShutdownFlag:
        return False
    if pkt_out.outpacket.RemoteID == my_id.getLocalID():
        return False
    if pkt_out.outpacket.CreatorID != my_id.getLocalID():
        return False
    if status == 'finished':
        if error == 'unanswered' and pkt_out.outpacket.Command == commands.Identity():
            check_create(pkt_out.outpacket.RemoteID)
            if _Debug:
                lg.out(_DebugLevel, 'online_status.OutboxStatus packet %s was "unanswered"' % pkt_out)
            A(pkt_out.outpacket.RemoteID, 'ping-failed', (pkt_out, status, error))
        # else:
        #     A(pkt_out.outpacket.RemoteID, 'sent-done', (pkt_out, status, error))
    else:
        if _Debug:
            lg.out(_DebugLevel, 'online_status.OutboxStatus %s: [%s] with %s' % (status, pkt_out, pkt_out.outpacket))
        if status == 'cancelled':
            if _Debug:
                lg.out(_DebugLevel, '    skipped')
        # else:
            # lg.warn('sending event "sent-failed" to contact status of : %s' % pkt_out.remote_idurl)
        #     A(pkt_out.outpacket.RemoteID, 'sent-failed', (pkt_out, status, error))
    return False


def Inbox(newpacket, info, status, message):
    """
    This is called when some ``packet`` was received from remote peer - user seems to be ONLINE.
    """
    global _ShutdownFlag
    if _ShutdownFlag:
        return False
    if newpacket.OwnerID == my_id.getLocalID():
        return False
    if newpacket.RemoteID != my_id.getLocalID():
        return False
    check_create(newpacket.OwnerID)
    A(newpacket.OwnerID, 'inbox-packet', (newpacket, info, status, message))
    ratings.remember_connected_time(newpacket.OwnerID)
    return False


def PacketSendingTimeout(remoteID, packetID):
    """
    Called from ``p2p.io_throttle`` when some packet is timed out.
 
    Right now this do nothing, to be improved.
    """
    global _ShutdownFlag
    if _ShutdownFlag:
        return False
    if remoteID == my_id.getLocalID():
        return False
    check_create(remoteID)
    # TODO: do something in that case ... send event "ping-now" ?
    A(remoteID, 'sent-timeout', packetID)
    return True

#------------------------------------------------------------------------------

def RunOfflineChecks():
    for o_status in list(_OnlineStatusDict.values()):
        if o_status.state != 'OFFLINE':
            # if user is online or checking: do nothing
            continue
        if not o_status.latest_check_time:
            # if no checks done yet but he is offline: ping user
            o_status.automat('offline-check')
            continue
        if time.time() - o_status.latest_check_time > 10 * 60:
            # user is offline and latest check was sent a while ago: lets try to ping user again
            o_status.automat('offline-check')
            continue
        if o_status.latest_inbox_time and time.time() - o_status.latest_inbox_time < 60:
            # user is offline, but we know that he was online recently: lets try to ping him again
            o_status.automat('offline-check')
            continue
    return True

#------------------------------------------------------------------------------

def A(idurl, event=None, *args, **kwargs):
    """
    Access method to interact with a state machine created for given contact.
    """
    global _ShutdownFlag
    global _OnlineStatusDict
    idurl = strng.to_bin(idurl)
    if idurl not in _OnlineStatusDict:
        if _ShutdownFlag:
            return None
        if not event:
            return None
        _OnlineStatusDict[idurl] = OnlineStatus(
            idurl=idurl,
            name='online_%s' % global_id.UrlToGlobalID(idurl),
            state='AT_STARTUP',
            debug_level=_DebugLevel,
            log_events=False,
            log_transitions=_Debug,
        )
    if event is not None:
        _OnlineStatusDict[idurl].automat(event, *args, **kwargs)
    return _OnlineStatusDict[idurl]

#------------------------------------------------------------------------------

class OnlineStatus(automat.Automat):
    """
    This class implements all the functionality of ``online_status()`` state machine.
    """

    timers = {
        'timer-1min': (60, ['CONNECTED']),
        'timer-15sec': (15.0, ['PING?']),
        }

    def __init__(self, idurl, name, state, debug_level=0, log_events=False, log_transitions=False, **kwargs):
        """
        Builds `online_status()` state machine.
        """
        self.idurl = idurl
        self.latest_inbox_time = None
        self.latest_check_time = None
        super(OnlineStatus, self).__init__(
            name=name,
            state=state,
            debug_level=debug_level,
            log_events=log_events,
            log_transitions=log_transitions,
            **kwargs
        )
        if _Debug:
            lg.out(_DebugLevel + 2, 'online_status.ContactStatus %s %s %s' % (name, state, idurl))

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of `online_status()` machine.
        """

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `online_status()` state were changed.
        """
        if _Debug:
            lg.out(_DebugLevel - 2, '%s : [%s]->[%s]' % (self.name, oldstate, newstate))

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in the `online_status()`
        but automat state was not changed.
        """

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'OFFLINE'
                self.doInit(*args, **kwargs)
        #---PING?---
        elif self.state == 'PING?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'inbox-packet':
                self.state = 'CONNECTED'
                self.doRememberTime(*args, **kwargs)
            elif event == 'ping-failed' or event == 'timer-15sec':
                self.state = 'OFFLINE'
        #---CONNECTED---
        elif self.state == 'CONNECTED':
            if event == 'ping-failed':
                self.state = 'OFFLINE'
            elif event == 'ping-now':
                self.state = 'PING?'
                self.doPing(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'timer-1min' and not self.isRecentInbox(*args, **kwargs):
                self.doPing(*args, **kwargs)
            elif event == 'inbox-packet':
                self.doRememberTime(*args, **kwargs)
        #---OFFLINE---
        elif self.state == 'OFFLINE':
            if event == 'ping-now':
                self.state = 'PING?'
                self.doPing(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'inbox-packet':
                self.state = 'CONNECTED'
                self.doRememberTime(*args, **kwargs)
            elif event == 'offline-check':
                self.doRememberCheckTime(*args, **kwargs)
                self.doPing(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def isRecentInbox(self, *args, **kwargs):
        """
        Condition method.
        """
        if not self.latest_inbox_time:
            return False
        return time.time() - self.latest_inbox_time > 20

    def doPing(self, *args, **kwargs):
        """
        Action method.
        """
        try:
            timeout = int(args[0])
        except:
            timeout = 15
        d = propagate.PingContact(self.idurl, timeout=timeout)
        d.addCallback(self._on_ping_success)
        d.addErrback(self._on_ping_failed)

    def doRememberTime(self, *args, **kwargs):
        """
        Action method.
        """
        self.latest_inbox_time = time.time()

    def doRememberCheckTime(self, *args, **kwargs):
        """
        Action method.
        """
        self.latest_check_time = time.time()

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.idurl = None
        self.latest_inbox_time = None
        self.destroy()

    def _on_ping_success(self, result):
        try:
            response, info = result
            if _Debug:
                lg.out(_DebugLevel, 'online_status._on_ping_success %s : %s %s' % (
                    self.idurl, response, info, ))
        except:
            lg.exc()
        return (response, info, )

    def _on_ping_failed(self, err):
        try:
            msg = err.getErrorMessage()
        except:
            msg = str(err)
        if _Debug:
            lg.out(_DebugLevel, 'online_status._on_ping_failed %s : %s' % (self.idurl, msg, ))
        self.automat('ping-failed')
        return None

