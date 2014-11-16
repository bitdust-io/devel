

"""
.. module:: udp_connector
.. role:: red
BitPie.NET udp_connector() Automat


EVENTS:
    * :red:`abort`
    * :red:`dht-read-failed`
    * :red:`dht-read-success`
    * :red:`dht-write-failed`
    * :red:`dht-write-success`
    * :red:`start`
"""

import sys
import time

from logs import lg

from lib import automat

from dht import dht_service

import udp_session

#------------------------------------------------------------------------------ 

_Debug = False
_DebugLevel = 18

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
    if _Debug:
        lg.out(_DebugLevel, 'udp_connector.create peer_id=%s' % peer_id)

    c = DHTUDPConnector(node, peer_id)
    connectors()[c.id] = c
    lg.out(12, 'udp_connector.create peer_id=%s, refs=%d' % (peer_id, sys.getrefcount(c)))
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
    
    fast = True

    def __init__(self, node, peer_id):
        self.node = node
        self.peer_id = peer_id
        name = 'udp_connector[%s]' % self.peer_id
        automat.Automat.__init__(self, name, 'AT_STARTUP', 18)
        
    def init(self):
        """
        Method to initialize additional variables and flags at creation of the state machine.
        """
        self.listen_port = None
        self.my_id = None
        self.my_address = None
        self.working_deferred = None

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
            elif event == 'abort' :
                self.state = 'ABORTED'
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
            elif event == 'abort' :
                self.state = 'ABORTED'
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
            elif event == 'abort' :
                self.state = 'ABORTED'
                self.doDestroyMe(arg)
        #---ABORTED---
        elif self.state == 'ABORTED':
            pass
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
        self.working_deferred = dht_service.get_value(key)
        self.working_deferred.addCallback(self._got_peer_incoming, key, self.KeyPosition)
        self.working_deferred.addErrback(lambda x: self.automat('dht-read-failed'))

    def doDHTWriteIncoming(self, arg):
        """
        Action method.
        """
        key = self.peer_id+':incoming'+str(self.KeyPosition)
        value = '%s %s:%d %s\n' % (
            str(self.my_id), self.my_address[0], self.my_address[1], str(time.time()))
        if _Debug:
            lg.out(_DebugLevel, 'doDHTWriteIncoming  key=%s' % key)
        self.working_deferred = dht_service.set_value(key, value)
        self.working_deferred.addCallback(self._wrote_peer_incoming)
        self.working_deferred.addErrback(lambda x: self.automat('dht-write-failed'))
        
    def doStartNewSession(self, arg):
        """
        Action method.
        """
        peer_address = arg
        if self.node.my_address is None:
            if _Debug:
                lg.out(_DebugLevel, 'udp_connector.doStartNewSession to %s at %s SKIP because my_address is None' % (self.peer_id, peer_address))
            return
        s = udp_session.get(peer_address)
        if s:
            if _Debug:
                lg.out(_DebugLevel, 'udp_connector.doStartNewSession SKIP because found existing : %s' % s)
            return
        s = udp_session.get_by_peer_id(self.peer_id)
        if s:
            if _Debug:
                lg.out(_DebugLevel, 'udp_connector.doStartNewSession SKIP because found existing by peer id:%s %s' % (self.peer_id, s))
            return
        s = udp_session.create(self.node, peer_address, self.peer_id)
        s.automat('init', (self.listen_port, self.my_id, self.my_address))

    def doDHTReadPeerAddress(self, arg):
        """
        Action method.
        """
        key = self.peer_id+':address'
        self.working_deferred = dht_service.get_value(key)
        self.working_deferred.addCallback(self._got_peer_address, key)
        self.working_deferred.addErrback(lambda x: self.automat('dht-read-failed'))

    def doReportFailed(self, arg):
        """
        Action method.
        """
        udp_session.report_and_remove_pending_outbox_files_to_host(self.peer_id, 'unable to establish connection')
        
    def doDestroyMe(self, arg):
        """
        Action method.
        """
        if self.working_deferred:
            self.working_deferred.cancel()
            self.working_deferred = None
        self.node = None
        connectors().pop(self.id)
        self.destroy()

    def _got_peer_incoming(self, value, key, position):
        if _Debug:
            lg.out(_DebugLevel, 'udp_connector._got_peer_incoming at position %d: %d' % (position, len(str(value))))
        self.working_deferred = None
        incoming = None 
        if type(value) != dict:
            self.automat('dht-read-failed')
            return
        try:
            # incoming = value.values()[0]
            incoming = value[dht_service.key_to_hash(key)]
        except:
            lg.out(2, '%r' % value)
            lg.exc()
            self.automat('dht-read-failed')
            return
        try:
            incoming_peer_id, incoming_user_address, time_placed = incoming.split(' ')
            incoming_user_address = incoming_user_address.split(':')
            incoming_user_address = (incoming_user_address[0], int(incoming_user_address[1]))
        except:
            lg.out(2, '%r' % incoming)
            lg.exc()
            self.automat('dht-read-failed')
            return
        self.automat('dht-read-success', (incoming_peer_id, incoming_user_address))        
        
    def _wrote_peer_incoming(self, nodes):
        self.working_deferred = None
        if len(nodes) > 0:
            self.automat('dht-write-success')
        else:
            self.automat('dht-write-failed')
        
    def _got_peer_address(self, value, key):
        if type(value) != dict:
            self.automat('dht-read-failed')
            return
        try:
            peer_ip, peer_port = value[dht_service.key_to_hash(key)].split(':')
            peer_port = int(peer_port)
        except:
            lg.exc()
            self.automat('dht-read-failed')            
            return
        if _Debug:
            lg.out(_DebugLevel, 'udp_connector._got_peer_address %s:%d ~ %s' % (
                peer_ip, peer_port, self.peer_id))
        self.automat('dht-read-success', (peer_ip, peer_port))        


