#!/usr/bin/env python
# udp_node.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (udp_node.py) is part of BitDust Software.
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
.. module:: udp_node.

.. role:: red
BitDust udp_node() Automat


EVENTS:
    * :red:`connect`
    * :red:`datagram-received`
    * :red:`dht-read-result`
    * :red:`dht-write-failed`
    * :red:`dht-write-success`
    * :red:`disconnected`
    * :red:`go-offline`
    * :red:`go-online`
    * :red:`stun-failed`
    * :red:`stun-success`
    * :red:`timer-10sec`
    * :red:`timer-1sec`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

import time

from twisted.internet import reactor  # @UnresolvedImport

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from lib import udp
from lib import strng
from lib import misc

from main import settings

from dht import dht_service

from services import driver

from transport.udp import udp_connector
from transport.udp import udp_session

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 18

#------------------------------------------------------------------------------

_UDPNode = None

#------------------------------------------------------------------------------


def A(event=None, *args, **kwargs):
    """
    Access method to interact with the state machine.
    """
    global _UDPNode
    if _UDPNode is None:
        # set automat name and starting state here
        _UDPNode = UDPNode('udp_node', 'AT_STARTUP', 24)
    if event is not None:
        _UDPNode.automat(event, *args, **kwargs)
    return _UDPNode


def Destroy():
    """
    Destroy udp_node() automat and remove its instance from memory.
    """
    global _UDPNode
    if _UDPNode is None:
        return
    _UDPNode.destroy()
    del _UDPNode
    _UDPNode = None


