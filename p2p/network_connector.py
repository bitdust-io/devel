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
    * :red:`connection-done`
    * :red:`got-network-info`
    * :red:`init`
    * :red:`internet-failed`
    * :red:`internet-success`
    * :red:`network-down`
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

from lib.automat import Automat
import lib.automats as automats

import lib.dhnio as dhnio
import lib.dhnnet as dhnnet
import lib.settings as settings
import lib.stun as stun

import userid.identity as identity
# from id import identity
import lib.misc as misc

# import lib.transport_control as transport_control
# if transport_control._TransportCSpaceEnable:
#     import lib.transport_cspace as transport_cspace

import transport.gate as gate
import dht.dht_service as dht_service
import lib.udp as udp
import stun.stun_server as stun_server
import stun.stun_client as stun_client

import userid.id_server as id_server

import p2p_connector
# import central_connector
import shutdowner

import dhnicon
import run_upnpc

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


class NetworkConnector(Automat):
    """
    Class to monitor Internet connection and reconnect when needed.  
    """
    
    timers = {
        'timer-1hour': (3600, ['DISCONNECTED']),
        'timer-5sec': (5.0, ['DISCONNECTED','CONNECTED']),
        }

    fast = False
    last_upnp_time = 0
    last_reconnect_time = 0
    last_internet_state = 'disconnected'

    def state_changed(self, oldstate, newstate):
        automats.set_global_state('NETWORK ' + newstate)
        p2p_connector.A('network_connector.state', newstate)
        dhnicon.state_changed(self.state, p2p_connector.A().state)

    def A(self, event, arg):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init' :
                self.state = 'UP'
                self.doSetUp(arg)
                self.Disconnects=0
                self.Reset=False
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

    def isNeedUPNP(self, arg):
        return settings.enableUPNP() and time.time() - self.last_upnp_time < 60*60

    def isConnectionAlive(self, arg):
        if udp.get_last_datagram_time() < 5*60 and settings.enableDHTUDP():
            return True
        if gate.last_inbox_time() < 3*60:
            return True
        if 'receive' in gate.transport_states().values():
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
#        dhnio.Dprint(6, 'network_connector.isConnectionAlive    %d/%d' % (_CounterSuccessConnections, _CounterFailedConnections) )
#        return False

    def isNetworkActive(self, arg):
        return len(arg) > 0
    
    def isCurrentInterfaceActive(self, arg):
        # Not sure about external IP, because if we have white IP it is the same to local IP
        return ( misc.readLocalIP() in arg ) or ( misc.readExternalIP() in arg ) 

    def isTimePassed(self, arg):
        return time.time() - self.last_reconnect_time < 15

    def doSetUp(self, arg):
        dhnio.Dprint(6, 'network_connector.doSetUp')
        # dhnnet.SetConnectionDoneCallbackFunc(ConnectionDoneCallback)
        # dhnnet.SetConnectionFailedCallbackFunc(ConnectionFailedCallback)
        dhtudp_port = int(settings.getDHTUDPPort())
        if not udp.proto(dhtudp_port):
            udp.listen(dhtudp_port)
        stun_server.A('start', dhtudp_port) 
        if settings.enableIdServer():       
            id_server.A('start', (settings.getIdServerWebPort(), 
                                  settings.getIdServerTCPPort()))  
        dht_service.connect()
        gate.start().addCallback(
            lambda x: reactor.callLater(0, self.automat, 'network-up'))

    def doSetDown(self, arg):
        """
        """
        dhnio.Dprint(6, 'network_connector.doSetDown')
        shutlist = []
        dhtudp_port = int(settings.getDHTUDPPort())
        # d_udp = udp.close_all() # (dhtudp_port)
        # if d_udp:
        #     shutlist.append(d_udp)
        d_dht = dht_service.disconnect()
        if d_dht:
            shutlist.append(d_dht)
        d_gate = gate.stop()
        if d_gate:
            shutlist.append(d_gate)
        stun_server.A('stop')
        if settings.enableIdServer():
            id_server.A('stop')   
        DeferredList(shutlist).addCallback(
            lambda x: reactor.callLater(0, self.automat, 'network-down'))

    def doUPNP(self, arg):
        self.last_upnp_time = time.time()
        UpdateUPNP()

    def doPingGoogleDotCom(self, arg):
        """
        Action method.
        """
        dhnio.Dprint(4, 'network_connector.doPingGoogleDotCom')
        dhnnet.TestInternetConnection().addCallbacks(
            lambda x: self.automat('internet-success', 'connected'), 
            lambda x: self.automat('internet-failed', 'disconnected'))
            
    def doCheckNetworkInterfaces(self, arg):
        dhnio.Dprint(4, 'network_connector.doCheckNetworkInterfaces')
        # TODO
        # self.automat('got-network-info', [])
        start_time = time.time()
        if dhnio.Linux():
            def _call():
                return dhnnet.getNetworkInterfaces()
            def _done(result, start_time):
                dhnio.Dprint(4, 'network_connector.doCheckNetworkInterfaces._done: %s in %d seconds' % (str(result), time.time()- start_time))
                self.automat('got-network-info', result)
            d = threads.deferToThread(_call)
            d.addBoth(_done, start_time)
        else:
            ips = dhnnet.getNetworkInterfaces()
            dhnio.Dprint(4, 'network_connector.doCheckNetworkInterfaces DONE: %s in %d seconds' % (str(ips), time.time()- start_time))
            self.automat('got-network-info', ips)

    def doRememberTime(self, arg):
        self.last_reconnect_time = time.time()

#------------------------------------------------------------------------------ 


def UpdateUPNP():
    """
    Use ``lib.run_upnpc`` to configure UPnP device to create a port forwarding.
    """
    #global _UpnpResult
    dhnio.Dprint(8, 'network_connector.UpdateUPNP ')

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
            #dhnio.Dprint(4, 'network_connector.update_upnp done: ' + str(_UpnpResult))
            A('upnp-done')
            return
        dhnio.Dprint(14, 'network_connector.UpdateUPNP._update_next_proto ' + str(protos_need_upnp))
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
        dhnio.Dprint(4, 'network_connector.UpdateUPNP._upnp_proto_done %s: %s' % (proto, str(result)))
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



