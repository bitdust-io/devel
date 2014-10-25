

import os
import sys
import random

from twisted.internet import reactor
from twisted.internet.defer import Deferred, DeferredList

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

from logs import lg

from lib import bpio
from lib import udp
from lib import settings

from stun import stun_client
from dht import dht_service

#------------------------------------------------------------------------------ 

def loop_send_packets(min_port, max_port):
    n = 0
    if max_port - min_port > 100:
        max_port = min_port + 100
    for port_num in range(min_port, max_port+1):
        udp.send_command(int(settings.getUDPPort()), udp.CMD_PING, 'ping', (sys.argv[1], port_num))
        n += 1
    print 'sent %d packets to %s' % (n, sys.argv[1])
    reactor.callLater(10, loop_send_packets, min_port, max_port)

def datagram_received(datagram, address):
    try:
        cmd, payload = datagram
    except:
        return
    if cmd != udp.CMD_PING:
        return
    print 'datagram [%s] from %r' % (datagram, address)
    if address[0] == sys.argv[1]:
        print 'OKAY!!!!!!!!!!!!!!'
        reactor.stop()

def main():
    print 'usage:  natpunch.py  <remote IP> [min port] [max port]'
    lg.set_debug_level(24)
    bpio.init()
    dht_service.init(int(settings.getDHTPort()))
    udp.listen(int(settings.getUDPPort()))
    udp.proto(int(settings.getUDPPort())).add_callback(datagram_received)
    def _finished(x, result):
        # print 'stun_finished:', stun_client.A().stun_results.values()
        min_port = 999999
        max_port = 0
        if len(sys.argv) > 3:
            min_port = int(sys.argv[2])
            max_port = int(sys.argv[3])
        else:
            for addr, port in stun_client.A().stun_results.values():
                print addr, port
                if port > max_port:
                    max_port = port
                if port < min_port:
                    min_port = port
        print 'ports range:', min_port, max_port
        loop_send_packets(min_port, max_port)
    stun_client.A('start', (int(settings.getUDPPort()), _finished))
    reactor.run()

if __name__ == '__main__':
    main()
    