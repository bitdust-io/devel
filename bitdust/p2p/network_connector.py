#!/usr/bin/env python
# network_connector.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (network_connector.py) is part of BitDust Software.
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
#
"""
.. module:: network_connector.

.. role:: red

.. raw:: html

    <a href="https://bitdust.io/automats/network_connector/network_connector.png" target="_blank">
    <img src="https://bitdust.io/automats/network_connector/network_connector.png" style="max-width:100%;">
    </a>

The ``network_connector()`` machine is needed to monitor status of the Internet connection.

It will periodically check for incoming traffic and start STUN discovery procedure
to detect connection status and possible external IP changes.

If BitDust get disconnected it will ping "Google dot com" (joke) to check what is going on.


EVENTS:
    * :red:`all-network-transports-disabled`
    * :red:`all-network-transports-ready`
    * :red:`check-reconnect`
    * :red:`connection-done`
    * :red:`gateway-is-not-started`
    * :red:`got-network-info`
    * :red:`init`
    * :red:`internet-failed`
    * :red:`internet-success`
    * :red:`network-down`
    * :red:`network-transport-state-changed`
    * :red:`network-transports-verified`
    * :red:`network-up`
    * :red:`reconnect`
    * :red:`timer-1hour`
    * :red:`timer-5sec`
    * :red:`upnp-done`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from six.moves import range

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 16

#------------------------------------------------------------------------------

import sys
import time

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in network_connector.py')

from twisted.internet import threads

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.lib import net_misc
from bitdust.lib import misc
from bitdust.lib import strng

from bitdust.services import driver

from bitdust.main import settings
from bitdust.main import shutdowner

from bitdust.p2p import p2p_stats

#------------------------------------------------------------------------------

_NetworkConnector = None
_CounterSuccessConnections = 0
_CounterFailedConnections = 0
_LastSuccessConnectionTime = 0

#------------------------------------------------------------------------------


def A(event=None, *args, **kwargs):
    """
    Access method to interact with the state machine.
    """
    global _NetworkConnector
    if event is None:
        return _NetworkConnector
    if _NetworkConnector is None:
        _NetworkConnector = NetworkConnector(
            name='network_connector',
            state='AT_STARTUP',
            debug_level=_DebugLevel,
            log_events=_Debug,
            log_transitions=_Debug,
        )
    if event is not None:
        _NetworkConnector.automat(event, *args, **kwargs)
    return _NetworkConnector


def Destroy():
    """
    Destroy network_connector() automat and remove its instance from memory.
    """
    global _NetworkConnector
    if _NetworkConnector is None:
        return
    _NetworkConnector.destroy()
    del _NetworkConnector
    _NetworkConnector = None


class NetworkConnector(automat.Automat):

    """
    Class to monitor Internet connection and reconnect when needed.
    """

    fast = False

    timers = {
        'timer-1hour': (3600, ['DISCONNECTED']),
        'timer-5sec': (30.0, ['DISCONNECTED', 'CONNECTED']),
    }

    managed_services = [
        'service_udp_datagrams',
        'service_service_entangled_dht',
        'service_ip_port_responder',
        'service_my_ip_port',
        'service_private_messages',
    ]

    def init(self):
        self.last_upnp_time = 0
        self.last_reconnect_time = 0
        self.last_internet_state = 'disconnected'
        self.last_bytes_in_counter = 0
        net_misc.SetConnectionDoneCallbackFunc(ConnectionDoneCallback)
        net_misc.SetConnectionFailedCallbackFunc(ConnectionFailedCallback)

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        if driver.is_on('service_p2p_hookups'):
            from bitdust.p2p import p2p_connector
            from bitdust.system import tray_icon
            p2p_connector.A('network_connector.state', newstate)
            tray_icon.state_changed(self.state, p2p_connector.A().state)
        if oldstate != 'CONNECTED' and newstate == 'CONNECTED':
            # TODO: redesign the state machine to cover that
            if self.last_bytes_in_counter < p2p_stats.get_total_bytes_in():
                lg.info('HELLO BITDUST WORLD!')
            else:
                lg.warn('no incoming traffic detected yet, potentially a signal that my node is offline')
            self.last_bytes_in_counter = p2p_stats.get_total_bytes_in()

    def A(self, event, *args, **kwargs):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'START_UP'
                self.Disconnects = 0
                self.Reset = False
                self.ColdStart = True
                self.doCheckNetworkInterfaces(*args, **kwargs)
        #---CONNECTED---
        elif self.state == 'CONNECTED':
            if event == 'reconnect' or (event == 'timer-5sec' and (self.Reset or not self.isConnectionAlive(*args, **kwargs))):
                self.state = 'DOWN'
                self.Disconnects = 0
                self.Reset = False
                self.doSetDown(*args, **kwargs)
            elif event == 'check-reconnect':
                self.state = 'TRANSPORTS?'
                self.doVerifyTransports(*args, **kwargs)
        #---NETWORK?---
        elif self.state == 'NETWORK?':
            if event == 'got-network-info' and not self.isNetworkActive(*args, **kwargs):
                self.state = 'DISCONNECTED'
            elif event == 'got-network-info' and self.isNetworkActive(*args, **kwargs) and self.isCurrentInterfaceActive(*args, **kwargs):
                self.state = 'INTERNET?'
                self.doPingGoogleDotCom(*args, **kwargs)
            elif event == 'got-network-info' and self.isNetworkActive(*args, **kwargs) and not self.isCurrentInterfaceActive(*args, **kwargs):
                self.state = 'UP'
                self.doSetUp(*args, **kwargs)
        #---INTERNET?---
        elif self.state == 'INTERNET?':
            if event == 'internet-failed':
                self.state = 'DISCONNECTED'
            elif event == 'internet-success':
                self.state = 'UP'
                self.doSetUp(*args, **kwargs)
        #---DISCONNECTED---
        elif self.state == 'DISCONNECTED':
            if event == 'reconnect' or event == 'check-reconnect' or event == 'timer-1hour' or (event == 'timer-5sec' and (self.Disconnects < 3 or self.Reset)) or (event == 'connection-done' and self.isTimePassed(*args, **kwargs)):
                self.state = 'DOWN'
                self.doRememberTime(*args, **kwargs)
                self.Disconnects += 1
                self.Reset = False
                self.doSetDown(*args, **kwargs)
        #---UP---
        elif self.state == 'UP':
            if not self.ColdStart and event == 'network-up' and not self.isNeedUPNP(*args, **kwargs):
                self.state = 'TRANSPORTS?'
                self.doStartNetworkTransports(*args, **kwargs)
            elif event == 'reconnect' or event == 'check-reconnect':
                self.Reset = True
            elif self.ColdStart and event == 'network-up':
                self.state = 'TRANSPORTS?'
                self.doColdStartNetworkTransports(*args, **kwargs)
                self.ColdStart = False
            elif not self.ColdStart and event == 'network-up' and self.isNeedUPNP(*args, **kwargs):
                self.state = 'UPNP'
                self.doUPNP(*args, **kwargs)
        #---DOWN---
        elif self.state == 'DOWN':
            if event == 'network-down':
                self.state = 'NETWORK?'
                self.doCheckNetworkInterfaces(*args, **kwargs)
        #---TRANSPORTS?---
        elif self.state == 'TRANSPORTS?':
            if event == 'reconnect' or event == 'check-reconnect':
                self.Reset = True
            elif not self.Reset and (
                (event == 'all-network-transports-ready' or event == 'network-transports-verified' or event == 'network-transport-state-changed') and (self.isAllReady(*args, **kwargs) and self.isAllListening(*args, **kwargs))
            ):
                self.state = 'CONNECTED'
            elif self.Reset and ((event == 'all-network-transports-ready' or event == 'network-transports-verified' or event == 'network-transport-state-changed') and self.isAllReady(*args, **kwargs)):
                self.state = 'DOWN'
                self.Reset = False
                self.Disconnects = 0
                self.doSetDown(*args, **kwargs)
            elif (event == 'all-network-transports-disabled' or event == 'gateway-is-not-started' or event == 'network-transport-state-changed') and (self.isAllReady(*args, **kwargs) and not self.isAllListening(*args, **kwargs)):
                self.state = 'DISCONNECTED'
        #---START_UP---
        elif self.state == 'START_UP':
            if event == 'got-network-info' and not self.isNetworkActive(*args, **kwargs):
                self.state = 'DISCONNECTED'
                self.Disconnects = 3
            elif event == 'reconnect' or event == 'check-reconnect':
                self.state = 'UP'
                self.doSetUp(*args, **kwargs)
        #---UPNP---
        elif self.state == 'UPNP':
            if event == 'upnp-done':
                self.state = 'TRANSPORTS?'
                self.doStartNetworkTransports(*args, **kwargs)
            elif event == 'reconnect' or event == 'check-reconnect':
                self.Reset = True
        return None

    def isNeedUPNP(self, *args, **kwargs):
        if not settings.enableUPNP():
            return False
        if driver.is_on('service_tcp_transport'):
            try:
                from bitdust.transport.tcp import tcp_node
                if int(tcp_node.get_internal_port()) != int(settings.getTCPPort()):
                    return True
            except:
                lg.exc()
                return False
        return time.time() - self.last_upnp_time > 60*60

    def isConnectionAlive(self, *args, **kwargs):
        # miss = 0
        if driver.is_on('service_udp_datagrams'):
            from bitdust.lib import udp
            if time.time() - udp.get_last_datagram_time() < 60:
                if settings.enableUDP() and settings.enableUDPreceiving():
                    return True
        # else:
        #     miss += 1
        if driver.is_on('service_gateway'):
            from bitdust.transport import gateway
            if time.time() - gateway.last_inbox_time() < 60:
                return True
            transport_states = [t.state for t in list(gateway.transports().values())]
            if 'LISTENING' in transport_states:
                return True
            if 'STARTING' in transport_states:
                return True
        # else:
        #     miss += 1
        # if miss >= 2:
        #     return True
        # return False ... still testing that approach
        return True

    def isNetworkActive(self, *args, **kwargs):
        ips = args[0]
        if _Debug:
            lg.args(_DebugLevel, ips=ips)
        return len(ips) > 0

    def isCurrentInterfaceActive(self, *args, **kwargs):
        # TODO: not sure about external IP
        # because if you have a white IP it should be the same as your local IP
        loc = strng.to_bin(misc.readLocalIP())
        ext = strng.to_bin(misc.readExternalIP())
        ips = args[0]
        if _Debug:
            lg.args(_DebugLevel, local=loc, external=ext)
        return (loc in ips) or (ext in ips)

    def isTimePassed(self, *args, **kwargs):
        return time.time() - self.last_reconnect_time < 15

    def isAllListening(self, *args, **kwargs):
        """
        Condition method.
        """
        if not driver.is_on('service_gateway'):
            if _Debug:
                lg.out(_DebugLevel, 'network_connector.isAllListening returning False : service_gateway is OFF')
            return False
        from bitdust.transport import gateway
        transports = list(gateway.transports().values())
        for t in transports:
            if t.state != 'LISTENING':
                if _Debug:
                    lg.out(_DebugLevel, 'network_connector.isAllListening returning False : transport %s is not LISTENING' % t)
                return False
        if _Debug:
            lg.out(_DebugLevel, 'network_connector.isAllListening returning True')
        return True

    def isAllReady(self, *args, **kwargs):
        """
        Condition method.
        """
        if not driver.is_on('service_gateway'):
            if _Debug:
                lg.out(_DebugLevel, 'network_connector.isAllReady returning False : service_gateway is OFF')
            return False
        LISTENING_count = 0
        OFFLINE_count = 0
        from bitdust.transport import gateway
        transports = list(gateway.transports().values())
        for t in transports:
            if t.state != 'OFFLINE' and t.state != 'LISTENING':
                if _Debug:
                    lg.out(_DebugLevel, 'network_connector.isAllReady returning False : transport %s is not READY yet' % t)
                return False
            if t.state == 'OFFLINE':
                OFFLINE_count += 1
            if t.state == 'LISTENING':
                LISTENING_count += 1
        if _Debug:
            lg.out(_DebugLevel, 'network_connector.isAllReady returning True : all transports READY')
            lg.out(_DebugLevel, '    OFFLINE transports:%d, LISTENING transports: %d' % (OFFLINE_count, LISTENING_count))
        return True

    def doSetUp(self, *args, **kwargs):
        for svc_name in self.managed_services:
            if driver.is_on(svc_name):
                if driver.is_suspended(svc_name):
                    if not driver.resume(svc_name):
                        lg.err('resuming network service %r failed' % svc_name)
                    else:
                        lg.info('network service resumed: %r' % svc_name)
                else:
                    lg.warn('network service %r was not suspended' % svc_name)
            else:
                lg.warn('network service %r was not ON' % svc_name)
        self.automat('network-up')

    def doSetDown(self, *args, **kwargs):
        for svc_name in [
            'service_gateway',
        ] + list(reversed(self.managed_services)):
            if driver.is_on(svc_name):
                if not driver.is_suspended(svc_name):
                    if not driver.suspend(svc_name):
                        lg.err('suspending network service %r failed' % svc_name)
                    else:
                        lg.info('network service suspended: %r' % svc_name)
                else:
                    lg.warn('network service %r already suspended' % svc_name)
            else:
                lg.warn('network service %r was not ON' % svc_name)
        self.automat('network-down')

    def doUPNP(self, *args, **kwargs):
        self.last_upnp_time = time.time()
        UpdateUPNP()

    def doPingGoogleDotCom(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'network_connector.doPingGoogleDotCom')
        net_misc.TestInternetConnection().addCallbacks(lambda x: self.automat('internet-success', 'connected'), lambda x: self.automat('internet-failed', 'disconnected'))

    def doCheckNetworkInterfaces(self, *args, **kwargs):
        start_time = time.time()
        #         if bpio.Linux():
        #             def _call():
        #                 return net_misc.getNetworkInterfaces()
        #
        #             def _done(result, start_time):
        #                 if _Debug:
        #                     lg.out(_DebugLevel, 'network_connector.doCheckNetworkInterfaces DONE: %s in %d seconds' % (str(result), time.time() - start_time))
        #                 if not result:
        #                     lg.err('no network interfaces found')
        #                 self.automat('got-network-info', result)
        #             d = threads.deferToThread(_call)
        #             d.addBoth(_done, start_time)
        #         else:
        ips = net_misc.getNetworkInterfaces()
        if _Debug:
            lg.args(_DebugLevel, result=ips, tm=(time.time() - start_time))
        if not ips:
            lg.err('no network interfaces found')
        self.automat('got-network-info', ips)

    def doRememberTime(self, *args, **kwargs):
        self.last_reconnect_time = time.time()

    def doStartNetworkTransports(self, *args, **kwargs):
        """
        Action method.
        """
        if not driver.is_on('service_gateway'):
            self.automat('gateway-is-not-started')
            return
        if not driver.is_suspended('service_gateway'):
            self.automat('all-network-transports-ready')
            return
        restarted_transports = driver.resume('service_gateway')
        if len(restarted_transports) == 0:
            self.automat('all-network-transports-ready')

    def doColdStartNetworkTransports(self, *args, **kwargs):
        """
        Action method.
        """
        if not driver.is_on('service_gateway'):
            self.automat('gateway-is-not-started')
            return
        if not driver.is_suspended('service_gateway'):
            self.automat('all-network-transports-ready')
            return
        restarted_transports = driver.resume('service_gateway', cold_start=True)
        if len(restarted_transports) == 0:
            self.automat('all-network-transports-ready')

    def doVerifyTransports(self, *args, **kwargs):
        """
        Action method.
        """
        if not driver.is_on('service_gateway'):
            self.automat('gateway-is-not-started')
            return
        from bitdust.transport import gateway

        def _transports_verified(all_results):
            if _Debug:
                lg.out(_DebugLevel, 'network_connector._transports_verified : %s' % str(all_results))
            order, all_results = all_results
            not_valid_count = 0
            restarts_count = 0
            if len(order) == 0:
                self.automat('network-transports-verified')
                return
            for proto in order:
                if not all_results[proto]:
                    not_valid_count += 1
            for priority in range(len(order)):
                proto = order[priority]
                if not all_results[proto]:
                    if _Debug:
                        lg.out(_DebugLevel, '    [%s] at position %d needs restart' % (proto, priority))
                    gateway.transport(proto).automat('restart')
                    restarts_count += 1
                    if not_valid_count > 1:  # this one failed, 2 other failed as well
                        self.automat('network-transports-verified')
                        return
                    continue
                if not_valid_count > 0:
                    if _Debug:
                        lg.out(_DebugLevel, '    skip %d transport [%s]' % (priority, proto))
                    if restarts_count == 0:
                        if _Debug:
                            lg.out(_DebugLevel, '    but no restarts and %d:[%s] is valid' % (priority, proto))
                        self.automat('network-transports-verified')
                    return
                if _Debug:
                    lg.out(_DebugLevel, '        [%s] at position %d is fine, skip other transports' % (proto, priority))
                self.automat('network-transports-verified')
                return

        gateway.verify().addCallback(_transports_verified)


#------------------------------------------------------------------------------


def UpdateUPNP():
    """
    Use ``lib.run_upnpc`` to configure UPnP device to create a port forwarding.
    """
    if _Debug:
        lg.out(_DebugLevel, 'network_connector.UpdateUPNP ')
    protos_need_upnp = set([
        'tcp',
    ])
    if not settings.enableTCP():
        # need to update only enabled protocols
        protos_need_upnp.discard('tcp')

    def _update_next_proto():
        if len(protos_need_upnp) == 0:
            lg.out(_DebugLevel, 'network_connector.update_upnp done, sending "upnp-done" event')
            A('upnp-done')
            return
        if _Debug:
            lg.out(_DebugLevel, 'network_connector.UpdateUPNP._update_next_proto ' + str(protos_need_upnp))
        proto = protos_need_upnp.pop()
        protos_need_upnp.add(proto)
        port = -1
        if proto == 'tcp':
            port = settings.getTCPPort()
        if port > 0:
            d = threads.deferToThread(_call_upnp, port)
            d.addCallback(_upnp_proto_done, proto)
        else:
            reactor.callLater(0, _upnp_proto_done, proto)  # @UndefinedVariable

    def _call_upnp(port):
        # start messing with upnp settings
        # success can be false if you're behind a router that doesn't support upnp
        # or if you are not behind a router at all and have an external ip address
        from bitdust.system import run_upnpc
        shutdowner.A('block')
        success, port = run_upnpc.update(port)
        shutdowner.A('unblock')
        return (success, port)

    def _upnp_proto_done(result, proto):
        if _Debug:
            lg.out(_DebugLevel, 'network_connector.UpdateUPNP._upnp_proto_done %s: %s' % (proto, str(result)))
        if result[0] == 'upnp-done':
            if proto == 'tcp':
                if str(settings.getTCPPort()) != str(result[1]).strip():
                    lg.out(_DebugLevel, '    !!!!!!!!!! created a new port mapping, TCP port were changed: %s -> %s' % (settings.getTCPPort(), str(result[1])))
                settings.setTCPPort(result[1])
        protos_need_upnp.discard(proto)
        reactor.callLater(0, _update_next_proto)  # @UndefinedVariable

    _update_next_proto()


#------------------------------------------------------------------------------


def ConnectionDoneCallback(param, proto, info):
    global _CounterSuccessConnections
    global _LastSuccessConnectionTime
    _CounterSuccessConnections += 1
    _LastSuccessConnectionTime = time.time()
    A('connection-done')


def ConnectionFailedCallback(param, proto, info):
    global _CounterFailedConnections
    if proto is not 'udp' and proto is not 'proxy':
        _CounterFailedConnections += 1
    A('connection-failed')
