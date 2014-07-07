

"""
.. module:: stun_client
.. role:: red

BitPie.NET ``stun_client()`` Automat


EVENTS:
    * :red:`datagram-received`
    * :red:`found-one-peer`
    * :red:`peers-not-found`
    * :red:`start`
    * :red:`timer-02sec`
    * :red:`timer-3sec`
"""

import os
import random

import lib.dhnio as dhnio
import lib.automat as automat
import lib.udp as udp
import lib.settings as settings

import dht.dht_service as dht_service

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
        _StunClient = StunClient('stun_client', 'STOPPED')
    if event is not None:
        _StunClient.automat(event, arg)
    return _StunClient


class StunClient(automat.Automat):
    """
    This class implements all the functionality of the ``stun_client()`` state machine.
    """

    timers = {
        'timer-02sec': (0.2, ['REQUEST']),
        'timer-3sec': (3.0, ['REQUEST']),
        }

    def init(self):
        self.listen_port = None
        self.peer_address = None
        self.callback = None
        
    def A(self, event, arg):
        #---STOPPED---
        if self.state is 'STOPPED':
            if event == 'start' :
                self.state = 'RANDOM_PEER'
                self.doInit(arg)
                self.doDHTFindRandomNode(arg)
        #---RANDOM_PEER---
        elif self.state is 'RANDOM_PEER':
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
        elif self.state is 'REQUEST':
            if event == 'datagram-received' and self.isMyIPPort(arg) :
                self.state = 'KNOW_MY_IP'
                self.doReportSuccess(arg)
            elif event == 'timer-3sec' :
                self.state = 'RANDOM_PEER'
                self.doDHTFindRandomNode(arg)
            elif event == 'timer-02sec' :
                self.doStun(arg)
        #---KNOW_MY_IP---
        elif self.state is 'KNOW_MY_IP':
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
        self.listen_port, self.callback = arg
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
            return False
        oldip = dhnio._read_data(settings.ExternalIPFilename()).strip()
        dhnio._write_data(settings.ExternalIPFilename(), ip)
        dhnio._write_data(settings.ExternalUDPPortFilename(), str(port))
        self.callback('stun-success', (ip, port))
        if oldip != ip:
            import p2p.network_connector
            p2p.network_connector.A('reconnect')

    def doReportFailed(self, arg):
        """
        Action method.
        """
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
        dhnio.Dprint(18, 'stun_client.doStun to %s' % str(self.peer_address))
        udp.send_command(self.listen_port, udp.CMD_STUN, '', self.peer_address)

    def _datagram_received(self, datagram, address):
        """
        """
        self.automat('datagram-received', (datagram, address))
        
    def _found_nodes(self, nodes):
        # addresses = map(lambda x: x.address, nodes)
        dhnio.Dprint(18, 'stun_client.found_nodes %d nodes' % len(nodes))
        if len(nodes) > 0:
            node = random.choice(nodes)
            d = node.request('stun_port')
            d.addBoth(self._got_stun_port, node.address)
        else:
            self.automat('peers-not-found')
        
    def _got_stun_port(self, response, node_ip_address):
        # dhnio.Dprint(18, 'stun_client.got_stun_port response=%s' % str(response) )
        try:
            port = int(response['stun_port'])
        except:
            # Unknown stun port, let's use default port, even if we use some another port
            # TODO need to put that default port in the settings 
            port = int(settings.DefaultUDPPort())
            # dhnio.DprintException()
        if port:
            self.automat('found-one-peer', (node_ip_address, port))
        else:
            self.automat('peers-not-found')
