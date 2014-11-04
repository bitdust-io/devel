

"""
.. module:: stun_client
.. role:: red

BitPie.NET ``stun_client()`` Automat


EVENTS:
    * :red:`all-port-numbers-received`
    * :red:`all-responded`
    * :red:`datagram-received`
    * :red:`dht-nodes-not-found`
    * :red:`found-some-nodes`
    * :red:`init`
    * :red:`shutdown`
    * :red:`start`
    * :red:`timer-10sec`
    * :red:`timer-2sec`
"""

if __name__ == '__main__':
    import sys
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

from logs import lg

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
        _StunClient = StunClient('stun_client', 'AT_STARTUP', 8)
    if event is not None:
        _StunClient.automat(event, arg)
    return _StunClient


class StunClient(automat.Automat):
    """
    This class implements all the functionality of the ``stun_client()`` state machine.
    """
    fast = True

    timers = {
        'timer-2sec': (2.0, ['REQUEST']),
        'timer-10sec': (10.0, ['PORTS_NUM?','REQUEST']),
        }

    MESSAGES = {
        'MSG_01': 'not found any DHT nodes',
        'MSG_02': 'not found any available stun servers',
        'MSG_03': 'timeout responding from stun servers',
        }

    def msg(self, msgid, arg=None):
        return self.MESSAGES.get(msgid, '')
    
    def init(self):
        # self.log_events = True
        self.listen_port = None
        self.callback = None
        self.minimum_needed_servers = 4
        self.stun_nodes = []
        self.stun_servers = []
        self.stun_results = {}
        self.deferreds = {}
        
    def A(self, event, arg):
        #---STOPPED---
        if self.state == 'STOPPED':
            if event == 'shutdown' :
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'start' :
                self.state = 'RANDOM_NODES'
                self.doDHTFindRandomNodes(arg)
        #---REQUEST---
        elif self.state == 'REQUEST':
            if event == 'shutdown' :
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'datagram-received' and self.isMyIPPort(arg) :
                self.doRecordResult(arg)
            elif event == 'timer-2sec' :
                self.doStun(arg)
            elif event == 'all-responded' or ( event == 'timer-10sec' and self.isSomeServersResponded(arg) ) :
                self.state = 'KNOW_MY_IP'
                self.doReportSuccess(arg)
                self.doClearResults(arg)
            elif event == 'timer-10sec' and not self.isSomeServersResponded(arg) :
                self.state = 'STOPPED'
                self.doReportFailed(self.msg('MSG_03', arg))
                self.doClearResults(arg)
        #---KNOW_MY_IP---
        elif self.state == 'KNOW_MY_IP':
            if event == 'shutdown' :
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'start' :
                self.state = 'RANDOM_NODES'
                self.doDHTFindRandomNodes(arg)
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'init' :
                self.state = 'STOPPED'
                self.doInit(arg)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        #---PORTS_NUM?---
        elif self.state == 'PORTS_NUM?':
            if event == 'shutdown' :
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'timer-10sec' and not self.isSomePortNumberReceived(arg) :
                self.state = 'STOPPED'
                self.doReportFailed(self.msg('MSG_02', arg))
                self.doClearResults(arg)
            elif event == 'all-port-numbers-received' or ( event == 'timer-10sec' and self.isSomePortNumberReceived(arg) ) :
                self.state = 'REQUEST'
                self.doStun(arg)
        #---RANDOM_NODES---
        elif self.state == 'RANDOM_NODES':
            if event == 'shutdown' :
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'found-some-nodes' :
                self.state = 'PORTS_NUM?'
                self.doRememberStunNodes(arg)
                self.doRequestStunPortNumbers(arg)
            elif event == 'dht-nodes-not-found' :
                self.state = 'STOPPED'
                self.doReportFailed(self.msg('MSG_01', arg))
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

    def isSomeServersResponded(self, arg):
        """
        Condition method.
        """
        return len(self.stun_results) > 0

    def isSomePortNumberReceived(self, arg):
        """
        Condition method.
        """
        return len(self.stun_servers) > 0

    def doInit(self, arg):
        """
        Action method.
        """
        self.listen_port = arg
        lg.out(12, 'stun_client.doInit on port %d' % self.listen_port)
        udp.proto(self.listen_port).add_callback(self._datagram_received)

    def doDHTFindRandomNodes(self, arg):
        """
        Action method.
        """
        if arg:
            self.callback = arg
        self._find_random_nodes(3, [])

    def doRememberStunNodes(self, arg):
        """
        Action method.
        """
        self.stun_nodes = arg
            
    def doRequestStunPortNumbers(self, arg):
        """
        Action method.
        """
        nodes = arg
        for node in nodes:
            d = node.request('stun_port')
            d.addBoth(self._stun_port_received, node)
            self.deferreds[node] = d
       
    def doStun(self, arg):
        """
        Action method.
        """
        lg.out(12, 'stun_client.doStun to %d nodes' % len(self.stun_servers))
        for address in self.stun_servers:
            if address is None:
                continue
            if address in self.stun_results.keys():
                continue
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
        self.stun_results[address] = (ip, port)
        if len(self.stun_results) >= len(self.stun_servers):
            self.automat('all-responded')        

    def doClearResults(self, arg):
        """
        Action method.
        """
        self.stun_nodes = []
        self.stun_servers = []
        self.stun_results = {}

    def doReportSuccess(self, arg):
        """
        Action method.
        """
        try:
            min_port = min(map(lambda addr: addr[1], self.stun_results.values()))
            max_port = max(map(lambda addr: addr[1], self.stun_results.values()))
            my_ip = self.stun_results.values()[0][0]
        except:
            lg.exc()
            result = ('stun-failed', None, None, [])
        if min_port == max_port:
            result = ('stun-success', 'non-symmetric', my_ip, min_port)
        else:
            result = ('stun-success', 'symmetric', my_ip, self.stun_results)
        lg.out(4, 'stun_client.doReportSuccess: %s' % str(result))
        if self.callback:
            self.callback(result[0], result[1], result[2], result[3])

    def doReportFailed(self, arg):
        """
        Action method.
        """
        lg.out(4, 'stun_client.doReportFailed : %s' % arg)
        if self.callback:
            self.callback('stun-failed', None, None, [])

    def doDestroyMe(self, arg):
        """
        Action method.
        """
        global _StunClient
        _StunClient = None
        for d in self.deferreds.values():
            d.cancel()
        self.deferreds.clear()
        udp.proto(self.listen_port).remove_callback(self._datagram_received)
        self.destroy()

    def _datagram_received(self, datagram, address):
        self.automat('datagram-received', (datagram, address))
        return False

    def _find_random_nodes(self, tries, result_list, prev_key=None):
        if prev_key and self.deferreds.has_key(prev_key):
            self.deferreds.pop(prev_key)
        lg.out(12, 'stun_client._find_random_nodes tries=%d result_list=%d' % (tries, len(result_list)))
        if tries <= 0 or len(result_list) >= self.minimum_needed_servers:
            if len(result_list) > 0:
                self.automat('found-some-nodes', result_list)
            else:
                self.automat('dht-nodes-not-found')
            return
        new_key = dht_service.random_key()
        d = dht_service.find_node(new_key)
        d.addCallback(lambda nodes: self._find_random_nodes(tries-1, list(set(result_list+nodes)), new_key))
        d.addErrback(lambda x: self._find_random_nodes(tries-1, result_list, new_key))
        self.deferreds[new_key] = d
        
    def _stun_port_received(self, result, node):
        self.deferreds.pop(node)
        if isinstance(result, dict):
            try:
                port = int(result['stun_port'])
                address = node.address
                self.stun_servers.append((address, port))
            except:
                lg.exc()
                self.stun_servers.append(None)
        else:
            self.stun_servers.append(None)
        if len(self.stun_servers) == len(self.stun_nodes):
            self.automat('all-port-numbers-received')
            
#------------------------------------------------------------------------------ 

def main():
    from twisted.internet import reactor
    lg.set_debug_level(30)
    settings.init()
    dht_service.init(int(settings.getDHTPort()))
    dht_service.connect()
    udp.listen(int(settings.getUDPPort()))
    def _cb2(result, typ, ip, details):
        print 2, result, typ, ip, details
        A('shutdown')
    def _cb(result, typ, ip, details):
        print 1, result, typ, ip, details
        reactor.callLater(1, A, 'start', _cb2)
        reactor.callLater(1.1, A, 'shutdown')
    A('init', (int(settings.getUDPPort())))
    A('start', _cb)
    reactor.run()

if __name__ == '__main__':
    main()
    
    
    
    
