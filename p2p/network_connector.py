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

    <a href="http://bitpie.net/automats/network_connector/network_connector.png" target="_blank">
    <img src="http://bitpie.net/automats/network_connector/network_connector.png" style="max-width:100%;">
    </a>
    
The ``network_connector()`` machine is needed to monitor status of the Internet connection.

It will periodically check for incoming traffic and start STUN discovery procedure 
to detect connection status and possible external IP changes.

If BitPie.NET get disconnected it will ping "http://google.com" to know what is going on.


EVENTS:
    * :red:`all-transports-ready`
    * :red:`connection-done`
    * :red:`got-network-info`
    * :red:`init`
    * :red:`internet-failed`
    * :red:`internet-success`
    * :red:`network-down`
    * :red:`network-up`
    * :red:`reconnect`
    * :red:`timer-1hour`
    * :red:`timer-20sec`
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

from logs import lg

from lib.automat import Automat
from lib import automats
from lib import bpio
from lib import net_misc
from lib import settings
from lib import misc

from transport import gate
from dht import dht_service
from lib import udp
from stun import stun_server
from stun import stun_client

from userid import id_server

import p2p_connector
import shutdowner
import tray_icon
import run_upnpc

#------------------------------------------------------------------------------ 

_NetworkConnector = None
_CounterSuccessConnections = 0
_CounterFailedConnections = 0
_LastSuccessConnectionTime = 0
_TransportsInitialization = []
_TransportsStarting = []
_TransportsStopping = []

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


class NetworkConnector(Automat):
    """
    Class to monitor Internet connection and reconnect when needed.  
    """
    
    timers = {
        'timer-1hour': (3600, ['DISCONNECTED']),
        'timer-5sec': (5.0, ['DISCONNECTED','CONNECTED']),
        'timer-20sec': (20.0, ['GATE_INIT']),
        }

    fast = False
    
    def init(self):
        self.last_upnp_time = 0
        self.last_reconnect_time = 0
        self.last_internet_state = 'disconnected'

    def state_changed(self, oldstate, newstate, event, arg):
        automats.set_global_state('NETWORK ' + newstate)
        p2p_connector.A('network_connector.state', newstate)
        tray_icon.state_changed(self.state, p2p_connector.A().state)

    def A(self, event, arg):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init' :
                self.state = 'GATE_INIT'
                self.doInitGate(arg)
        #---UPNP---
        elif self.state == 'UPNP':
            if event == 'upnp-done' :
                self.state = 'CONNECTED'
                stun_client.A('start')
            elif event == 'reconnect' :
                self.Reset=True
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
                self.state = 'CONNECTED'
                stun_client.A('start')
        #---DOWN---
        elif self.state == 'DOWN':
            if event == 'network-down' :
                self.state = 'NETWORK?'
                self.doCheckNetworkInterfaces(arg)
        #---GATE_INIT---
        elif self.state == 'GATE_INIT':
            if event == 'timer-20sec' or event == 'all-transports-ready' :
                self.state = 'UP'
                self.doSetUp(arg)
                self.Disconnects=0
                self.Reset=False

    def isNeedUPNP(self, arg):
        return settings.enableUPNP() and time.time() - self.last_upnp_time < 60*60

    def isConnectionAlive(self, arg):
        if time.time() - udp.get_last_datagram_time() < 60:
            if settings.enableUDP() and settings.enableUDPreceiving():
                return True
        if time.time() - gate.last_inbox_time() < 60:
            return True
        transport_states = map(lambda t: t.state, gate.transports().values())
        if 'LISTENING' in transport_states:
            return True
        if 'STARTING' in transport_states:
            return True
        return False

