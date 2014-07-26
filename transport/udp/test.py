
import os
import sys

from twisted.internet import reactor
from twisted.internet.defer import Deferred

sys.path.append(os.path.abspath('../..'))

from logs import lg

from lib import misc
from lib import settings
from lib import nameurl
from lib import udp

from dht import dht_service

import udp_node
import udp_session

#------------------------------------------------------------------------------ 

def main():
    lg.set_debug_level(24)
    options = { 'idurl': misc.getLocalID(),}
    options['host'] = nameurl.GetName(misc.getLocalID())+'@'+'somehost.org'
    options['dht_port'] = int(settings.getDHTPort())
    options['udp_port'] = int(settings.getUDPPort())
    dht_service.init(int(settings.getDHTPort()))
    dht_service.connect()
    udp.listen(int(settings.getUDPPort())) 
    udp_node.A('go-online', options)
    if len(sys.argv) > 3:
        udp_session.add_pending_outbox_file(sys.argv[1], sys.argv[2], 'descr', Deferred(), False)
        udp_node.A('connect', sys.argv[2])
    reactor.run()
    
if __name__ == '__main__':
    main()
    
        