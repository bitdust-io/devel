

"""
.. module:: udp_node
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

from twisted.internet import reactor

from logs import lg

from automats import automat
from lib import udp
from main import settings

from stun import stun_client

from dht import dht_service

from services import driver

import udp_connector
import udp_session
import udp_interface
import udp_stream

#------------------------------------------------------------------------------ 

_Debug = False
_DebugLevel = 18

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
        _UDPNode = UDPNode('udp_node', 'AT_STARTUP', 24)
    if event is not None:
        _UDPNode.automat(event, arg)
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
    This class implements all the functionality of the ``udp_node()`` state machine.
    """

    fast = True

    timers = {
        'timer-1sec': (1.0, ['LISTEN']),
        'timer-10sec': (10.0, ['LISTEN']),
        }

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the state machine.
        """
        self.listen_port = None
        self.my_id = None
        self.my_address = None
        if driver.is_started('service_my_ip_port'):
            self.my_address = stun_client.A().getMyExternalAddress()
        self.notified = False
        self.IncomingPosition = -1
        
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
            elif event == 'dht-read-result' :
                self.doCheckAndStartNewSession(arg)
                self.doDHTRemoveMyIncoming(arg)
                self.doNotifyConnected(arg)
            elif event == 'connect' and not self.isKnowMyAddress(arg) :
                self.state = 'STUN'
                self.doStartStunClient(arg)
            elif event == 'timer-1sec' :
                self.doDHTReadNextIncoming(arg)
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'go-online' and not self.isKnowMyAddress(arg) :
                self.state = 'STUN'
                self.GoOn=False
                self.doInit(arg)
                self.doStartStunClient(arg)
            elif event == 'go-online' and self.isKnowMyAddress(arg) :
                self.state = 'WRITE_MY_IP'
                self.GoOn=False
                self.doInit(arg)
                self.doDHTWtiteMyAddress(arg)
        #---STUN---
        elif self.state == 'STUN':
            if event == 'stun-success' :
                self.state = 'WRITE_MY_IP'
                self.doUpdateMyAddress(arg)
                self.doDHTWtiteMyAddress(arg)
            elif event == 'go-offline' :
                self.state = 'DISCONNECTING'
                self.doDisconnect(arg)
            elif event == 'stun-failed' :
                self.state = 'OFFLINE'
                self.doUpdateMyAddress(arg)
                self.doNotifyFailed(arg)
        #---OFFLINE---
        elif self.state == 'OFFLINE':
            if event == 'go-online' :
                self.state = 'STUN'
                self.doStartStunClient(arg)
        #---WRITE_MY_IP---
        elif self.state == 'WRITE_MY_IP':
            if event == 'go-offline' :
                self.state = 'DISCONNECTING'
                self.doDisconnect(arg)
            elif event == 'connect' and not self.isKnowMyAddress(arg) :
                self.state = 'STUN'
                self.doStartStunClient(arg)
            elif event == 'connect' and self.isKnowMyAddress(arg) and not self.isKnownUser(arg) :
                self.doStartNewConnector(arg)
            elif event == 'dht-write-failed' :
                self.state = 'OFFLINE'
                self.doNotifyFailed(arg)
            elif event == 'dht-write-success' :
                self.state = 'LISTEN'
                self.doDHTReadNextIncoming(arg)
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
        return None

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
        if address in stun_client.A().stun_servers:
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
        if _Debug:
            lg.out(_DebugLevel, 'udp_node.isKnownUser %s not found in %s' % (
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
        bandoutlimit = settings.getBandOutLimit() #  or settings.DefaultBandwidthOutLimit()
        bandinlimit = settings.getBandInLimit() #  or settings.DefaultBandwidthInLimit()
        udp_stream.set_global_limit_send_bytes_per_sec(bandoutlimit)
        udp_stream.set_global_limit_receive_bytes_per_sec(bandinlimit)
        reactor.callLater(0, udp_session.process_sessions)

    def doStartStunClient(self, arg):
        """
        Action method.
        """
        stun_client.A('start', self._stun_finished)

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
        if _Debug:
            lg.out(_DebugLevel, 'udp_node.doStartNewSession wants to start a new session with UNKNOWN peer at %s' % str(address))
        s = udp_session.create(self, address)
        s.automat('init')
        s.automat('datagram-received', arg)

    def doCheckAndStartNewSession(self, arg):
        """
        Action method.
        """
        if self.my_address is None:
            if _Debug: 
                lg.out(_DebugLevel, 'dp_node.doCheckAndStartNewSession SKIP because my_address is None')
            return
        incoming_str = arg
        if incoming_str is None:
            return
        try:
            incoming_user_id, incoming_user_address, time_placed = incoming_str.split(' ')
            incoming_user_address = incoming_user_address.split(':')
            incoming_user_address[1] = int(incoming_user_address[1])
            incoming_user_address = tuple(incoming_user_address)
        except:
            if _Debug:
                lg.out(_DebugLevel, '%r' % incoming_str)
            lg.exc()
            return
        s = udp_session.get(incoming_user_address) 
        if s:
            if _Debug:
                lg.out(_DebugLevel, 'udp_node.doCheckAndStartNewSessions SKIP because found existing %s' % s)
            return
        s = udp_session.get_by_peer_id(incoming_user_id)
        if s:
            if _Debug:            
                lg.out(_DebugLevel, 'udp_node.doCheckAndStartNewSession SKIP because found existing by peer id:%s %s' % (incoming_user_id, s))
            return
        if _Debug:            
            lg.out(_DebugLevel, 'udp_node.doCheckAndStartNewSession wants to start a new session with incoming peer %s at %s' % (
                incoming_user_id, incoming_user_address))
        s = udp_session.create(self, incoming_user_address, incoming_user_id)
        s.automat('init')

    def doUpdateMyAddress(self, arg):
        """
        Action method.
        """
        try:
            typ, new_ip, new_port = arg
            new_addr = (new_ip, new_port)
        except:
            lg.exc()
            return
        if _Debug:            
            lg.out(4, 'udp_node.doUpdateMyAddress typ=[%s]' % typ)
            if self.my_address:
                lg.out(4, '    old=%s new=%s' % (str(self.my_address), str(new_addr)))
            else:
                lg.out(4, '    new=%s' % str(new_addr))
        self.my_address = new_addr

    def doDHTReadNextIncoming(self, arg):
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

    def doDHTRemoveMyIncoming(self, arg):
        """
        Action method.
        """
        if arg:
            key = self.my_id + ':incoming' + str(self.IncomingPosition)
            dht_service.delete_key(key)

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
        lg.out(12, 'udp_node.doDisconnect going to close %d sessions and %d connectors' % (
            len(udp_session.sessions().values()), len(udp_connector.connectors().values())))
        udp_session.stop_process_sessions()
        for s in udp_session.sessions().values():
            if _Debug:            
                lg.out(_DebugLevel, 'udp_node.doShutdown sends "shutdown" to %s' % s)
            s.automat('shutdown')
        for c in udp_connector.connectors().values():
            c.automat('abort')
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
            if _Debug:
                lg.out(4, 'udp_node.doNotifyConnected my host is %s' % self.my_id)
        
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
        
    def _stun_finished(self, result, typ, ip, details):
        if result == 'stun-success' and typ == 'symmetric':
            result = 'stun-failed'
        self.automat(result, (typ, ip, details))
        
    def _got_my_address(self, value, key):
        if type(value) != dict:
            lg.warn('can not read my address')
            self.automat('dht-write-failed')
            return
        try:
            addr = value[dht_service.key_to_hash(key)].strip('\n').strip()
        except:
            if _Debug:            
                lg.out(4, 'udp_node._got_my_address ERROR   wrong key in response: %r' % value)
                lg.exc()
            self.automat('dht-write-failed')
            return
        if addr != '%s:%d' % (self.my_address[0], self.my_address[1]):
            if _Debug:            
                lg.out(4, 'udp_node._got_my_address ERROR   value not fit: %r' % value)
            self.automat('dht-write-failed')
            return
        self.automat('dht-write-success')
        
    def _wrote_my_address(self, nodes):
        if len(nodes) == 0:
            self.automat('dht-write-failed')
            return
        key = self.my_id+':address'
        d = dht_service.get_value(key)
        d.addCallback(self._got_my_address, key)
        d.addErrback(lambda x: self.automat('dht-write-failed'))

    def _got_my_incoming(self, value, key, position):
        if type(value) != dict:
            if _Debug:            
                lg.out(_DebugLevel, 'udp_node._got_my_incoming no incoming at position: %d' % position)
            self.automat('dht-read-result', None)
            return
        try:
            myincoming = value[dht_service.key_to_hash(key)]
        except: 
            if _Debug:
                lg.out(_DebugLevel, 'udp_node._got_my_incoming ERROR reading my incoming at position: %d\n%r' % (position, value))
            self.automat('dht-read-result', None)
            return
        if _Debug:
            lg.out(_DebugLevel, 'udp_node._got_my_incoming found one: %r' % myincoming)
        self.automat('dht-read-result', myincoming)

    def _failed_my_incoming(self, err, key, position):
        if _Debug:
            lg.out(_DebugLevel, 'udp_node._got_my_incoming incoming empty: %s' % str(position))
        self.automat('dht-read-result', None)

