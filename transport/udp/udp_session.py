#!/usr/bin/env python
# udp_session.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (udp_session.py) is part of BitDust Software.
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


"""
.. module:: udp_session.

BitDust udp_session() Automat


EVENTS:
    * :red:`datagram-received`
    * :red:`init`
    * :red:`send-keep-alive`
    * :red:`shutdown`
    * :red:`timer-10sec`
    * :red:`timer-1sec`
    * :red:`timer-20sec`
    * :red:`timer-30sec`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

import os
import sys
import time

from twisted.internet import reactor  # @UnresolvedImport

#------------------------------------------------------------------------------

from logs import lg

from lib import strng
from lib import misc
from lib import udp

from automats import automat

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 14

#------------------------------------------------------------------------------

MIN_PROCESS_SESSIONS_DELAY = 0.001
MAX_PROCESS_SESSIONS_DELAY = 1.0

#------------------------------------------------------------------------------

_SessionsDict = {}
_SessionsDictByPeerAddress = {}
_SessionsDictByPeerID = {}
_KnownPeersDict = {}
_KnownUserIDsDict = {}
_PendingOutboxFiles = []
_ProcessSessionsTask = None
_ProcessSessionsDelay = MIN_PROCESS_SESSIONS_DELAY

#------------------------------------------------------------------------------


def sessions():
    """
    """
    global _SessionsDict
    return _SessionsDict


def sessions_by_peer_address():
    """
    """
    global _SessionsDictByPeerAddress
    return _SessionsDictByPeerAddress


def sessions_by_peer_id():
    """
    """
    global _SessionsDictByPeerID
    return _SessionsDictByPeerID


def pending_outbox_files():
    """
    """
    global _PendingOutboxFiles
    return _PendingOutboxFiles

#------------------------------------------------------------------------------


def create(node, peer_address, peer_id=None):
    """
    """
    if _Debug:
        lg.out(_DebugLevel, 'udp_session.create peer_address=%s' % str(peer_address))
    s = UDPSession(node, peer_address, peer_id)
    sessions()[s.id] = s
    try:
        sessions_by_peer_address()[peer_address].append(s)
    except:
        sessions_by_peer_address()[peer_address] = [s, ]
    if peer_id:
        try:
            sessions_by_peer_id()[peer_id].append(s)
        except:
            sessions_by_peer_id()[peer_id] = [s, ]
    return s


def get(peer_address):
    """
    """
    return sessions_by_peer_address().get(peer_address, [])


def get_by_peer_id(peer_id):
    """
    """
    return sessions_by_peer_id().get(peer_id, [])


def close(peer_address):
    """
    """
    active_sessions = get(peer_address)
    if not active_sessions:
        return False
    for s in active_sessions:
        s.automat('shutdown')
    return True


def add_pending_outbox_file(filename, host, description='', result_defer=None, keep_alive=True):
    """
    """
    pending_outbox_files().append((filename, host, description, result_defer, keep_alive, time.time()))
    if _Debug:
        lg.out(_DebugLevel, 'udp_session.add_pending_outbox_file %s for %s : %s' % (
            os.path.basename(filename), host, description))


def remove_pending_outbox_file(host, filename):
    ok = False
    i = 0
    while i < len(pending_outbox_files()):
        fn, hst, description, result_defer, keep_alive, tm = pending_outbox_files()[i]
        if fn == filename and host == hst:
            if _Debug:
                lg.out(_DebugLevel, 'udp_interface.cancel_outbox_file removed pending %s for %s' % (os.path.basename(fn), hst))
            pending_outbox_files().pop(i)
            ok = True
        else:
            i += 1
    return ok


def report_and_remove_pending_outbox_files_to_host(remote_host, error_message):
    """
    """
    from transport.udp import udp_interface
    global _PendingOutboxFiles
    i = 0
    while i < len(_PendingOutboxFiles):
        filename, host, description, result_defer, keep_alive, tm = _PendingOutboxFiles[
            i]
        if host != remote_host:
            i += 1
            continue
        try:
            udp_interface.interface_cancelled_file_sending(
                remote_host, filename, 0, description, error_message).addErrback(lambda err: lg.exc(err))
        except Exception as exc:
            lg.warn(str(exc))
        if result_defer:
            result_defer.callback(
                ((filename, description), 'failed', error_message))
        _PendingOutboxFiles.pop(i)


def process_sessions(sessions_to_process=None):
    global _ProcessSessionsTask
    global _ProcessSessionsDelay
    has_activity = False
    if not sessions_to_process:
        sessions_to_process = list(sessions().values())
    for s in sessions_to_process:
        if not s.peer_id:
            continue
        if not s.file_queue:
            continue
        if s.state != 'CONNECTED':
            continue
        has_outbox = s.file_queue.process_outbox_queue()
        has_sends = s.file_queue.process_outbox_files()
        if has_sends or has_outbox:
            has_activity = True
    if _ProcessSessionsTask is None or _ProcessSessionsTask.called:
        if has_activity:
            _ProcessSessionsDelay = MIN_PROCESS_SESSIONS_DELAY
        else:
            _ProcessSessionsDelay = misc.LoopAttenuation(
                _ProcessSessionsDelay, has_activity,
                MIN_PROCESS_SESSIONS_DELAY, MAX_PROCESS_SESSIONS_DELAY,)
        # attenuation
        _ProcessSessionsTask = reactor.callLater(  # @UndefinedVariable
            _ProcessSessionsDelay, process_sessions)


def stop_process_sessions():
    global _ProcessSessionsTask
    if _ProcessSessionsTask:
        if _ProcessSessionsTask.active():
            _ProcessSessionsTask.cancel()
        _ProcessSessionsTask = None

#------------------------------------------------------------------------------


class UDPSession(automat.Automat):
    """
    This class implements all the functionality of the ``udp_session()`` state
    machine.
    """

    fast = True

    timers = {
        'timer-1sec': (1.0, ['PING', 'GREETING']),
        'timer-30sec': (30.0, ['GREETING']),
        'timer-10sec': (10.0, ['CONNECTED']),
        'timer-20sec': (20.0, ['PING']),
    }

    MESSAGES = {
        'MSG_1': 'remote peer is not active',
        'MSG_2': 'greeting is timed out',
        'MSG_3': 'ping remote machine has failed',
        'MSG_4': 'session has been closed at startup',
    }

    def __init__(self, node, peer_address, peer_id=None):
        from transport.udp import udp_file_queue
        self.node = node
        self.peer_address = peer_address
        self.peer_id = peer_id
        self.peer_idurl = None
        self.bytes_sent = 0
        self.bytes_received = 0
        self.file_queue = udp_file_queue.FileQueue(self)
        name = 'udp_session[%s:%d:%s]' % (
            self.peer_address[0], self.peer_address[1], str(self.peer_id))
        automat.Automat.__init__(self, name, 'AT_STARTUP', debug_level=_DebugLevel, log_events=_Debug)

    def msg(self, msgid, *args, **kwargs):
        return self.MESSAGES.get(msgid, '')

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the
        state machine.
        """
        if _Debug:
            self.log_events = True
            self.log_transitions = True
        self.last_datagram_received_time = 0
        self.my_rtt_id = '0'  # out
        self.peer_rtt_id = '0'  # in
        self.rtts = {}
        self.min_rtt = None

    def send_packet(self, command, payload):
        self.bytes_sent += len(payload)
        return udp.send_command(self.node.listen_port, command,
                                payload, self.peer_address)

    def A(self, event, *args, **kwargs):
        #---CONNECTED---
        if self.state == 'CONNECTED':
            if event == 'shutdown' or ( event == 'timer-10sec' and not self.isSessionActive(*args, **kwargs) ):
                self.state = 'CLOSED'
                self.doErrMsg(event,self.msg('MSG_1', *args, **kwargs))
                self.doClosePendingFiles(*args, **kwargs)
                self.doNotifyDisconnected(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'datagram-received' and self.isGreeting(*args, **kwargs):
                self.doAcceptGreeting(*args, **kwargs)
                self.doFinishRTT(*args, **kwargs)
                self.doAlive(*args, **kwargs)
            elif event == 'datagram-received' and self.isPayloadData(*args, **kwargs):
                self.doReceiveData(*args, **kwargs)
            elif event == 'datagram-received' and self.isPing(*args, **kwargs):
                self.doAcceptPing(*args, **kwargs)
                self.doGreeting(*args, **kwargs)
            elif event == 'send-keep-alive' or event == 'timer-10sec':
                self.doAlive(*args, **kwargs)
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'PING'
                self.doInit(*args, **kwargs)
                self.doStartRTT(*args, **kwargs)
                self.doPing(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doErrMsg(event,self.msg('MSG_4', *args, **kwargs))
                self.doClosePendingFiles(*args, **kwargs)
                self.doNotifyDisconnected(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---PING---
        elif self.state == 'PING':
            if event == 'timer-1sec':
                self.doStartRTT(*args, **kwargs)
                self.doPing(*args, **kwargs)
            elif event == 'datagram-received' and self.isGreeting(*args, **kwargs):
                self.state = 'GREETING'
                self.doAcceptGreeting(*args, **kwargs)
                self.doFinishRTT(*args, **kwargs)
                self.doStartRTT(*args, **kwargs)
                self.doGreeting(*args, **kwargs)
            elif event == 'datagram-received' and self.isPing(*args, **kwargs):
                self.state = 'GREETING'
                self.doAcceptPing(*args, **kwargs)
                self.doStartRTT(*args, **kwargs)
                self.doGreeting(*args, **kwargs)
            elif event == 'shutdown' or event == 'timer-20sec':
                self.state = 'CLOSED'
                self.doErrMsg(event,self.msg('MSG_3', *args, **kwargs))
                self.doClosePendingFiles(*args, **kwargs)
                self.doNotifyDisconnected(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---GREETING---
        elif self.state == 'GREETING':
            if event == 'timer-1sec':
                self.doStartRTT(*args, **kwargs)
                self.doGreeting(*args, **kwargs)
            elif event == 'shutdown' or event == 'timer-30sec':
                self.state = 'CLOSED'
                self.doErrMsg(event,self.msg('MSG_2', *args, **kwargs))
                self.doClosePendingFiles(*args, **kwargs)
                self.doNotifyDisconnected(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'datagram-received' and self.isAlive(*args, **kwargs):
                self.state = 'CONNECTED'
                self.doAcceptAlive(*args, **kwargs)
                self.doFinishAllRTTs(*args, **kwargs)
                self.doNotifyConnected(*args, **kwargs)
                self.doCheckPendingFiles(*args, **kwargs)
                self.doAlive(*args, **kwargs)
            elif event == 'datagram-received' and self.isPing(*args, **kwargs):
                self.doAcceptPing(*args, **kwargs)
                self.doStartRTT(*args, **kwargs)
                self.doGreeting(*args, **kwargs)
            elif event == 'datagram-received' and self.isGreeting(*args, **kwargs):
                self.doAcceptGreeting(*args, **kwargs)
                self.doFinishRTT(*args, **kwargs)
                self.doAlive(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def isPayloadData(self, *args, **kwargs):
        """
        Condition method.
        """
        command = args[0][0][0]
        return (command == udp.CMD_DATA or command == udp.CMD_ACK)

    def isPing(self, *args, **kwargs):
        """
        Condition method.
        """
        command = args[0][0][0]
        return (command == udp.CMD_PING)

    def isGreeting(self, *args, **kwargs):
        """
        Condition method.
        """
        command = args[0][0][0]
        return (command == udp.CMD_GREETING)

    def isAlive(self, *args, **kwargs):
        """
        Condition method.
        """
        command = args[0][0][0]
        return (command == udp.CMD_ALIVE)

#    def isGreetingOrAlive(self, *args, **kwargs):
#        """
#        Condition method.
#        """
#        command = arg[0][0]
#        return ( command == udp.CMD_ALIVE or command == udp.CMD_GREETING)

    def isSessionActive(self, *args, **kwargs):
        """
        Condition method.
        """
        return time.time() - self.last_datagram_received_time < 20

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        # self.listen_port, self.my_id, self.my_address = arg

    def doPing(self, *args, **kwargs):
        """
        Action method.
        """
#        if udp_stream._Debug:
#            if not (self.peer_address.count('37.18.255.42') or self.peer_address.count('37.18.255.38')):
#                return
        # rtt_id_out = self._rtt_start('PING')
        udp.send_command(
            self.node.listen_port,
            udp.CMD_PING,
            strng.to_bin(self.my_rtt_id),
            self.peer_address,
        )
        # # print 'doPing', self.my_rtt_id
        self.my_rtt_id = '0'

    def doGreeting(self, *args, **kwargs):
        """
        Action method.
        """
        # rtt_id_out = self._rtt_start('GREETING')
        payload = "%s %s %s %s" % (
            str(self.node.my_id), str(self.node.my_idurl),
            str(self.peer_rtt_id), str(self.my_rtt_id),)
        udp.send_command(
            self.node.listen_port,
            udp.CMD_GREETING,
            strng.to_bin(payload),
            self.peer_address)
        # print 'doGreeting', self.peer_rtt_id, self.my_rtt_id
        self.peer_rtt_id = '0'
        self.my_rtt_id = '0'

    def doAlive(self, *args, **kwargs):
        """
        Action method.
        """
        udp.send_command(
            self.node.listen_port,
            udp.CMD_ALIVE,
            strng.to_bin(self.peer_rtt_id),
            self.peer_address)
        # print 'doAlive', self.peer_rtt_id
        self.peer_rtt_id = '0'

    def doAcceptPing(self, *args, **kwargs):
        """
        Action method.
        """
        address, command, payload = self._dispatch_datagram(args[0])
        self.peer_rtt_id = payload.strip()
        # print 'doAcceptPing', self.peer_rtt_id

    def doAcceptGreeting(self, *args, **kwargs):
        """
        Action method.
        """
        address, command, payload = self._dispatch_datagram(args[0])
        parts = payload.split(' ')
        try:
            new_peer_id = parts[0]
            new_peer_idurl = parts[1]
            if len(parts) >= 4:
                self.peer_rtt_id = parts[3]
            else:
                self.peer_rtt_id = '0'
            if len(parts) >= 3:
                self.my_rtt_id = parts[2]
            else:
                self.my_rtt_id = '0'
        except:
            lg.exc()
            return
        # print 'doAcceptGreeting', self.peer_rtt_id, self.my_rtt_id
        # self._rtt_finish(rtt_id_in)
        # rtt_id_out = self._rtt_start('ALIVE')
        # udp.send_command(self.node.listen_port, udp.CMD_ALIVE, '', self.peer_address)
        first_greeting = False
        if self.peer_id:
            if new_peer_id != self.peer_id:
                lg.warn(
                    'session: %s,  peer_id from GREETING is different: %s' %
                    (self, new_peer_id))
        else:
            lg.out(
                _DebugLevel,
                'udp_session.doAcceptGreeting detected peer id : %s for session %s' %
                (new_peer_id,
                 self.peer_address))
            self.peer_id = new_peer_id
            self.name = 'udp_session[%s:%d:%s]' % (
                self.peer_address[0], self.peer_address[1], str(self.peer_id))
            first_greeting = True
            try:
                sessions_by_peer_id()[self.peer_id].append(self)
            except:
                sessions_by_peer_id()[self.peer_id] = [self, ]
        if self.peer_idurl:
            if new_peer_idurl != self.peer_idurl:
                lg.warn(
                    'session: %s,  peer_idurl from GREETING is different: %s' %
                    (self, new_peer_idurl))
        else:
            if _Debug:
                lg.out(
                    _DebugLevel,
                    'udp_session.doAcceptGreeting detected peer idurl : %s for session %s' %
                    (new_peer_idurl,
                     self.peer_address))
            self.peer_idurl = new_peer_idurl
            first_greeting = True
        if first_greeting:
            for s in sessions().values():
                if self.id == s.id:
                    continue
                if self.peer_id == s.peer_id:
                    lg.warn(
                        'got GREETING from another address, close session %s' %
                        s)
                    s.automat('shutdown')
                    continue
                if self.peer_idurl == s.peer_idurl:
                    lg.warn(
                        'got GREETING from another idurl, close session %s' %
                        s)
                    s.automat('shutdown')
                    continue

    def doAcceptAlive(self, *args, **kwargs):
        """
        Action method.
        """
        address, command, payload = self._dispatch_datagram(args[0])
        self.my_rtt_id = payload.strip()
        # print 'doAcceptAlive', self.my_rtt_id

    def doReceiveData(self, *args, **kwargs):
        """
        Action method.
        """
        self.last_datagram_received_time = time.time()
        try:
            datagram, address = args[0]
            command, payload = datagram
        except:
            return
        assert address == self.peer_address
        self.bytes_received += len(payload)
        if command == udp.CMD_DATA:
            self.file_queue.on_received_data_packet(payload)
        elif command == udp.CMD_ACK:
            self.file_queue.on_received_ack_packet(payload)
#        elif command == udp.CMD_PING:
#            pass
#        elif command == udp.CMD_ALIVE:
#            pass
#        elif command == udp.CMD_GREETING:
#            pass

    def doNotifyConnected(self, *args, **kwargs):
        """
        Action method.
        """
        # # print 'CONNECTED!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!'

    def doNotifyDisconnected(self, *args, **kwargs):
        """
        Action method.
        """
        # # print 'DISCONNECTED!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!'

    def doCheckPendingFiles(self, *args, **kwargs):
        """
        Action method.
        """
        global _PendingOutboxFiles
        i = 0
        outgoings = 0
        # print 'doCheckPendingFiles', self.peer_id, len(_PendingOutboxFiles)
        while i < len(_PendingOutboxFiles):
            filename, host, description, result_defer, keep_alive, tm = _PendingOutboxFiles[i]
            # print filename, host, description,
            if host == self.peer_id:
                outgoings += 1
                # small trick to speed up service packets - they have a high
                # priority
                if description.startswith(
                        'Identity') or description.startswith('Ack'):
                    self.file_queue.insert_outbox_file(
                        filename, description, result_defer, keep_alive)
                else:
                    self.file_queue.append_outbox_file(
                        filename, description, result_defer, keep_alive)
                _PendingOutboxFiles.pop(i)
                # print 'pop'
            else:
                # _PendingOutboxFiles.insert(i, (filename, host, description, result_defer, keep_alive, tm))
                i += 1
                # print 'skip'
        # print len(_PendingOutboxFiles)
        if outgoings > 0:
            reactor.callLater(0, process_sessions)  # @UndefinedVariable

    def doClosePendingFiles(self, *args, **kwargs):
        """
        Action method.
        """
        report_and_remove_pending_outbox_files_to_host(
            self.peer_id, self.error_message)
        self.file_queue.report_failed_inbox_files(self.error_message)
        self.file_queue.report_failed_outbox_files(self.error_message)
        self.file_queue.report_failed_outbox_queue(self.error_message)

    def doStartRTT(self, *args, **kwargs):
        """
        Action method.
        """
        self.my_rtt_id = self._rtt_start(self.state)

    def doFinishRTT(self, *args, **kwargs):
        """
        Action method.
        """
        self._rtt_finish(self.my_rtt_id)
        self.my_rtt_id = '0'

    def doFinishAllRTTs(self, *args, **kwargs):
        """
        Action method.
        """
        self._rtt_finish(self.my_rtt_id)
        self.my_rtt_id = '0'
        to_remove = []
        good_rtts = {}
        min_rtt = sys.float_info.max
        for rtt_id in self.rtts.keys():
            if self.rtts[rtt_id][1] == -1:
                to_remove.append(rtt_id)
            else:
                rtt = self.rtts[rtt_id][1] - self.rtts[rtt_id][0]
                if rtt < min_rtt:
                    min_rtt = rtt
                good_rtts[rtt_id] = rtt
        self.min_rtt = min_rtt
        for rtt_id in to_remove:
            # print 'doFinishAllRTTs closed', rtt_id
            del self.rtts[rtt_id]
            lg.out(
                _DebugLevel,
                'udp_session.doFinishAllRTTs: %r' %
                good_rtts)  # print self.rtts.keys()

    def doErrMsg(self, event, *args, **kwargs):
        """
        Action method.
        """
        if event.count('shutdown'):
            self.error_message = 'session has been closed'
        else:
            self.error_message = args[0]

    def doDestroyMe(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'udp_session.doDestroyMe %s' % self)
        self.file_queue.close()
        self.file_queue = None
        self.node = None
        sessions().pop(self.id)
        sessions_by_peer_address()[self.peer_address].remove(self)
        if len(sessions_by_peer_address()[self.peer_address]) == 0:
            sessions_by_peer_address().pop(self.peer_address)
        if self.peer_id in list(sessions_by_peer_id().keys()):
            sessions_by_peer_id()[self.peer_id].remove(self)
            if len(sessions_by_peer_id()[self.peer_id]) == 0:
                sessions_by_peer_id().pop(self.peer_id)
        self.destroy()

    def _dispatch_datagram(self, *args, **kwargs):
        self.last_datagram_received_time = time.time()
        try:
            datagram, address = args[0]
            command, payload = datagram
        except:
            lg.exc()
            return None, None, None
        assert address == self.peer_address
        return address, command, payload

    def _rtt_start(self, name):
        i = 0
        while name + str(i) in list(self.rtts.keys()):
            i += 1
        new_rtt_id = name + str(i)
        self.rtts[new_rtt_id] = [time.time(), -1]
        #     lg.out(_DebugLevel, 'udp_session._rtt_start added new RTT %s' % new_rtt_id)
        if len(self.rtts) > 10:
            oldest_rtt_moment = time.time()
            oldest_rtt_id = None
            for rtt_id in self.rtts.keys():
                rtt_data = self.rtts[rtt_id]
                if rtt_data[0] < oldest_rtt_moment:
                    oldest_rtt_moment = rtt_data[1]
                    oldest_rtt_id = rtt_id
            if oldest_rtt_id:
                # rtt = self.rtts[oldest_rtt_id][1] - self.rtts[oldest_rtt_id][0]
                del self.rtts[oldest_rtt_id]
                #     lg.out(_DebugLevel, 'udp_session._rtt_start removed oldest RTT %s  %r' % (
                #     oldest_rtt_id, rtt))
        while len(self.rtts) > 10:
            i = self.rtts.popitem()
            #     lg.out(_DebugLevel, 'udp_session._rtt_finish removed one extra item : %r' % str(i))
        # print 'rtt start', new_rtt_id, self.peer_id
        return new_rtt_id

    def _rtt_finish(self, rtt_id_in):
        # print 'rtt finish', rtt_id_in, self.peer_id
        if rtt_id_in == '0' or rtt_id_in not in self.rtts:
            return
#             or rtt_id_in not in self.rtts:
#            for rtt_id in self.rtts.keys():
#                if self.rtts[rtt_id][1] == -1:
#                    rtt = self.rtts[rtt_id][1] - self.rtts[rtt_id][0]
#                    del self.rtts[rtt_id]
#                        lg.out(_DebugLevel, 'udp_session._rtt_finish removed not finished RTT %s:%r' % (
#                        rtt_id, rtt))
#                    return
#            lg.warn('rtt %s not found in %s' % (rtt_id_in, self))
#            return
        self.rtts[rtt_id_in][1] = time.time()
        rtt = self.rtts[rtt_id_in][1] - self.rtts[rtt_id_in][0]
        if _Debug:
            lg.out(
                _DebugLevel, 'udp_session._rtt_finish registered RTT %s  %r' %
                (rtt_id_in, rtt))
