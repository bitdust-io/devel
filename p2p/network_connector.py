#!/usr/bin/env python
#network_connector.py
#
# <<<COPYRIGHT>>>
#
#
#
#
#

"""
.. module:: network_connector
.. role:: red

.. raw:: html

    <a href="http://bitdust.io/automats/network_connector/network_connector.png" target="_blank">
    <img src="http://bitdust.io/automats/network_connector/network_connector.png" style="max-width:100%;">
    </a>
    
The ``network_connector()`` machine is needed to monitor status of the Internet connection.

It will periodically check for incoming traffic and start STUN discovery procedure 
to detect connection status and possible external IP changes.

If BitDust get disconnected it will ping "http://google.com" to know what is going on.


EVENTS:
    * :red:`all-network-transports-disabled`
    * :red:`all-network-transports-ready`
    * :red:`connection-done`
    * :red:`gateway-is-not-started`
    * :red:`got-network-info`
    * :red:`init`
    * :red:`internet-failed`
    * :red:`internet-success`
    * :red:`network-down`
    * :red:`network-transport-state-changed`
    * :red:`network-up`
    * :red:`reconnect`
    * :red:`timer-1hour`
    * :red:`timer-5sec`
    * :red:`upnp-done`
    
"""

import os
import sys
import time

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in network_connector.py')

from twisted.internet.defer import Deferred, DeferredList
from twisted.internet.task import LoopingCall
from twisted.internet import threads

#------------------------------------------------------------------------------ 

from logs import lg

from automats import automat
from automats import global_state

from system import bpio
from system import run_upnpc

from lib import net_misc
from lib import misc

from services import driver

from main import settings
from main import shutdowner
from main import tray_icon

#------------------------------------------------------------------------------ 

_NetworkConnector = None
_CounterSuccessConnections = 0
_CounterFailedConnections = 0
_LastSuccessConnectionTime = 0

#------------------------------------------------------------------------------

