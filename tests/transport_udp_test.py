#!/usr/bin/env python
# transport_udp_test.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (transport_udp_test.py) is part of BitDust Software.
#
# BitDust is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BitDust Software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with BitDust Software.  If not, see <http://www.gnu.org/licenses/>.
#
# Please contact us if you have any questions at bitdust.io@gmail.com

import os
import sys

from twisted.internet import reactor
from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(
        0, _p.abspath(
            _p.join(
                _p.dirname(
                    _p.abspath(
                        sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg
from userid import my_id
from lib import misc
from main import settings
from lib import nameurl
from lib import udp
from system import bpio
from p2p import commands
from crypt import signed
from dht import dht_service
from transport.udp import udp_node
from transport.udp import udp_session
from transport import gateway

#------------------------------------------------------------------------------


def main():
    lg.set_debug_level(24)
    lg.life_begins()
    from crypt import key
    key.InitMyKey()
    from contacts import identitycache
    identitycache.init()
    from system import tmpfile
    tmpfile.init()
    # options = { 'idurl': my_id.getLocalID(),}
    # options['host'] = nameurl.GetName(my_id.getLocalID())+'@'+'somehost.org'
    # options['dht_port'] = int(settings.getDHTPort())
    # options['udp_port'] = int(settings.getUDPPort())
    udp.listen(int(settings.getUDPPort()))
    dht_service.init(settings.getDHTPort())
    # dht_service.connect()
    # udp_node.A('go-online', options)
    reactor.addSystemEventTrigger('before', 'shutdown', gateway.shutdown)
    gateway.init()
    gateway.start()
    # [filename] [peer idurl]
    if len(sys.argv) >= 3:
        p = signed.Packet(commands.Data(), my_id.getLocalID(),
                          my_id.getLocalID(), my_id.getLocalID(),
                          bpio.ReadBinaryFile(sys.argv[1]), sys.argv[2])
        # bpio.WriteFile(sys.argv[1]+'.signed', p.Serialize())

        def _try_reconnect():
            sess = udp_session.get_by_peer_id(sys.argv[2])
            reconnect = False
            if not sess:
                reconnect = True
                print 'sessions', udp_session.sessions_by_peer_id().keys()
                print map(lambda s: s.peer_id, udp_session.sessions().values())
            else:
                if sess.state != 'CONNECTED':
                    print 'state: ', sess.state
                    reconnect = True
            if reconnect:
                print 'reconnect', sess
                udp_session.add_pending_outbox_file(
                    sys.argv[1] + '.signed', sys.argv[2], 'descr', Deferred(), False)
                udp_node.A('connect', sys.argv[2])
            reactor.callLater(0.5, _try_reconnect)

        def _try_connect():
            if udp_node.A().state == 'LISTEN':
                print 'connect'
                gateway.stop_packets_timeout_loop()
                udp_session.add_pending_outbox_file(
                    sys.argv[1] + '.signed', sys.argv[2], 'descr', Deferred(), False)
                udp_node.A('connect', sys.argv[2])
                reactor.callLater(5, _try_reconnect)
            else:
                reactor.callLater(1, _try_connect)
        # _try_connect()

        def _send(c):
            from transport.udp import udp_stream
            print '_send', udp_stream.streams().keys()
            gateway.outbox(p)
            # if c < 20:
            #     reactor.callLater(0.01, _send, c+1)
        reactor.callLater(10, _send, 0)
    reactor.run()


if __name__ == '__main__':
    main()
