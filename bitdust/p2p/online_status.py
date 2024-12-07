#!/usr/bin/python
# online_status.py
#
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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
    * :red:`ack-receieved`
    * :red:`ack-received`
    * :red:`handshake`
    * :red:`inbox-packet`
    * :red:`init`
    * :red:`offline-check`
    * :red:`ping-failed`
    * :red:`ping-now`
    * :red:`shook-up-hands`
    * :red:`shutdown`
    * :red:`timer-1min`
    * :red:`timer-20sec`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

from twisted.internet.task import LoopingCall
from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.lib import strng
from bitdust.lib import utime

from bitdust.contacts import contactsdb

from bitdust.main import events
from bitdust.main import listeners

from bitdust.p2p import ratings
from bitdust.p2p import commands
from bitdust.p2p import handshaker

from bitdust.transport import callback

from bitdust.userid import my_id
from bitdust.userid import id_url
from bitdust.userid import global_id

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
    Called from top level code when the software is starting.
    Needs to be called before other methods here.
    """
    global _OfflineCheckTask
    global _ShutdownFlag
    if _Debug:
        lg.out(_DebugLevel, 'online_status.init')
    _ShutdownFlag = False
    callback.insert_inbox_callback(1, Inbox)  # try to not overwrite top callback in the list, but stay on top
    callback.add_queue_item_status_callback(OutboxStatus)
    _OfflineCheckTask = LoopingCall(RunOfflineChecks)
    _OfflineCheckTask.start(10, now=False)


def shutdown():
    """
    Called from top level code when the software is stopping.
    """
    global _OfflineCheckTask
    global _ShutdownFlag
    global _OnlineStatusDict
    if _Debug:
        lg.out(_DebugLevel, 'online_status.shutdown')
    handshaker.cancel_all()
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


def online_statuses():
    global _OnlineStatusDict
    return _OnlineStatusDict


def check_create(idurl, keep_alive=True):
    """
    Creates new instance of online_status() state machine and send "init" event to it.
    """
    idurl = strng.to_bin(idurl)
    if id_url.is_empty(idurl):
        return False
    if not id_url.is_cached(idurl):
        return False
    idurl = id_url.field(idurl)
    if idurl not in list(_OnlineStatusDict.keys()):
        A(idurl, 'init', keep_alive=keep_alive)
        if _Debug:
            lg.out(_DebugLevel, 'online_status.check_create instance for %r was not found, made a new with state OFFLINE' % idurl)
    return True


#------------------------------------------------------------------------------


def on_ping_failed(err, idurl=None, channel=None):
    if _Debug:
        lg.args(_DebugLevel, err=err, idurl=idurl, channel=channel)
    return err


def ping(idurl, channel=None, ack_timeout=15, ping_retries=0, keep_alive=False):
    """
    Doing handshake with remote node only if it is currently not connected.
    Returns Deferred object.
    """
    idurl = strng.to_bin(idurl)
    if _Debug:
        lg.args(_DebugLevel, idurl=idurl, keep_alive=keep_alive, channel=channel)
    result = Deferred()
    result.addErrback(on_ping_failed, idurl=idurl, channel=channel)
    if id_url.is_empty(idurl):
        result.errback(Exception('empty idurl provided'))
        return result
    if not id_url.is_cached(idurl):
        if _Debug:
            lg.dbg(_DebugLevel, 'user identity %r not cached yet, executing clean handshake' % idurl)
        return handshaker.ping(
            idurl=idurl,
            ack_timeout=ack_timeout,
            ping_retries=ping_retries,
            channel=channel or 'clean_ping',
            keep_alive=keep_alive,
        )
    idurl = id_url.field(idurl)
    if not isKnown(idurl):
        if not check_create(idurl, keep_alive=keep_alive):
            raise Exception('can not create instance')
    A(idurl, 'ping-now', result, channel=channel, ack_timeout=ack_timeout, ping_retries=ping_retries, original_idurl=idurl.to_original())
    return result


def handshake(idurl, channel=None, ack_timeout=None, ping_retries=2, keep_alive=False):
    """
    Immediately doing handshake with remote node by fetching remote identity file and then
    sending my own Identity() to remote peer and wait for an Ack() packet.
    Returns Deferred object.
    """
    idurl = strng.to_bin(idurl)
    if _Debug:
        lg.args(_DebugLevel, idurl=idurl, keep_alive=keep_alive, channel=channel, ack_timeout=ack_timeout, ping_retries=ping_retries)
    result = Deferred()
    result.addErrback(on_ping_failed, idurl=idurl, channel=channel)
    if id_url.is_empty(idurl):
        result.errback(Exception('empty idurl provided'))
        return result
    if not id_url.is_cached(idurl):
        if _Debug:
            lg.dbg(_DebugLevel, 'user identity %r not cached yet, executing clean handshake' % idurl)
        return handshaker.ping(
            idurl=idurl,
            ack_timeout=ack_timeout,
            ping_retries=ping_retries,
            channel=channel or 'clean_handshake',
            keep_alive=keep_alive,
        )
    idurl = id_url.field(idurl)
    if not isKnown(idurl):
        if not check_create(idurl, keep_alive=keep_alive):
            raise Exception('can not create instance')
    A(idurl, 'handshake', result, channel=channel, ack_timeout=ack_timeout, ping_retries=ping_retries, original_idurl=idurl.to_original())
    return result


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
    if id_url.is_empty(idurl):
        return False
    if not id_url.is_cached(idurl):
        return False
    idurl = id_url.field(idurl)
    return idurl in list(_OnlineStatusDict.keys())


def isOnline(idurl):
    """
    Return True if given contact's state is ONLINE.
    """
    global _ShutdownFlag
    if _ShutdownFlag:
        return False
    if id_url.is_empty(idurl):
        return False
    if not id_url.is_cached(idurl):
        return False
    idurl = id_url.field(idurl)
    if not isKnown(idurl):
        return False
    return A(idurl).state in [
        'CONNECTED',
        'PING?',
    ]


def isOffline(idurl):
    """
    Return True if given contact's state is OFFLINE.
    """
    global _ShutdownFlag
    if _ShutdownFlag:
        return True
    if id_url.is_empty(idurl):
        return True
    if not id_url.is_cached(idurl):
        return True
    idurl = id_url.field(idurl)
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
    if id_url.is_empty(idurl):
        return False
    if not id_url.is_cached(idurl):
        return False
    idurl = id_url.field(idurl)
    if not isKnown(idurl):
        return False
    return A(idurl).state == 'PING'


def getInstance(idurl, autocreate=True):
    if _ShutdownFlag:
        return None
    if id_url.is_empty(idurl):
        return None
    if not id_url.is_cached(idurl):
        return None
    idurl = id_url.field(idurl)
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
    if id_url.is_empty(idurl):
        return None
    if not id_url.is_cached(idurl):
        return None
    idurl = id_url.field(idurl)
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
    if id_url.is_empty(idurl):
        return '?'
    if not id_url.is_cached(idurl):
        return '?'
    idurl = id_url.field(idurl)
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


def remove_online_status_listener_callback(idurl, callback_method=None, callback_id=None):
    """
    Release already added listener callback from the corresponding ``online_contact()`` automat.
    """
    online_status_instance = getInstance(idurl)
    if not online_status_instance:
        return False
    return online_status_instance.removeStateChangedCallback(cb=callback_method, callback_id=callback_id) > 0


#------------------------------------------------------------------------------


def populate_online_statuses():
    for online_s in online_statuses().values():
        listeners.push_snapshot('online_status', snap_id=online_s.idurl.to_text(), data=online_s.to_json())


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
    if pkt_out.outpacket.RemoteID.to_bin() == my_id.getIDURL().to_bin():
        return False
    if pkt_out.outpacket.CreatorID.to_bin() != my_id.getIDURL().to_bin():
        return False
    if status == 'finished':
        if error == 'unanswered' and pkt_out.outpacket.Command == commands.Identity():
            if pkt_out.outpacket.OwnerID == my_id.getIDURL() and pkt_out.outpacket.CreatorID == my_id.getIDURL():
                # if not handshaker.is_running(pkt_out.outpacket.RemoteID):
                if _Debug:
                    lg.dbg(_DebugLevel, 'ping packet %s addressed to %r was "unanswered"' % (pkt_out, pkt_out.outpacket.RemoteID))
    else:
        if _Debug:
            lg.dbg(_DebugLevel, 'packet %s is "%s" with %s error: %r' % (pkt_out, status, pkt_out.outpacket, error))
    if pkt_out.outpacket.Command == commands.Identity():
        if pkt_out.outpacket.OwnerID == my_id.getIDURL() and pkt_out.outpacket.CreatorID == my_id.getIDURL():
            if handshaker.is_running(pkt_out.outpacket.RemoteID):
                handshaker.on_identity_packet_outbox_status(pkt_out, status, error)
    return False


def Inbox(newpacket, info, status, message):
    """
    This is called when some ``packet`` was received from remote peer - user seems to be ONLINE.
    """
    global _ShutdownFlag
    if _ShutdownFlag:
        return False
    if id_url.is_cached(newpacket.OwnerID):
        if newpacket.OwnerID == my_id.getIDURL():
            return False
    else:
        if newpacket.OwnerID.to_bin() == my_id.getIDURL().to_bin():
            return False
    if not id_url.is_cached(newpacket.OwnerID):
        return False
    if newpacket.RemoteID != my_id.getIDURL():
        return False
    check_create(newpacket.OwnerID)
    A(newpacket.OwnerID, 'inbox-packet', (newpacket, info, status, message))
    return False


def PacketSendingTimeout(remoteID, packetID):
    """
    Called from ``p2p.io_throttle`` when some packet is timed out.

    Right now this do nothing, to be improved.
    """
    global _ShutdownFlag
    if _ShutdownFlag:
        return False
    if remoteID == my_id.getIDURL():
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
        if utime.utcnow_to_sec1970() - o_status.latest_check_time > 10*60:
            # user is offline and latest check was sent a while ago: lets try to ping user again
            o_status.automat('offline-check')
            continue
        if o_status.latest_inbox_time and utime.utcnow_to_sec1970() - o_status.latest_inbox_time < 60:
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
    idurl = id_url.field(idurl)
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
        'timer-20sec': (20.0, ['PING?']),
    }

    def __init__(self, idurl, name, state, debug_level=0, log_events=False, log_transitions=False, **kwargs):
        """
        Builds `online_status()` state machine.
        """
        self.idurl = idurl
        self.latest_inbox_time = None
        self.latest_check_time = None
        self.keep_alive = False
        super(OnlineStatus, self).__init__(name=name, state=state, debug_level=debug_level, log_events=log_events, log_transitions=log_transitions, **kwargs)
        if _Debug:
            lg.out(_DebugLevel, 'online_status.ContactStatus %s %s %s' % (name, state, idurl))

    def to_json(self):
        j = super().to_json()
        glob_id = global_id.ParseIDURL(self.idurl)
        j.update({
            'idurl': self.idurl.to_text(),
            'global_id': glob_id['customer'],
            'idhost': glob_id['idhost'],
            'username': glob_id['user'],
        })
        return j

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
            lg.out(_DebugLevel, '%s : [%s]->[%s]' % (self.name, oldstate, newstate))
        if newstate == 'CONNECTED':
            lg.info('remote node connected : %s' % self.idurl)
            events.send('node-connected', data=dict(
                global_id=self.idurl.to_id(),
                idurl=self.idurl,
                old_state=oldstate,
                new_state=newstate,
            ))
            listeners.push_snapshot('online_status', snap_id=self.idurl.to_text(), data=self.to_json())
        if newstate == 'OFFLINE' and oldstate != 'AT_STARTUP':
            lg.info('remote node disconnected : %s' % self.idurl)
            events.send('node-disconnected', data=dict(
                global_id=self.idurl.to_id(),
                idurl=self.idurl,
                old_state=oldstate,
                new_state=newstate,
            ))
            listeners.push_snapshot('online_status', snap_id=self.idurl.to_text(), data=self.to_json())
        if newstate == 'PING?' and oldstate != 'AT_STARTUP':
            listeners.push_snapshot('online_status', snap_id=self.idurl.to_text(), data=self.to_json())

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
                self.doReportOffline(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'ping-failed' or event == 'timer-20sec':
                self.state = 'OFFLINE'
                self.doReportOffline(*args, **kwargs)
            elif event == 'handshake' or event == 'ping-now':
                self.doSetCallback(*args, **kwargs)
            elif event == 'inbox-packet' or event == 'ack-received' or event == 'shook-up-hands':
                self.state = 'CONNECTED'
                self.doRememberTime(*args, **kwargs)
                self.doReportConnected(*args, **kwargs)
        #---CONNECTED---
        elif self.state == 'CONNECTED':
            if event == 'ping-failed':
                self.state = 'OFFLINE'
                self.doReportOffline(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doReportOffline(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'timer-1min' and not self.isRecentInbox(*args, **kwargs):
                self.doHandshake(event, *args, **kwargs)
            elif event == 'handshake':
                self.state = 'PING?'
                self.doSetCallback(*args, **kwargs)
                self.doHandshake(event, *args, **kwargs)
            elif event == 'ping-now':
                self.doSetCallback(*args, **kwargs)
                self.doReportAlreadyConnected(*args, **kwargs)
            elif event == 'inbox-packet' or event == 'shook-up-hands' or event == 'ack-receieved':
                self.doRememberTime(*args, **kwargs)
        #---OFFLINE---
        elif self.state == 'OFFLINE':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
            elif event == 'handshake' or event == 'ping-now':
                self.state = 'PING?'
                self.doSetCallback(*args, **kwargs)
                self.doHandshake(event, *args, **kwargs)
            elif event == 'inbox-packet' or event == 'shook-up-hands':
                self.state = 'CONNECTED'
                self.doRememberTime(*args, **kwargs)
                self.doReportConnected(*args, **kwargs)
            elif event == 'offline-check' or event == 'ack-received':
                self.doRememberCheckTime(*args, **kwargs)
                self.doHandshake(event, *args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def isRecentInbox(self, *args, **kwargs):
        """
        Condition method.
        """
        if handshaker.is_running(self.idurl.to_bin()):
            return True
        if not self.latest_inbox_time:
            return False
        return utime.utcnow_to_sec1970() - self.latest_inbox_time > 60

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.handshake_callbacks = []
        self.keep_alive = kwargs.get('keep_alive', True)

    def doSetCallback(self, *args, **kwargs):
        """
        Action method.
        """
        if args and args[0]:
            self.handshake_callbacks.append(args[0])

    def doHandshake(self, event, *args, **kwargs):
        """
        Action method.
        """
        channel = kwargs.get('channel', None)
        ack_timeout = kwargs.get('ack_timeout', 15)
        ping_retries = kwargs.get('ping_retries', 2)
        original_idurl = kwargs.get('original_idurl', self.idurl.to_bin())
        d = None
        if event == 'ping-now':
            d = handshaker.ping(
                idurl=original_idurl,
                ack_timeout=ack_timeout,
                ping_retries=ping_retries,
                channel=channel or 'ping',
                cancel_running=True,
            )
        elif event == 'handshake':
            d = handshaker.ping(
                idurl=original_idurl,
                ack_timeout=ack_timeout,
                ping_retries=ping_retries,
                force_cache=True,
                channel=channel or 'handshake',
                cancel_running=True,
            )
        elif event == 'offline-ping':
            if self.keep_alive:
                d = handshaker.ping(
                    idurl=original_idurl,
                    ack_timeout=ack_timeout,
                    cache_timeout=15,
                    ping_retries=ping_retries,
                    force_cache=True,
                    channel='offline_ping',
                )
        else:
            if self.keep_alive:
                d = handshaker.ping(
                    idurl=original_idurl,
                    ack_timeout=ack_timeout,
                    cache_timeout=15,
                    ping_retries=ping_retries,
                    force_cache=True,
                    channel='idle_ping',
                )
        if d:
            d.addCallback(self._on_ping_success)
            d.addErrback(self._on_ping_failed)

    def doRememberTime(self, *args, **kwargs):
        """
        Action method.
        """
        to_be_remembered = True
        if self.latest_inbox_time:
            if utime.utcnow_to_sec1970() - self.latest_inbox_time < 5*60:
                to_be_remembered = False
        if to_be_remembered:
            ratings.remember_connected_time(self.idurl.to_bin())
        self.latest_inbox_time = utime.utcnow_to_sec1970()

    def doRememberCheckTime(self, *args, **kwargs):
        """
        Action method.
        """
        self.latest_check_time = utime.utcnow_to_sec1970()

    def doReportAlreadyConnected(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, idurl=self.idurl, keep_alive=self.keep_alive, handshake_callbacks=len(self.handshake_callbacks))
        for cb in self.handshake_callbacks:
            if isinstance(cb, Deferred):
                if not cb.called:
                    cb.callback(None)
            else:
                cb(None)
        self.handshake_callbacks = []

    def doReportOffline(self, *args, **kwargs):
        """
        Action method.
        """
        err = args[0] if (args and args[0]) else Exception('user is offline')
        try:
            err_msg = err.getErrorMessage()
        except:
            err_msg = repr(err)
        if _Debug:
            lg.args(_DebugLevel, idurl=self.idurl, err=err_msg, keep_alive=self.keep_alive, handshake_callbacks=len(self.handshake_callbacks))
        for cb in self.handshake_callbacks:
            if isinstance(cb, Deferred):
                if not cb.called:
                    cb.errback(err)
            else:
                cb(err)
        self.handshake_callbacks = []

    def doReportConnected(self, *args, **kwargs):
        """
        Action method.
        """
        response = args[0] if (args and args[0]) else None
        if _Debug:
            lg.args(_DebugLevel, idurl=self.idurl, response=response, keep_alive=self.keep_alive, handshake_callbacks=len(self.handshake_callbacks))
        for cb in self.handshake_callbacks:
            if isinstance(cb, Deferred):
                if not cb.called:
                    cb.callback(response)
            else:
                cb(response)
        self.handshake_callbacks = []

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        global _OnlineStatusDict
        _OnlineStatusDict.pop(self.idurl)
        self.idurl = None
        self.latest_inbox_time = None
        self.handshake_callbacks = None
        self.destroy()

    def _on_ping_success(self, result):
        try:
            response = result[0]
            info = result[1]
        except:
            lg.exc()
        if _Debug:
            lg.out(_DebugLevel, 'online_status._on_ping_success %r : %r' % (self.idurl, result))
        self.automat('shook-up-hands', (
            response,
            info,
        ))
        return None

    def _on_ping_failed(self, err):
        try:
            msg = err.getErrorMessage()
        except:
            msg = str(err)
        if _Debug:
            lg.out(_DebugLevel, 'online_status._on_ping_failed %r : %s' % (self.idurl, msg))
        self.automat('ping-failed', err)
        return None