def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """
    global _NetworkConnector
    if _NetworkConnector is None:
        _NetworkConnector = NetworkConnector('network_connector', 'AT_STARTUP', 4)
    if event is not None:
        _NetworkConnector.automat(event, arg)
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
    
    timers = {
        'timer-1hour': (3600, ['DISCONNECTED']),
        'timer-5sec': (5.0, ['DISCONNECTED','CONNECTED']),
        }

    def init(self):
        self.last_upnp_time = 0
        self.last_reconnect_time = 0
        self.last_internet_state = 'disconnected'
        net_misc.SetConnectionDoneCallbackFunc(ConnectionDoneCallback)
        net_misc.SetConnectionFailedCallbackFunc(ConnectionFailedCallback)

    def state_changed(self, oldstate, newstate, event, arg):
        global_state.set_global_state('NETWORK ' + newstate)
        # if driver.is_started('service_p2p_hookups'):
        #     import p2p_connector
        #     p2p_connector.A('network_connector.state', newstate)
        #     tray_icon.state_changed(self.state, p2p_connector.A().state)

    def A(self, event, arg):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init' :
                self.state = 'START_UP'
                self.Disconnects=0
                self.Reset=False
                self.doCheckNetworkInterfaces(arg)
        #---UPNP---
        elif self.state == 'UPNP':
            if event == 'reconnect' :
                self.Reset=True
            elif event == 'upnp-done' :
                self.state = 'TRANSPORTS?'
                self.doStartNetworkTransports(arg)
        #---CONNECTED---
        elif self.state == 'CONNECTED':
            if event == 'reconnect' or ( event == 'timer-5sec' and ( self.Reset or not self.isConnectionAlive(arg) ) ) :
                self.state = 'DOWN'
                self.Disconnects=0
                self.Reset=False
                self.doSetDown(arg)
        #---NETWORK?---
        elif self.state == 'NETWORK?':
            if event == 'got-network-info' and not self.isNetworkActive(arg) :
                self.state = 'DISCONNECTED'
            elif event == 'got-network-info' and self.isNetworkActive(arg) and self.isCurrentInterfaceActive(arg) :
                self.state = 'INTERNET?'
                self.doPingGoogleDotCom(arg)
            elif event == 'got-network-info' and self.isNetworkActive(arg) and not self.isCurrentInterfaceActive(arg) :
                self.state = 'UP'
                self.doSetUp(arg)
        #---INTERNET?---
        elif self.state == 'INTERNET?':
            if event == 'internet-failed' :
                self.state = 'DISCONNECTED'
            elif event == 'internet-success' :
                self.state = 'UP'
                self.doSetUp(arg)
        #---DISCONNECTED---
        elif self.state == 'DISCONNECTED':
            if event == 'reconnect' or event == 'timer-1hour' or ( event == 'timer-5sec' and ( self.Disconnects < 3 or self.Reset ) ) or ( event == 'connection-done' and self.isTimePassed(arg) ) :
                self.state = 'DOWN'
                self.doRememberTime(arg)
                self.Disconnects+=1
                self.Reset=False
                self.doSetDown(arg)
        #---UP---
        elif self.state == 'UP':
            if event == 'reconnect' :
                self.Reset=True
            elif event == 'network-up' and self.isNeedUPNP(arg) :
                self.state = 'UPNP'
                self.doUPNP(arg)
            elif event == 'network-up' and not self.isNeedUPNP(arg) :
                self.state = 'TRANSPORTS?'
                self.doStartNetworkTransports(arg)
        #---DOWN---
        elif self.state == 'DOWN':
            if event == 'network-down' :
                self.state = 'NETWORK?'
                self.doCheckNetworkInterfaces(arg)
        #---TRANSPORTS?---
        elif self.state == 'TRANSPORTS?':
            if event == 'reconnect' :
                self.Reset=True
            elif event == 'all-network-transports-disabled' or event == 'gateway-is-not-started' or ( event == 'network-transport-state-changed' and self.isAllTransportsFailed(arg) ) :
                self.state = 'DISCONNECTED'
            elif event == 'all-network-transports-ready' or ( event == 'network-transport-state-changed' and self.isAllTransportsReady(arg) ) :
                self.state = 'CONNECTED'
        #---START_UP---
        elif self.state == 'START_UP':
            if event == 'got-network-info' and not self.isNetworkActive(arg) :
                self.state = 'DISCONNECTED'
                self.Disconnects=3
            elif event == 'reconnect' :
                self.state = 'UP'
                self.doSetUp(arg)
        return None

    def isNeedUPNP(self, arg):
        return settings.enableUPNP() and time.time() - self.last_upnp_time < 60*60

    def isConnectionAlive(self, arg):
        # miss = 0
        if driver.is_started('service_udp_datagrams'):
            from lib import udp
            if time.time() - udp.get_last_datagram_time() < 60:
                if settings.enableUDP() and settings.enableUDPreceiving():
                    return True
        # else:
        #     miss += 1
        if driver.is_started('service_gateway'):
            from transport import gateway
            if time.time() - gateway.last_inbox_time() < 60:
                return True
            transport_states = map(lambda t: t.state, gateway.transports().values())
            if 'LISTENING' in transport_states:
                return True
            if 'STARTING' in transport_states:
                return True
        # else:
        #     miss += 1
        # if miss >= 2:
        #     return True 
        return False

    def isNetworkActive(self, arg):
        return len(arg) > 0
    
    def isCurrentInterfaceActive(self, arg):
        # I am not sure about external IP, 
        # because if you have a white IP it should be the same with your local IP
        return ( misc.readLocalIP() in arg ) or ( misc.readExternalIP() in arg ) 

    def isTimePassed(self, arg):
        return time.time() - self.last_reconnect_time < 15

    def isAllTransportsFailed(self, arg):
        """
        Condition method.
        """
        if not driver.is_started('service_gateway'):
            return True
        from transport import gateway
        transports = gateway.transports().values()
        for t in transports:
            if t.state != 'OFFLINE':
                return False
        return True

    def isAllTransportsReady(self, arg):
        """
        Condition method.
        """
        if not driver.is_started('service_gateway'):
            return False
        from transport import gateway
        transports = gateway.transports().values()
        for t in transports:
            if t.state != 'OFFLINE' and t.state != 'LISTENING':
                return False
        return True

    def doSetUp(self, arg):
        lg.out(6, 'network_connector.doSetUp')
        # if driver.is_started('service_identity_server'): 
        #     if settings.enableIdServer():       
        #         from userid import id_server
        #         id_server.A('start', (settings.getIdServerWebPort(), 
        #                               settings.getIdServerTCPPort()))
        if driver.is_started('service_service_entangled_dht'):
            from dht import dht_service
            dht_service.reconnect()
        if driver.is_started('service_ip_port_responder'):
            from stun import stun_server
            udp_port = int(settings.getUDPPort())
            stun_server.A('start', udp_port)
        if driver.is_started('service_my_ip_port'):
            from stun import stun_client
            stun_client.A().dropMyExternalAddress()
            stun_client.A('start')    
        if driver.is_started('service_private_messages'):
            from chat import nickname_holder
            nickname_holder.A('set', None)
        # if driver.is_started('service_gateway'):
        #     from transport import gateway
        #     gateway.start()
        self.automat('network-up')

    def doSetDown(self, arg):
        """
        """
        lg.out(6, 'network_connector.doSetDown')
        if driver.is_started('service_service_entangled_dht'):
            from dht import dht_service
            dht_service.disconnect()
        if driver.is_started('service_ip_port_responder'):
            from stun import stun_server
            stun_server.A('stop')
        # if driver.is_started('service_identity_server'): 
        #     if settings.enableIdServer():
        #         from userid import id_server
        #         id_server.A('stop')
        if driver.is_started('service_gateway'):
            from transport import gateway
            gateway.stop()
        # if driver.is_started('service_my_ip_port'):
        #     from stun import stun_client
        #     stun_client.A().drop...
        self.automat('network-down')

    def doUPNP(self, arg):
        self.last_upnp_time = time.time()
        UpdateUPNP()

    def doPingGoogleDotCom(self, arg):
        """
        Action method.
        """
        lg.out(4, 'network_connector.doPingGoogleDotCom')
        net_misc.TestInternetConnection().addCallbacks(
            lambda x: self.automat('internet-success', 'connected'), 
            lambda x: self.automat('internet-failed', 'disconnected'))
            
    def doCheckNetworkInterfaces(self, arg):
        # lg.out(4, 'network_connector.doCheckNetworkInterfaces')
        # TODO
        # self.automat('got-network-info', [])
        start_time = time.time()
        if bpio.Linux():
            def _call():
                return net_misc.getNetworkInterfaces()
            def _done(result, start_time):
                lg.out(4, 'network_connector.doCheckNetworkInterfaces DONE: %s in %d seconds' % (str(result), time.time()-start_time))
                self.automat('got-network-info', result)
            d = threads.deferToThread(_call)
            d.addBoth(_done, start_time)
        else:
            ips = net_misc.getNetworkInterfaces()
            lg.out(4, 'network_connector.doCheckNetworkInterfaces DONE: %s in %d seconds' % (str(ips), time.time()-start_time))
            self.automat('got-network-info', ips)

    def doRememberTime(self, arg):
        self.last_reconnect_time = time.time()

    def doStartNetworkTransports(self, arg):
        """
        Action method.
        """
        if not driver.is_started('service_gateway'):
            self.automat('gateway-is-not-started')
            return
        from transport import gateway
        # transports = gateway.transports().values()
        if len(gateway.start()) > 0:
            return
        # transports = gateway.transports().values()
        # if len(transports) == 0: 
        #     self.automat('all-network-transports-disabled')
        #     return
        self.automat('all-network-transports-ready')

#------------------------------------------------------------------------------ 

def UpdateUPNP():
    """
    Use ``lib.run_upnpc`` to configure UPnP device to create a port forwarding.
    """
    #global _UpnpResult
    lg.out(8, 'network_connector.UpdateUPNP ')

#    protos_need_upnp = set(['tcp', 'ssh', 'http'])
    protos_need_upnp = set(['tcp',])

    #we want to update only enabled protocols
    if not settings.enableTCP():
        protos_need_upnp.discard('tcp')
    # if not settings.enableSSH() or not transport_control._TransportSSHEnable:
    #     protos_need_upnp.discard('ssh')
    # if not settings.enableHTTPServer() or not transport_control._TransportHTTPEnable:
    #     protos_need_upnp.discard('http')

    def _update_next_proto():
        if len(protos_need_upnp) == 0:
            #out(4, 'network_connector.update_upnp done: ' + str(_UpnpResult))
            A('upnp-done')
            return
        lg.out(14, 'network_connector.UpdateUPNP._update_next_proto ' + str(protos_need_upnp))
        proto = protos_need_upnp.pop()
        protos_need_upnp.add(proto)
        if proto == 'tcp':
            port = settings.getTCPPort()
        # elif proto == 'ssh':
        #     port = settings.getSSHPort()
        # elif proto == 'http':
        #     port = settings.getHTTPPort()
        d = threads.deferToThread(_call_upnp, port)
        d.addCallback(_upnp_proto_done, proto)

    def _call_upnp(port):
        # start messing with upnp settings
        # success can be false if you're behind a router that doesn't support upnp
        # or if you are not behind a router at all and have an external ip address
        shutdowner.A('block')
        success, port = run_upnpc.update(port)
        shutdowner.A('unblock')
        return (success, port)

    def _upnp_proto_done(result, proto):
        lg.out(4, 'network_connector.UpdateUPNP._upnp_proto_done %s: %s' % (proto, str(result)))
        #_UpnpResult[proto] = result[0]
        #if _UpnpResult[proto] == 'upnp-done':
        if result[0] == 'upnp-done':
            if proto == 'tcp':
                settings.setTCPPort(result[1])
            # elif proto == 'ssh':
            #     settings.setSSHPort(result[1])
            # elif proto == 'http':
            #     settings.setHTTPPort(result[1])
        protos_need_upnp.discard(proto)
        reactor.callLater(0, _update_next_proto)

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


