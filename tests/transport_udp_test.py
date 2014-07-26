
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
        def _try_connect():
            if udp_node.A().state == 'LISTEN':
                udp_session.add_pending_outbox_file(sys.argv[1], sys.argv[2], 'descr', Deferred(), False)
                udp_node.A('connect', sys.argv[2])
            else:
                reactor.callLater(1, _try_connect)
        _try_connect()
    reactor.run()
    
        
if __name__ == '__main__':
    main()
    
        