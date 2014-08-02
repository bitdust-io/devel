

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
        self.listen_port = None
        self.my_id = None
        self.my_address = None
        name = 'udp_connector[%s]' % self.peer_id
        automat.Automat.__init__(self, name, 'AT_STARTUP')

    def state_changed(self, oldstate, newstate):
        """
        Method to to catch the moment when automat's state were changed.
        """

    def A(self, event, arg):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'start' :
                self.state = 'DHT_WRITE'
                self.doInit(arg)
                self.doDHTWritePeerIncomings(arg)
        #---DHT_WRITE---
        elif self.state == 'DHT_WRITE':
            if event == 'dht-write-success' :
                self.state = 'DHT_READ'
                self.doDHTReadPeerAddress(arg)
            elif event == 'dht-write-failed' :
                self.state = 'FAILED'
                self.doDestroyMe(arg)
        #---DHT_READ---
        elif self.state == 'DHT_READ':
            if event == 'dht-read-success' :
                self.state = 'DONE'
                self.doStartNewSession(arg)
                self.doDestroyMe(arg)
            elif event == 'dht-read-failed' :
                self.state = 'FAILED'
                self.doDestroyMe(arg)
        #---DONE---
        elif self.state == 'DONE':
            pass
        #---FAILED---
        elif self.state == 'FAILED':
            pass

    def doInit(self, arg):
        """
        Action method.
        """
        self.listen_port, self.my_id, self.my_address = arg

    def doStartNewSession(self, arg):
        """
        Action method.
        """
        # lg.out(10, 'udp_connector.doStartNewSession wants to start a new session')
        peer_address = arg
        s = udp_session.get(peer_address)
        if s:
            return
        s = udp_session.create(self.node, peer_address, self.peer_id)
        s.automat('init', (self.listen_port, self.my_id, self.my_address))

    def doDHTWritePeerIncomings(self, arg):
        """
        Action method.
        """
        d = dht_service.get_value(self.peer_id+':incomings')
        d.addCallback(self._got_peer_incomings)
        d.addErrback(lambda x, key: self.automat, 'dht-write-failed')

    def doDHTReadPeerAddress(self, arg):
        """
        Action method.
        """
        d = dht_service.get_value(self.peer_id+':address')
        d.addCallback(self._got_peer_address)
        d.addErrback(lambda x, key: self.automat, 'dht-read-failed')

    def doDestroyMe(self, arg):
        """
        Action method.
        """
        self.node = None
        connectors().pop(self.id)
        automat.objects().pop(self.index)

    def _got_peer_incomings(self, value):
        # lg.out(18, 'udp_connector._got_peer_incomings %r' % value)
        current_incomings = []
        if type(value) == dict:
            try:
                current_incomings = value.values()[0].split('\n')
            except:
                lg.exc()
        new_incomings = []
        for incoming in current_incomings:
            try:
                incoming_peer_id, incoming_user_address, time_placed = incoming.split(' ')
                incoming_user_address = incoming_user_address.split(':')
                incoming_user_address = (incoming_user_address[0], int(incoming_user_address[1]))
            except:
                continue
            if incoming_peer_id == self.my_id and incoming_user_address == self.my_address:
                self.automat('dht-write-success')
                return
            new_incomings.append(incoming)
        my_incoming = '%s %s:%d %s\n' % (
            str(self.my_id), self.my_address[0], self.my_address[1], str(time.time()))
        new_incomings.append(my_incoming)
        new_value = '\n'.join(new_incomings)
        del new_incomings
        del current_incomings
        d = dht_service.set_value(self.peer_id+':incomings', new_value)
        d.addCallback(self._wrote_peers_incomings)
        
    def _wrote_peers_incomings(self, nodes):
        if len(nodes) > 0:
            self.automat('dht-write-success')
        else:
            self.automat('dht-write-failed')
        
    def _got_peer_address(self, value):
        # lg.out(18, 'udp_connector._got_peer_address  %r' % value)
        if type(value) != dict:
            self.automat('dht-read-failed')
            return
        try:
            peer_ip, peer_port = value.values()[0].split(':')
            peer_port = int(peer_port)
        except:
            self.automat('dht-read-failed')            
            return
        # print '_got_peer_address', value.values(), (peer_ip, peer_port)
        self.automat('dht-read-success', (peer_ip, peer_port))


