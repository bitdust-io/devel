

"""
.. module:: stun_client
.. role:: red

BitPie.NET ``stun_client()`` Automat


EVENTS:
    * :red:`datagram-received`
    * :red:`found-one-peer`
    * :red:`peers-not-found`
    * :red:`start`
    * :red:`timer-01sec`
    * :red:`timer-1sec`
"""

import os
import random

from logs import lg

from lib import bpio
from lib import automat
from lib import udp
from lib import settings

from dht import dht_service

#------------------------------------------------------------------------------ 

_StunClient = None

#------------------------------------------------------------------------------ 

def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """
    global _StunClient
    if _StunClient is None:
        # set automat name and starting state here
        _StunClient = StunClient('stun_client', 'STOPPED', 8)
    if event is not None:
        _StunClient.automat(event, arg)
    return _StunClient


class StunClient(automat.Automat):
    """
    This class implements all the functionality of the ``stun_client()`` state machine.
    """

    timers = {
        'timer-1sec': (1.0, ['REQUEST']),
        'timer-01sec': (0.1, ['REQUEST']),
        }

    def init(self):
        self.listen_port = None
        self.peer_address = None
        self.callback = None
        
    def A(self, event, arg):
        #---STOPPED---
        if self.state == 'STOPPED':
            if event == 'start' :
                self.state = 'RANDOM_PEER'
                self.doInit(arg)
                self.doDHTFindRandomNode(arg)
        #---RANDOM_PEER---
        elif self.state == 'RANDOM_PEER':
            if event == 'found-one-peer' :
                self.state = 'REQUEST'
                self.doRememberPeer(arg)
                self.doStun(arg)
            elif event == 'datagram-received' and self.isMyIPPort(arg) :
                self.state = 'KNOW_MY_IP'
                self.doReportSuccess(arg)
            elif event == 'peers-not-found' :
                self.state = 'STOPPED'
                self.doReportFailed(arg)
        #---REQUEST---
        elif self.state == 'REQUEST':
            if event == 'datagram-received' and self.isMyIPPort(arg) :
                self.state = 'KNOW_MY_IP'
                self.doReportSuccess(arg)
            elif event == 'timer-1sec' :
                self.state = 'RANDOM_PEER'
                self.doDHTFindRandomNode(arg)
            elif event == 'timer-01sec' :
                self.doStun(arg)
        #---KNOW_MY_IP---
        elif self.state == 'KNOW_MY_IP':
            if event == 'start' :
                self.state = 'RANDOM_PEER'
                self.doInit(arg)
                self.doDHTFindRandomNode(arg)

    def isMyIPPort(self, arg):
        """
        Condition method.
        """
        try:
            datagram, address = arg
            command, payload = datagram
        except:
            return False
        return command == udp.CMD_MYIPPORT

    def doInit(self, arg):
        """
        Action method.
        """
        # udp.add_datagram_receiver_callback(self._datagram_received)
        if arg:
            self.listen_port, self.callback = arg
        else:
            self.listen_port, self.callback = int(settings.getUDPPort()), None
        udp.proto(self.listen_port).add_callback(self._datagram_received)

    def doReportSuccess(self, arg):
        """
        Action method.
        """
        try:
            datagram, address = arg
            command, payload = datagram
            ip, port = payload.split(':')
            port = int(port)
        except:
            lg.exc()
            return False
        oldip = bpio._read_data(settings.ExternalIPFilename()).strip()
        bpio._write_data(settings.ExternalIPFilename(), ip)
        bpio._write_data(settings.ExternalUDPPortFilename(), str(port))
        if self.callback:
            self.callback('stun-success', (ip, port))
        if oldip != ip:
            import p2p.network_connector
            p2p.network_connector.A('reconnect')
        lg.out(4, 'stun_client.doReportSuccess my IP:PORT is %s:%d' % (ip, port))

    def doReportFailed(self, arg):
        """
        Action method.
        """
        if self.callback:
            self.callback('stun-failed', None)

    def doRememberPeer(self, arg):
        """
        Action method.
        """
        self.peer_address = arg

    def doDHTFindRandomNode(self, arg):
        """
        Action method.
        """
        def _find(x):
            d = dht_service.find_node(dht_service.random_key())
            d.addCallback(self._found_nodes)
        d = dht_service.reconnect()
        d.addCallback(_find)

    def doStun(self, arg):
        """
        Action method.
        """
        # lg.out(18, 'stun_client.doStun to %s' % str(self.peer_address))
        udp.send_command(self.listen_port, udp.CMD_STUN, '', self.peer_address)

    def _datagram_received(self, datagram, address):
        """
        """
        # lg.out(10, 'stun_client._datagram_received %s' % str(datagram))
        self.automat('datagram-received', (datagram, address))
        return False
        
    def _found_nodes(self, nodes):
        # addresses = map(lambda x: x.address, nodes)
        # lg.out(18, 'stun_client.found_nodes %d nodes' % len(nodes))
        if len(nodes) > 0:
            node = random.choice(nodes)
            d = node.request('stun_port')
            d.addBoth(self._got_stun_port, node.address)
        else:
            self.automat('peers-not-found')
        
    def _got_stun_port(self, response, node_ip_address):
        try:
            port = int(response['stun_port'])
        except:
            # lg.exc()
            # Unknown stun port, let's use default port, even if we use some another port
            # TODO need to put that default port in the settings
            port = int(settings.DefaultUDPPort())
            lg.warn('stun_port is None, use default: %d' % port) 
        # lg.out(18, 'stun_client.got_stun_port %s' % str((node_ip_address, port)))
        if port:
            self.automat('found-one-peer', (node_ip_address, port))
        else:
            self.automat('peers-not-found')


