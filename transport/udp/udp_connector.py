

"""
.. module:: udp_connector
.. role:: red
BitPie.NET udp_connector() Automat


EVENTS:
    * :red:`dht-read-failed`
    * :red:`dht-read-success`
    * :red:`dht-write-failed`
    * :red:`dht-write-success`
    * :red:`start`
"""

import time

from logs import lg

from lib import automat

from dht import dht_service

import udp_session

#------------------------------------------------------------------------------ 

_ConnectorsDict = {}

#------------------------------------------------------------------------------ 

def connectors():
    """
    """
    global _ConnectorsDict
    return _ConnectorsDict


def create(node, peer_id):
    """
    """
    lg.out(12, 'udp_connector.create peer_id=%s' % peer_id)
    c = DHTUDPConnector(node, peer_id)
    connectors()[c.id] = c
    return c


def get(peer_id):
    """
    """
    for id, c in connectors().items():
        if c.peer_id == peer_id:
            return c 
    return None
    
#------------------------------------------------------------------------------ 

class DHTUDPConnector(automat.Automat):
    """
    This class implements all the functionality of the ``udp_connector()`` state machine.
    """

    def __init__(self, node, peer_id):
        self.node = node
        self.peer_id = peer_id
        name = 'udp_connector[%s]' % self.peer_id
        automat.Automat.__init__(self, name, 'AT_STARTUP')
    
    def init(self):
        """
        """
        self.listen_port = None
        self.my_id = None
        self.my_address = None

    def A(self, event, arg):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'start' :
                self.state = 'DHT_LOOP'
                self.doInit(arg)
                self.KeyPosition=0
                self.doDHTReadIncoming(arg)
        #---DHT_WRITE---
        elif self.state == 'DHT_WRITE':
            if event == 'dht-write-success' :
                self.state = 'DHT_READ'
                self.doDHTReadPeerAddress(arg)
            elif event == 'dht-write-failed' :
                self.state = 'FAILED'
                self.doReportFailed(arg)
                self.doDestroyMe(arg)
        #---DHT_READ---
        elif self.state == 'DHT_READ':
            if event == 'dht-read-success' :
                self.state = 'DONE'
                self.doStartNewSession(arg)
                self.doDestroyMe(arg)
            elif event == 'dht-read-failed' :
                self.state = 'FAILED'
                self.doReportFailed(arg)
                self.doDestroyMe(arg)
        #---DONE---
        elif self.state == 'DONE':
            pass
        #---FAILED---
        elif self.state == 'FAILED':
            pass
        #---DHT_LOOP---
        elif self.state == 'DHT_LOOP':
            if event == 'dht-read-failed' :
                self.state = 'DHT_WRITE'
                self.doDHTWriteIncoming(arg)
            elif event == 'dht-read-success' and self.KeyPosition>=10 :
                self.state = 'FAILED'
                self.doReportFailed(arg)
                self.doDestroyMe(arg)
            elif event == 'dht-read-success' and self.KeyPosition<10 and not self.isMyIncoming(arg) :
                self.KeyPosition+=1
                self.doDHTReadIncoming(arg)
            elif event == 'dht-read-success' and self.isMyIncoming(arg) :
                self.state = 'DHT_READ'
                self.doDHTReadPeerAddress(arg)
        return None

    def isMyIncoming(self, arg):
        """
        Condition method.
        """
        incoming_peer_id, incoming_user_address = arg
        return incoming_peer_id == self.my_id and incoming_user_address == self.my_address

    def doInit(self, arg):
        """
        Action method.
        """
        self.listen_port, self.my_id, self.my_address = arg

    def doDHTReadIncoming(self, arg):
        """
        Action method.
        """
        key = self.peer_id+':incoming'+str(self.KeyPosition)
        d = dht_service.get_value(key)
        d.addCallback(self._got_peer_incoming, self.KeyPosition)
        d.addErrback(lambda x: self.automat('dht-read-failed'))

    def doDHTWriteIncoming(self, arg):
        """
        Action method.
        """
        key = self.peer_id+':incoming'+str(self.KeyPosition)
        value = '%s %s:%d %s\n' % (
            str(self.my_id), self.my_address[0], self.my_address[1], str(time.time()))
        lg.out(18, 'doDHTWriteIncoming  key=%s' % key)
        d = dht_service.set_value(key, value)
        d.addCallback(self._wrote_peer_incoming)
        d.addErrback(lambda x: self.automat('dht-write-failed'))

    def doStartNewSession(self, arg):
        """
        Action method.
        """
        peer_address = arg
        if self.node.my_address is None:
            lg.out(18, 'udp_connector.doStartNewSession to %s at %s SKIP because my_address is None' % (self.peer_id, peer_address))
            return
        s = udp_session.get(peer_address)
        if s:
            lg.out(18, 'udp_connector.doStartNewSession SKIP because found existing : %s' % s)
            return
        s = udp_session.get_by_peer_id(self.peer_id)
        if s:
            lg.out(18, 'udp_connector.doStartNewSession SKIP because found existing by peer id:%s %s' % (self.peer_id, s))
            return
        s = udp_session.create(self.node, peer_address, self.peer_id)
        s.automat('init', (self.listen_port, self.my_id, self.my_address))

    def doDHTReadPeerAddress(self, arg):
        """
        Action method.
        """
        d = dht_service.get_value(self.peer_id+':address')
        d.addCallback(self._got_peer_address)
        d.addErrback(lambda x: self.automat('dht-read-failed'))

    def doReportFailed(self, arg):
        """
        Action method.
        """
        udp_session.report_and_remove_pending_outbox_files_to_host(self.peer_id, 'unable to establish connection')

    def doDestroyMe(self, arg):
        """
        Action method.
        """
        self.node = None
        connectors().pop(self.id)
        automat.objects().pop(self.index)

    def _got_peer_incoming(self, value, position):
        lg.out(18, 'udp_connector._got_peer_incoming at position %d: %d' % (position, len(str(value))))
        incoming = None 
        if type(value) != dict:
            self.automat('dht-read-failed')
            return
        try:
            incoming = value.values()[0]
        except:
            lg.exc()
            self.automat('dht-read-failed')
            return
        try:
            incoming_peer_id, incoming_user_address, time_placed = incoming.split(' ')
            incoming_user_address = incoming_user_address.split(':')
            incoming_user_address = (incoming_user_address[0], int(incoming_user_address[1]))
        except:
            lg.exc()
            self.automat('dht-read-failed')
            return
        self.automat('dht-read-success', (incoming_peer_id, incoming_user_address))
        
    def _wrote_peer_incoming(self, nodes):
        if len(nodes) > 0:
            self.automat('dht-write-success')
        else:
            self.automat('dht-write-failed')
        
    def _got_peer_address(self, value):
        lg.out(18, 'udp_connector._got_peer_address  %r' % value)
        if type(value) != dict:
            self.automat('dht-read-failed')
            return
        try:
            peer_ip, peer_port = value.values()[0].split(':')
            peer_port = int(peer_port)
        except:
            self.automat('dht-read-failed')            
            return
        self.automat('dht-read-success', (peer_ip, peer_port))


