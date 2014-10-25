

"""
.. module:: stun_client
.. role:: red

BitPie.NET ``stun_client()`` Automat


EVENTS:
    * :red:`all-responded`
    * :red:`datagram-received`
    * :red:`found-some-peers`
    * :red:`peers-not-found`
    * :red:`start`
    * :red:`timer-10sec`
    * :red:`timer-2sec`
"""

import os
import sys
import random

from twisted.internet.defer import Deferred, DeferredList

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

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
        'timer-2sec': (2.0, ['REQUEST']),
        'timer-10sec': (10.0, ['REQUEST']),
        }

    def init(self):
        self.listen_port = None
        self.callback = None
        self.stun_servers = []
        self.stun_results = {}
        
    def A(self, event, arg):
        #---STOPPED---
        if self.state == 'STOPPED':
            if event == 'start' :
                self.state = 'RANDOM_PEERS'
                self.doInit(arg)
                self.doDHTFindRandomNodes(arg)
        #---REQUEST---
        elif self.state == 'REQUEST':
            if event == 'datagram-received' and self.isMyIPPort(arg) :
                self.doRecordResult(arg)
            elif event == 'timer-10sec' and not self.isResponded(arg) :
                self.state = 'STOPPED'
                self.doReportFailed(arg)
            elif event == 'timer-2sec' :
                self.doStun(arg)
            elif event == 'all-responded' or ( event == 'timer-10sec' and self.isResponded(arg) ) :
                self.state = 'KNOW_MY_IP'
                self.doReportSuccess(arg)
        #---KNOW_MY_IP---
        elif self.state == 'KNOW_MY_IP':
            if event == 'start' :
                self.state = 'RANDOM_PEERS'
                self.doInit(arg)
                self.doDHTFindRandomNodes(arg)
        #---RANDOM_PEERS---
        elif self.state == 'RANDOM_PEERS':
            if event == 'found-some-peers' :
                self.state = 'REQUEST'
                self.doRememberPeers(arg)
                self.doStun(arg)
            elif event == 'peers-not-found' :
                self.state = 'STOPPED'
                self.doReportFailed(arg)
        return None

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

    def isResponded(self, arg):
        """
        Condition method.
        """
        return len(self.stun_results) > 0
        
    def doInit(self, arg):
        """
        Action method.
        """
        if arg:
            self.listen_port, self.callback = arg
        else:
            self.listen_port, self.callback = int(settings.getUDPPort()), None
        udp.proto(self.listen_port).add_callback(self._datagram_received)

    def doReportSuccess(self, arg):
        """
        Action method.
        """
        if self.callback:
            self.callback('stun-success', self.stun_results.values()[0])
#        try:
#            datagram, address = arg
#            command, payload = datagram
#            ip, port = payload.split(':')
#            port = int(port)
#        except:
#            lg.exc()
#            return False
#        oldip = bpio._read_data(settings.ExternalIPFilename()).strip()
#        bpio._write_data(settings.ExternalIPFilename(), ip)
#        bpio._write_data(settings.ExternalUDPPortFilename(), str(port))
#        if self.callback:
#            self.callback('stun-success', (ip, port))
#        if oldip != ip:
#            import p2p.network_connector
#            p2p.network_connector.A('reconnect')
        # lg.out(4, 'stun_client.doReportSuccess my IP:PORT is %s:%d' % (ip, port))

    def doReportFailed(self, arg):
        """
        Action method.
        """
        if self.callback:
            self.callback('stun-failed', None)

    def doRememberPeers(self, arg):
        """
        Action method.
        """
        self.stun_servers = arg

    def doDHTFindRandomNodes(self, arg):
        """
        Action method.
        """
        self._find_one_node(1, [])

    def doStun(self, arg):
        """
        Action method.
        """
        lg.out(12, 'stun_client.doStun to %d nodes' % len(self.stun_servers))
        for address in self.stun_servers:
            if address in self.stun_results.keys():
                continue
            # print 'stun to %s:%d' % address
            udp.send_command(self.listen_port, udp.CMD_STUN, '', address)

    def doRecordResult(self, arg):
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
        # print 'my IP:PORT %s:%d from %r' % (ip, port, address)
        self.stun_results[address] = (ip, port)
        # print len(self.stun_results), len(self.stun_servers)
        if len(self.stun_results) >= len(self.stun_servers):
            self.automat('all-responded')

    def _datagram_received(self, datagram, address):
        """
        """
        # lg.out(10, 'stun_client._datagram_received %s' % str(datagram))
        self.automat('datagram-received', (datagram, address))
        return False

    def _find_one_node(self, tries, result_list):
        lg.out(18, 'stun_client._find_one_node %d result_list=%d' % (tries, len(result_list)))
        if tries <= 0 or len(result_list) >= 8:
            if len(result_list) > 0:
                # print result_list
                self.automat('found-some-peers', result_list)
            else:
                self.automat('peers-not-found')
            return
        def _find(x):
            d = dht_service.find_node(dht_service.random_key())
            d.addCallback(self._found_nodes, tries-1, result_list)
            d.addErrback(lambda x: self._find_one_node(tries-1, result_list))
        d = dht_service.reconnect()
        d.addCallback(_find)
        
    def _found_nodes(self, nodes, tries, result_list):
        # addresses = map(lambda x: x.address, nodes)
        # lg.out(18, 'stun_client.found_nodes %d nodes: %r' % (len(nodes), nodes))
        if len(nodes) == 0:
            self._find_one_node(tries, result_list)
            return
        l = []
        sent = set()
        for node in nodes:
            if node.address in map(lambda i: i[0], result_list):
                # print 'skip request to', node
                continue
            if node.address in sent:
                continue
            d = node.request('stun_port')
            d.addErrback(lambda x: x)
            l.append(d)
            sent.add(node.address)
            # print 'request stun port from', node
        dl = DeferredList(l)
        dl.addCallback(self._got_stun_servers_ports, nodes, tries, result_list)
        # dl.addErrback(self._request_error)
            
#    def _not_found_nodes(self, err, tries, result_list):
#        lg.out(1, str(err))
#        self._find_one_node(tries, result_list)
        
    def _got_stun_servers_ports(self, results, nodes, tries, result_list):
        # lg.out(18, 'stun_client._got_stun_servers_ports %r' % results)
        # lg.out(18, '    %r' % nodes)
        for i in range(len(results)):
            result = results[i]
            if result[0]:
                try:
                    port = int(result[1]['stun_port'])
                    address = nodes[i].address
                except:
                    lg.exc()
                    # Unknown stun port, let's use default port, even if we use some another port
                    # TODO need to put that default port in the settings
                    port = int(settings.DefaultUDPPort())
                    lg.warn('stun_port is None, use default: %d' % port) 
                result_list.append((address, port))
        # lg.out(18, '    %r' % result_list)
        self._find_one_node(tries, result_list)
        
    def _request_error(self, err):
        lg.out(1, str(err))
        
#------------------------------------------------------------------------------ 

def main():
    from twisted.internet import reactor
    lg.set_debug_level(24)
    bpio.init()
    dht_service.init(int(settings.getDHTPort()))
    udp.listen(int(settings.getUDPPort()))
    def _finished(x, result):
        print x, result
        reactor.stop()
    A('start', (int(settings.getUDPPort()), _finished))
    reactor.run()

if __name__ == '__main__':
    main()
    