class UDPNode(automat.Automat):
    """
    This class implements all the functionality of the ``udp_node()`` state
    machine.
    """

    fast = True

    timers = {
        'timer-1sec': (1.0, ['LISTEN']),
        'timer-10sec': (10.0, ['LISTEN']),
    }

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the
        state machine.
        """
        self.listen_port = None
        self.my_id = None
        self.my_address = None
        self.options = {}
        if driver.is_on('service_my_ip_port'):
            from stun import stun_client
            self.my_address = stun_client.A().getMyExternalAddress()
        self.notified = False
        self.IncomingPosition = -1

    def A(self, event, *args, **kwargs):
        #---LISTEN---
        if self.state == 'LISTEN':
            if event == 'datagram-received' and self.isPacketValid(*args, **kwargs) and not self.isStun(*args, **kwargs) and not self.isKnownPeer(*args, **kwargs):
                self.doStartNewSession(*args, **kwargs)
            elif event == 'go-offline':
                self.state = 'DISCONNECTING'
                self.doDisconnect(*args, **kwargs)
            elif event == 'connect' and self.isKnowMyAddress(*args, **kwargs) and not self.isKnownUser(*args, **kwargs):
                self.doStartNewConnector(*args, **kwargs)
            elif event == 'timer-10sec' and not self.isKnowMyAddress(*args, **kwargs):
                self.state = 'STUN'
                self.doStartStunClient(*args, **kwargs)
            elif event == 'timer-10sec' and self.isKnowMyAddress(*args, **kwargs):
                self.state = 'WRITE_MY_IP'
                self.doDHTWtiteMyAddress(*args, **kwargs)
            elif event == 'dht-read-result':
                self.doCheckAndStartNewSession(*args, **kwargs)
                self.doDHTRemoveMyIncoming(*args, **kwargs)
                self.doNotifyConnected(*args, **kwargs)
            elif event == 'connect' and not self.isKnowMyAddress(*args, **kwargs):
                self.state = 'STUN'
                self.doStartStunClient(*args, **kwargs)
            elif event == 'timer-1sec':
                self.doDHTReadNextIncoming(*args, **kwargs)
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'go-online' and not self.isKnowMyAddress(*args, **kwargs):
                self.state = 'STUN'
                self.GoOn = False
                self.doInit(*args, **kwargs)
                self.doStartStunClient(*args, **kwargs)
            elif event == 'go-online' and self.isKnowMyAddress(*args, **kwargs):
                self.state = 'WRITE_MY_IP'
                self.GoOn = False
                self.doInit(*args, **kwargs)
                self.doDHTWtiteMyAddress(*args, **kwargs)
        #---STUN---
        elif self.state == 'STUN':
            if event == 'stun-success':
                self.state = 'WRITE_MY_IP'
                self.doUpdateMyAddress(*args, **kwargs)
                self.doDHTWtiteMyAddress(*args, **kwargs)
            elif event == 'go-offline':
                self.state = 'DISCONNECTING'
                self.doDisconnect(*args, **kwargs)
            elif event == 'stun-failed':
                self.state = 'OFFLINE'
                self.doUpdateMyAddress(*args, **kwargs)
                self.doNotifyFailed(*args, **kwargs)
        #---OFFLINE---
        elif self.state == 'OFFLINE':
            if event == 'go-online':
                self.state = 'STUN'
                self.doStartStunClient(*args, **kwargs)
            elif event == 'go-offline':
                self.doNotifyDisconnected(*args, **kwargs)
        #---WRITE_MY_IP---
        elif self.state == 'WRITE_MY_IP':
            if event == 'go-offline':
                self.state = 'DISCONNECTING'
                self.doDisconnect(*args, **kwargs)
            elif event == 'connect' and not self.isKnowMyAddress(*args, **kwargs):
                self.state = 'STUN'
                self.doStartStunClient(*args, **kwargs)
            elif event == 'connect' and self.isKnowMyAddress(*args, **kwargs) and not self.isKnownUser(*args, **kwargs):
                self.doStartNewConnector(*args, **kwargs)
            elif event == 'dht-write-failed':
                self.state = 'OFFLINE'
                self.doNotifyFailed(*args, **kwargs)
            elif event == 'dht-write-success':
                self.state = 'LISTEN'
                self.doDHTReadNextIncoming(*args, **kwargs)
        #---DISCONNECTING---
        elif self.state == 'DISCONNECTING':
            if event == 'go-online':
                self.GoOn = True
            elif event == 'disconnected' and not self.GoOn:
                self.state = 'OFFLINE'
                self.doNotifyDisconnected(*args, **kwargs)
            elif event == 'disconnected' and self.GoOn:
                self.state = 'STUN'
                self.GoOn = False
                self.doNotifyDisconnected(*args, **kwargs)
                self.doStartStunClient(*args, **kwargs)
        return None

    def isKnownPeer(self, *args, **kwargs):
        """
        Condition method.
        """
        try:
            datagram, address = args[0]
            command, payload = datagram
        except:
            lg.exc()
            return False
        if driver.is_on('service_my_ip_port'):
            from stun import stun_client
            if address in stun_client.A().stun_servers:
                return True
        active_sessions = udp_session.get(address)
        return len(active_sessions) > 0

    def isKnownUser(self, *args, **kwargs):
        """
        Condition method.
        """
        user_id = args[0]
        if udp_session.get_by_peer_id(user_id):
            return True
        if udp_connector.get(user_id) is not None:
            return True
        if _Debug:
            lg.out(_DebugLevel, 'udp_node.isKnownUser %s not found in %s' % (
                user_id, list(udp_session.sessions_by_peer_id().keys())))
        return False

    def isKnowMyAddress(self, *args, **kwargs):
        """
        Condition method.
        """
        return self.my_address is not None

    def isPacketValid(self, *args, **kwargs):
        """
        Condition method.
        """
        try:
            datagram, address = args[0]
            command, payload = datagram
        except:
            return False
        return True

    def isStun(self, *args, **kwargs):
        """
        Condition method.
        """
        command = args[0][0][0]
        return command == udp.CMD_STUN

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        from transport.udp import udp_interface
        from transport.udp import udp_stream
        self.options = args[0]
        self.my_idurl = strng.to_text(self.options['idurl'])
        self.listen_port = int(self.options['udp_port'])
        self.my_id = udp_interface.idurl_to_id(self.my_idurl)
        udp.proto(self.listen_port).add_callback(self._datagram_received)
        bandoutlimit = settings.getBandOutLimit()
        bandinlimit = settings.getBandInLimit()
        udp_stream.set_global_output_limit_bytes_per_sec(bandoutlimit)
        udp_stream.set_global_input_limit_bytes_per_sec(bandinlimit)
        reactor.callLater(0, udp_session.process_sessions)  # @UndefinedVariable
        reactor.callLater(0, udp_stream.process_streams)  # @UndefinedVariable

    def doStartStunClient(self, *args, **kwargs):
        """
        Action method.
        """
        if driver.is_on('service_my_ip_port'):
            from stun import stun_client
            stun_client.A('start', self._stun_finished)
        else:
            self.automat('stun-success', ('unknown', misc.readExternalIP() or '127.0.0.1', settings.getUDPPort()))

    def doStartNewConnector(self, *args, **kwargs):
        """
        Action method.
        """
        c = udp_connector.create(self, *args, **kwargs)
        c.automat('start', (self.listen_port, self.my_id, self.my_address))

    def doStartNewSession(self, *args, **kwargs):
        """
        Action method.
        """
        try:
            datagram, address = args[0]
            command, payload = datagram
        except:
            lg.exc()
            return
        if _Debug:
            lg.out(
                _DebugLevel,
                'udp_node.doStartNewSession wants to start a new session with UNKNOWN peer at %s' %
                str(address))
        s = udp_session.create(self, address)
        s.automat('init')
        s.automat('datagram-received', *args, **kwargs)

    def doCheckAndStartNewSession(self, *args, **kwargs):
        """
        Action method.
        """
        if self.my_address is None:
            if _Debug:
                lg.out(
                    _DebugLevel,
                    'dp_node.doCheckAndStartNewSession SKIP because my_address is None')
            return
        incoming_str = args[0]
        if incoming_str is None:
            return
        try:
            incoming_user_id, incoming_user_address, _ = incoming_str.split(b' ')
            incoming_user_address = incoming_user_address.split(b':')
            incoming_user_address[1] = int(incoming_user_address[1])
            incoming_user_address = tuple(incoming_user_address)
        except:
            if _Debug:
                lg.out(_DebugLevel, '%r' % incoming_str)
            lg.exc()
            return
        active_sessions = udp_session.get(incoming_user_address)
        if active_sessions:
            if _Debug:
                lg.out(_DebugLevel, 'udp_node.doCheckAndStartNewSessions SKIP because found existing by address %s : %s' % (
                    incoming_user_address, active_sessions, ))
            return
        active_sessions = udp_session.get_by_peer_id(incoming_user_id)
        if active_sessions:
            if _Debug:
                lg.out(_DebugLevel, 'udp_node.doCheckAndStartNewSession SKIP because found existing by peer id %s : %s' % (
                    incoming_user_id, active_sessions, ))
            return
        if _Debug:
            lg.out(_DebugLevel, 'udp_node.doCheckAndStartNewSession wants to start a new session with incoming peer %s at %s' % (
                incoming_user_id, incoming_user_address))
        s = udp_session.create(self, incoming_user_address, incoming_user_id)
        s.automat('init')

    def doUpdateMyAddress(self, *args, **kwargs):
        """
        Action method.
        """
        try:
            typ, new_ip, new_port = args[0]
            new_addr = (new_ip, new_port)
        except:
            lg.exc()
            return
        if _Debug:
            lg.out(4, 'udp_node.doUpdateMyAddress typ=[%s]' % typ)
            if self.my_address:
                lg.out(4, '    old=%s new=%s' %
                       (str(self.my_address), str(new_addr)))
            else:
                lg.out(4, '    new=%s' % str(new_addr))
        self.my_address = new_addr

    def doDHTReadNextIncoming(self, *args, **kwargs):
        """
        Action method.
        """
        self.IncomingPosition += 1
        if self.IncomingPosition >= 10:
            self.IncomingPosition = 0
        key = self.my_id + ':incoming' + str(self.IncomingPosition)
        if _Debug:
            lg.out(_DebugLevel, 'udp_node.doDHTReadNextIncoming  key=%s' % key)
        d = dht_service.get_value(key)
        d.addCallback(self._got_my_incoming, key, self.IncomingPosition)
        d.addErrback(self._failed_my_incoming, key, self.IncomingPosition)

    def doDHTRemoveMyIncoming(self, *args, **kwargs):
        """
        Action method.
        """
        if args and args[0]:
            key = self.my_id + ':incoming' + str(self.IncomingPosition)
            dht_service.delete_key(key)

    def doDHTWtiteMyAddress(self, *args, **kwargs):
        """
        Action method.
        """
        d = dht_service.set_value(
            self.my_id + ':address',
            '%s:%d' % (strng.to_bin(self.my_address[0]), self.my_address[1]),
            age=int(time.time()),
        )
        d.addCallback(self._wrote_my_address)
        d.addErrback(lambda x: self.automat('dht-write-failed'))

    def doDisconnect(self, *args, **kwargs):
        """
        Action method.
        """
        from transport.udp import udp_stream
        lg.out(
            12, 'udp_node.doDisconnect going to close %d sessions and %d connectors' %
            (len(
                list(udp_session.sessions().values())), len(
                list(udp_connector.connectors().values()))))
        udp_stream.stop_process_streams()
        udp_session.stop_process_sessions()
        for s in udp_session.sessions().values():
            if _Debug:
                lg.out(
                    _DebugLevel,
                    'udp_node.doShutdown sends "shutdown" to %s' %
                    s)
            s.automat('shutdown')
        for c in udp_connector.connectors().values():
            c.automat('abort')
        self.automat('disconnected')

    def doNotifyDisconnected(self, *args, **kwargs):
        """
        Action method.
        """
        from transport.udp import udp_interface
        self.notified = False
        udp_interface.interface_disconnected(args[0])

    def doNotifyConnected(self, *args, **kwargs):
        """
        Action method.
        """
        from transport.udp import udp_interface
        if not self.notified:
            udp_interface.interface_receiving_started(self.my_id, self.options)
            self.notified = True
            if _Debug:
                lg.out(
                    4, 'udp_node.doNotifyConnected my host is %s' %
                    self.my_id)

    def doNotifyFailed(self, *args, **kwargs):
        """
        Action method.
        """
        from transport.udp import udp_interface
        udp_interface.interface_receiving_failed('state is %s' % self.state)

    def _datagram_received(self, datagram, address):
        """
        """
        # lg.out(18, '-> [%s] (%d bytes) from %s' % (command, len(payload), str(address)))
        active_sessions = udp_session.get(address)
        if active_sessions:
            for s in active_sessions:
                s.automat('datagram-received', (datagram, address))
        self.automat('datagram-received', (datagram, address))
        return False

    def _stun_finished(self, result, typ, ip, details):
        if result == 'stun-success' and typ == 'symmetric':
            result = 'stun-failed'
        self.automat(result, (typ, ip, details))

    def _got_my_address(self, value, key):
        if not isinstance(value, dict):
            lg.warn('can not read my address')
            self.automat('dht-write-failed')
            return
        try:
            addr = value[dht_service.key_to_hash(key)].strip('\n').strip()
        except:
            if _Debug:
                lg.out(
                    4,
                    'udp_node._got_my_address ERROR   wrong key in response: %r' %
                    value)
                lg.exc()
            self.automat('dht-write-failed')
            return
        if addr != '%s:%d' % (self.my_address[0], self.my_address[1]):
            if _Debug:
                lg.out(
                    4,
                    'udp_node._got_my_address ERROR   value not fit: %r' %
                    value)
            self.automat('dht-write-failed')
            return
        self.automat('dht-write-success')

    def _wrote_my_address(self, nodes):
        if len(nodes) == 0:
            self.automat('dht-write-failed')
            return
        key = self.my_id + ':address'
        d = dht_service.get_value(key)
        d.addCallback(self._got_my_address, key)
        d.addErrback(lambda x: self.automat('dht-write-failed'))

    def _got_my_incoming(self, value, key, position):
        if not isinstance(value, dict):
            if _Debug:
                lg.out(
                    _DebugLevel,
                    'udp_node._got_my_incoming no incoming at position: %d' %
                    position)
            self.automat('dht-read-result', None)
            return
        try:
            myincoming = value[dht_service.key_to_hash(key)]
        except:
            if _Debug:
                lg.out(
                    _DebugLevel,
                    'udp_node._got_my_incoming ERROR reading my incoming at position: %d\n%r' %
                    (position,
                     value))
            self.automat('dht-read-result', None)
            return
        if _Debug:
            lg.out(
                _DebugLevel,
                'udp_node._got_my_incoming found one: %r' %
                myincoming)
        self.automat('dht-read-result', myincoming)

    def _failed_my_incoming(self, err, key, position):
        if _Debug:
            lg.out(
                _DebugLevel,
                'udp_node._got_my_incoming incoming empty: %s' %
                str(position))
        self.automat('dht-read-result', None)