#        global _CounterSuccessConnections
#        global _CounterFailedConnections
#        global _LastSuccessConnectionTime
#        # if no info yet - we think positive 
#        if _CounterSuccessConnections == 0 and _CounterFailedConnections == 0:
#            return True
#        # if we have only 3 or less failed reports - hope no problems yet 
#        if _CounterFailedConnections <= 3:
#            return True
#        # at least one success report - the connection should be fine
#        if _CounterSuccessConnections >= 1:
#            return True
#        # no success connections after last "drop counters", 
#        # but last success connection was not so far 
#        if time.time() - _LastSuccessConnectionTime < 60 * 5:
#            return True
#        # more success than failed - connection is not failed for sure
#        if _CounterSuccessConnections > _CounterFailedConnections:
#            return True
#        lg.out(6, 'network_connector.isConnectionAlive    %d/%d' % (_CounterSuccessConnections, _CounterFailedConnections) )
#        return False

    def isNetworkActive(self, arg):
        return len(arg) > 0
    
    def isCurrentInterfaceActive(self, arg):
        # Not sure about external IP, because if we have white IP it is the same to local IP
        return ( misc.readLocalIP() in arg ) or ( misc.readExternalIP() in arg ) 

    def isTimePassed(self, arg):
        return time.time() - self.last_reconnect_time < 15

    def doInitGate(self, arg):
        """
        Action method.
        """
        global _TransportsInitialization
        _TransportsInitialization = gate.init(nw_connector=self)

    def doSetUp(self, arg):
        lg.out(6, 'network_connector.doSetUp')
        # net_misc.SetConnectionDoneCallbackFunc(ConnectionDoneCallback)
        # net_misc.SetConnectionFailedCallbackFunc(ConnectionFailedCallback)
        udp_port = int(settings.getUDPPort())
        if not udp.proto(udp_port):
            udp.listen(udp_port)
        stun_server.A('start', udp_port) 
        if settings.enableIdServer():       
            id_server.A('start', (settings.getIdServerWebPort(), 
                                  settings.getIdServerTCPPort()))  
        dht_service.connect()
        global _TransportsStarting
        _TransportsStarting = gate.start()
        if len(_TransportsStarting) == 0:
            self.automat('network-up')

    def doSetDown(self, arg):
        """
        """
        lg.out(6, 'network_connector.doSetDown')
        dht_service.disconnect()
        stun_server.A('stop')
        if settings.enableIdServer():
            id_server.A('stop')
        global _TransportsStopping    
        _TransportsStopping = gate.stop()
        if len(_TransportsStopping) == 0:
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
        lg.out(4, 'network_connector.doCheckNetworkInterfaces')
        # TODO
        # self.automat('got-network-info', [])
        start_time = time.time()
        if bpio.Linux():
            def _call():
                return net_misc.getNetworkInterfaces()
            def _done(result, start_time):
                lg.out(4, 'network_connector.doCheckNetworkInterfaces._done: %s in %d seconds' % (str(result), time.time()- start_time))
                self.automat('got-network-info', result)
            d = threads.deferToThread(_call)
            d.addBoth(_done, start_time)
        else:
            ips = net_misc.getNetworkInterfaces()
            lg.out(4, 'network_connector.doCheckNetworkInterfaces DONE: %s in %d seconds' % (str(ips), time.time()- start_time))
            self.automat('got-network-info', ips)

    def doRememberTime(self, arg):
        self.last_reconnect_time = time.time()
    
    def on_network_transport_state_changed(self, proto, oldstate, newstate):
        global _TransportsInitialization
        global _TransportsStarting
        global _TransportsStopping
        lg.out(6, 'network_connector.on_network_transport_state_changed %s : %s->%s network_connector state is %s' % (
            proto, oldstate, newstate, A().state))
        # print _TransportsInitialization, _TransportsStarting, _TransportsStopping
        if A().state == 'GATE_INIT':
            if newstate in ['STARTING', 'OFFLINE',]:
                _TransportsInitialization.remove(proto)
                if len(_TransportsInitialization) == 0:
                    A('all-transports-ready')                
        elif A().state == 'UP':
            if newstate in ['LISTENING', 'OFFLINE',]:
                _TransportsStarting.remove(proto)
                if len(_TransportsStarting) == 0:
                    A('network-up')
        elif A().state == 'DOWN':
            if newstate == 'OFFLINE':
                _TransportsStopping.remove(proto)
                if len(_TransportsStopping) == 0:
                    A('network-down')
        # print _TransportsInitialization, _TransportsStarting, _TransportsStopping
    

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


def ConnectionDoneCallback(param, proto, info):
    global _CounterSuccessConnections 
    global _LastSuccessConnectionTime
    _CounterSuccessConnections += 1
    _LastSuccessConnectionTime = time.time()
    A('connection-done')
    
    
def ConnectionFailedCallback(param, proto, info):
    global _CounterFailedConnections
    if proto is not 'udp':
        _CounterFailedConnections += 1
    A('connection-failed')


def NetworkAddressChangedCallback(newaddress):
    """
    Called when user's IP were changed to start reconnect process.
    """
    A('reconnect')


#def NetworkTransportInitialized(proto):
#    """
#    """
#    global _TransportsInitialization
#    _TransportsInitialization.remove(proto)
#    if len(_TransportsInitialization) == 0:
#        A('all-transports-ready')




