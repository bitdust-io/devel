
import os
import sys

from twisted.internet import reactor
from twisted.internet.defer import Deferred

sys.path.append(os.path.abspath('..'))

from logs import lg

from lib import misc
from lib import settings
from lib import nameurl
from lib import udp
from lib import bpio
from lib import commands

from crypto import signed

from dht import dht_service

from transport.udp import udp_node
from transport.udp import udp_session
from transport import gate

#------------------------------------------------------------------------------ 

def main():
    lg.set_debug_level(24)
    # options = { 'idurl': misc.getLocalID(),}
    # options['host'] = nameurl.GetName(misc.getLocalID())+'@'+'somehost.org'
    # options['dht_port'] = int(settings.getDHTPort())
    # options['udp_port'] = int(settings.getUDPPort())
    udp.listen(int(settings.getUDPPort())) 
    dht_service.init(int(settings.getDHTPort()))
    # dht_service.connect()
    # udp_node.A('go-online', options)
    reactor.addSystemEventTrigger('before', 'shutdown', gate.shutdown)
    gate.init()
    gate.start()
    if len(sys.argv) >= 3:
        p = signed.Packet(commands.Data(), misc.getLocalID(), 
                          misc.getLocalID(), misc.getLocalID(), 
                          bpio.ReadBinaryFile(sys.argv[1]), misc.getLocalID())
        bpio.WriteFile(sys.argv[1]+'.signed', p.Serialize())
        def _try_reconnect():
            sess = udp_session.get_by_peer_id(sys.argv[2])
            reconnect = False
            if not sess:
                reconnect = True
                print 'sessions', udp_session.sessions(),
                print map(lambda s: s.peer_id, udp_session.sessions())
            else:
                if sess.state != 'CONNECTED':
                    print 'state: ', sess.state
                    reconnect = True
            if reconnect:
                print 'reconnect', sess 
                udp_session.add_pending_outbox_file(sys.argv[1]+'.signed', sys.argv[2], 'descr', Deferred(), False)
                udp_node.A('connect', sys.argv[2])
            reactor.callLater(0.5, _try_reconnect)
        def _try_connect():
            if udp_node.A().state == 'LISTEN':
                print 'connect'
                gate.stop_packets_timeout_loop()
                udp_session.add_pending_outbox_file(sys.argv[1]+'.signed', sys.argv[2], 'descr', Deferred(), False)
                udp_node.A('connect', sys.argv[2])
                reactor.callLater(5, _try_reconnect)
            else:
                reactor.callLater(1, _try_connect)
        _try_connect()
    reactor.run()
    
        
if __name__ == '__main__':
    main()
    
        