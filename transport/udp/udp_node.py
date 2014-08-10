

"""
.. module:: udp_node
.. role:: red
BitPie.NET udp_node() Automat


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
        
"""

import time
import struct

from twisted.internet import reactor

from logs import lg

from lib import bpio
from lib import automat
from lib import udp
from lib import settings
from lib import misc

from stun import stun_client

from dht import dht_service

import udp_connector
import udp_session
import udp_interface
import udp_stream

#------------------------------------------------------------------------------ 

_UDPNode = None

#------------------------------------------------------------------------------ 

def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """
    global _UDPNode
    if _UDPNode is None:
        # set automat name and starting state here
        _UDPNode = UDPNode('udp_node', 'AT_STARTUP', 22)
    if event is not None:
        _UDPNode.automat(event, arg)
    return _UDPNode


class UDPNode(automat.Automat):
    """
    This class implements all the functionality of the ``udp_node()`` state machine.
    """

    fast = True

    timers = {
        'timer-10sec': (10.0, ['LISTEN']),
        }

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the state machine.
        """
        self.listen_port = None
        self.my_id = None
        self.my_address = None
        self.my_current_incomings = []
        self.notified = False
        
    def state_changed(self, oldstate, newstate):
        """
        """
        
    def A(self, event, arg):
        #---LISTEN---
        if self.state == 'LISTEN':
            if event == 'datagram-received' and self.isPacketValid(arg) and not self.isStun(arg) and not self.isKnownPeer(arg) :
                self.doStartNewSession(arg)
            elif event == 'go-offline' :
                self.state = 'DISCONNECTING'
                self.doDisconnect(arg)
            elif event == 'connect' and self.isKnowMyAddress(arg) and not self.isKnownUser(arg) :
                self.doStartNewConnector(arg)
            elif event == 'timer-10sec' and not self.isKnowMyAddress(arg) :
                self.state = 'STUN'
                self.doStartStunClient(arg)
            elif event == 'timer-10sec' and self.isKnowMyAddress(arg) :
                self.state = 'WRITE_MY_IP'
                self.doDHTWtiteMyAddress(arg)
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'go-online' :
                self.state = 'STUN'
                self.GoOn=False
                self.doInit(arg)
                self.doStartStunClient(arg)
        #---STUN---
        elif self.state == 'STUN':
            if event == 'stun-success' :
                self.state = 'WRITE_MY_IP'
                self.doUpdateMyAddress(arg)
                self.doDHTWtiteMyAddress(arg)
            elif event == 'go-offline' :
                self.state = 'DISCONNECTING'
                self.doDisconnect(arg)
            elif event == 'datagram-received' and self.isPacketValid(arg) and not self.isStun(arg) and not self.isKnownPeer(arg) :
                #self.doStartNewSession(arg)
                pass
            elif event == 'stun-failed' :
                self.state = 'OFFLINE'
                self.doUpdateMyAddress(arg)
                self.doNotifyFailed(arg)
        #---OFFLINE---
        elif self.state == 'OFFLINE':
            if event == 'go-online' :
                self.state = 'STUN'
                self.doStartStunClient(arg)
        #---DHT_READ---
        elif self.state == 'DHT_READ':
            if event == 'dht-read-result' :
                self.state = 'LISTEN'
                self.doCheckAndStartNewSessions(arg)
                self.doDHTRemoveMyIncomings(arg)
                self.doNotifyConnected(arg)
            elif event == 'go-offline' :
                self.state = 'DISCONNECTING'
                self.doDisconnect(arg)
            elif event == 'datagram-received' and self.isPacketValid(arg) and not self.isStun(arg) and not self.isKnownPeer(arg) :
                #self.doStartNewSession(arg)
                pass
            elif event == 'connect' and not self.isKnowMyAddress(arg) :
                self.state = 'STUN'
                self.doStartStunClient(arg)
            elif event == 'connect' and self.isKnowMyAddress(arg) and not self.isKnownUser(arg) :
                self.doStartNewConnector(arg)
        #---WRITE_MY_IP---
        elif self.state == 'WRITE_MY_IP':
            if event == 'dht-write-success' :
                self.state = 'DHT_READ'
                self.doDHTReadMyIncomings(arg)
            elif event == 'go-offline' :
                self.state = 'DISCONNECTING'
                self.doDisconnect(arg)
            elif event == 'datagram-received' and self.isPacketValid(arg) and not self.isStun(arg) and not self.isKnownPeer(arg) :
                #self.doStartNewSession(arg)
                pass
            elif event == 'connect' and not self.isKnowMyAddress(arg) :
                self.state = 'STUN'
                self.doStartStunClient(arg)
            elif event == 'connect' and self.isKnowMyAddress(arg) and not self.isKnownUser(arg) :
                self.doStartNewConnector(arg)
            elif event == 'dht-write-failed' :
                self.state = 'OFFLINE'
                self.doNotifyFailed(arg)
        #---DISCONNECTING---
        elif self.state == 'DISCONNECTING':
            if event == 'go-online' :
                self.GoOn=True
            elif event == 'disconnected' and not self.GoOn :
                self.state = 'OFFLINE'
                self.doNotifyDisconnected(arg)
            elif event == 'disconnected' and self.GoOn :
                self.state = 'STUN'
                self.GoOn=False
                self.doNotifyDisconnected(arg)
                self.doStartStunClient(arg)

    def isKnownPeer(self, arg):
        """
        Condition method.
        """
        try:
            datagram, address = arg
            command, payload = datagram
        except:
            lg.exc()
            return False
        if address == stun_client.A().peer_address:
            return True
        s = udp_session.get(address)
        return s is not None

    def isKnownUser(self, arg):
        """
        Condition method.
        """
        user_id = arg
        if udp_session.get_by_peer_id(user_id) is not None:
            return True
        if udp_connector.get(user_id) is not None:
            return True
        lg.out(18, 'udp_node.isKnownUser %s not found in %s' % (
            user_id, udp_session.sessions_by_peer_id().keys()))
        return False

    def isKnowMyAddress(self, arg):
        """
        Condition method.
        """
        return self.my_address is not None

    def isPacketValid(self, arg):
        """
        Condition method.
        """
        try:
            datagram, address = arg
            command, payload = datagram
        except:
            return False
        return True
        
    def isStun(self, arg):
        """
        Condition method.
        """
        command = arg[0][0]
        return command == udp.CMD_STUN

    def doInit(self, arg):
        """
        Action method.
        """
        options = arg
        self.my_idurl = options['idurl']
        self.listen_port = int(options['udp_port']) 
        self.my_id = udp_interface.idurl_to_id(self.my_idurl)
        udp.proto(self.listen_port).add_callback(self._datagram_received)
        bandoutlimit = settings.getBandOutLimit()
        if bandoutlimit == 0:
            bandoutlimit = 10 * 125000 # 1 Mbps = 125000 B/s ~ 122 KB/s
        udp_stream.set_global_limit_send_bytes_per_sec(bandoutlimit)
        # udp.proto(self.listen_port).set_command_filter_callback(udp_stream.command_received)
        reactor.callLater(0, udp_session.process_sessions)

    def doStartStunClient(self, arg):
        """
        Action method.
        """
        stun_client.A('start', (self.listen_port, self._stun_finished))

    def doStartNewConnector(self, arg):
        """
        Action method.
        """
        c = udp_connector.create(self, arg)
        c.automat('start', (self.listen_port, self.my_id, self.my_address))

    def doStartNewSession(self, arg):
        """
        Action method.
        """
        try:
            datagram, address = arg
            command, payload = datagram
        except:
            lg.exc()
            return
        lg.out(18, 'udp_node.doStartNewSession wants to start a new session with UNKNOWN peer at %s' % str(address))
        s = udp_session.create(self, address)
        s.automat('init')
        s.automat('datagram-received', arg)

    def doCheckAndStartNewSessions(self, arg):
        """
        Action method.
        """
        if self.my_address is None:
            lg.out(18, 'dp_node.doCheckAndStartNewSessions SKIP because my_address is None')
            return
        if type(arg) != list:
            raise Exception('Wrong type') 
        self.my_current_incomings = arg
        for incoming in self.my_current_incomings:
            try:
                incoming_user_id, incoming_user_address, time_placed = incoming.split(' ')
                incoming_user_address = incoming_user_address.split(':')
                incoming_user_address[1] = int(incoming_user_address[1])
                incoming_user_address = tuple(incoming_user_address)
            except:
                lg.exc()
                continue
            s = udp_session.get(incoming_user_address) 
            if s:
                lg.out(18, 'udp_node.doCheckAndStartNewSessions SKIP because found existing %s' % s)
                continue
            s = udp_session.get_by_peer_id(incoming_user_id)
            if s:
                lg.out(18, 'udp_node.doCheckAndStartNewSessions SKIP because found existing by peer id:%s %s' % (incoming_user_id, s))
                continue
            lg.out(18, 'udp_node.doCheckAndStartNewSessions wants to start a new session with incoming peer %s at %s' % (
                incoming_user_id, incoming_user_address))
            s = udp_session.create(self, incoming_user_address, incoming_user_id)
            s.automat('init')

    def doUpdateMyAddress(self, arg):
        """
        Action method.
        """
        if self.my_address:
            lg.out(4, 'udp_node.doUpdateMyAddress old=%s new=%s' % (str(self.my_address), str(arg)))
        self.my_address = arg
        # bpio.WriteFile(settings.ExternalIPFilename(), self.my_address[0])
        #TODO call top level code to notify about my external IP changes

    def doDHTReadMyIncomings(self, arg):
        """
        Action method.
        """
        # lg.out(18, 'doDHTReadMyIncomings')
        d = dht_service.get_value(self.my_id+':incomings')
        d.addCallback(self._got_my_incomings)

    def doDHTRemoveMyIncomings(self, arg):
        """
        Action method.
        """
        if len(self.my_current_incomings) > 0:
            # dht_service.delete_key(self.my_id+':incomings')
            dht_service.set_value(self.my_id+':incomings', '')

    def doDHTWtiteMyAddress(self, arg):
        """
        Action method.
        """
        d = dht_service.set_value(self.my_id+':address', '%s:%d' % (self.my_address[0], self.my_address[1]))
        d.addCallback(self._wrote_my_address)
        d.addErrback(lambda x: self.automat('dht-write-failed'))

    def doDisconnect(self, arg):
        """
        Action method.
        """
        udp_session.stop_process_sessions()
        for s in udp_session.sessions().values():
            lg.out(18, 'udp_node.doShutdown  send "shutdown" to %s' % s)
            s.automat('shutdown')
        # udp.remove_datagram_receiver_callback(self._datagram_received)
        self.automat('disconnected')

    def doNotifyDisconnected(self, arg):
        """
        Action method.
        """
        self.notified = False
        udp_interface.interface_disconnected(arg)

    def doNotifyConnected(self, arg):
        """
        Action method.
        """
        if not self.notified:
            udp_interface.interface_receiving_started(self.my_id)
            self.notified = True
            lg.out(4, 'udp_node.doNotifyConnected  my host is %s' % self.my_id)
        
    def doNotifyFailed(self, arg):
        """
        Action method.
        """
        udp_interface.interface_receiving_failed('state is %s' % self.state)

    def _datagram_received(self, datagram, address):
        """
        """
        command, payload = datagram
        # lg.out(18, '-> [%s] (%d bytes) from %s' % (command, len(payload), str(address)))
        s = udp_session.get(address)
        if s:
            s.automat('datagram-received', (datagram, address))
        self.automat('datagram-received', (datagram, address))
        return False
        
    def _stun_finished(self, result, address=None):
        self.automat(result, address)
        
    def _got_my_address(self, value):
        if type(value) != dict:
            lg.warn('  can not read my address')
            self.automat('dht-write-failed')
            return
        hkey = dht_service.key_to_hash(self.my_id+':address')
        if hkey not in value.keys():
            lg.out(4, 'udp_node._got_my_address ERROR   wrong key in response')
            self.automat('dht-write-failed')
            return
        value = value[hkey].strip('\n').strip()
        if value != '%s:%d' % (self.my_address[0], self.my_address[1]):
            lg.out(4, 'udp_node._got_my_address ERROR   value not fit: %s' % str(value)[:20])
            self.automat('dht-write-failed')
            return
        self.automat('dht-write-success')
        
    def _wrote_my_address(self, nodes):
        if len(nodes) == 0:
            self.automat('dht-write-failed')
            return
        d = dht_service.get_value(self.my_id+':address')
        d.addCallback(self._got_my_address)
        d.addErrback(lambda x: self.automat('dht-write-failed'))

    def _got_my_incomings(self, value):
        # lg.out(18, 'incomings: ' + str(value))
        if type(value) != dict:
            self.automat('dht-read-result', [])
            return
        hkey = dht_service.key_to_hash(self.my_id+':incomings')
        if hkey not in value.keys():
            self.automat('dht-read-result', [])
            return
        value = value[hkey].strip('\n').strip()
        if value == '':
            self.automat('dht-read-result', [])
            return
        value = value.split('\n')
        self.automat('dht-read-result', value)
    
#------------------------------------------------------------------------------ 


