#!/usr/bin/env python
# transport_udp_test.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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

from __future__ import absolute_import
import os
import sys

from twisted.internet import reactor  # @UnresolvedImport

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from bitdust.logs import lg
from bitdust.system import bpio
from bitdust.transport import gateway

#------------------------------------------------------------------------------


def main():
    lg.set_debug_level(18)
    lg.life_begins()
    from bitdust.crypt import key
    key.InitMyKey()
    from bitdust.contacts import identitycache
    identitycache.init()
    from bitdust.system import tmpfile
    tmpfile.init()
    from bitdust.services import driver

    required_services = [
        'service_http_connections',
        'service_http_transport',
        'service_gateway',
        'service_network',
    ]
    available_services_dir = os.path.join(bpio.getExecutableDir(), 'services')
    for filename in os.listdir(available_services_dir):
        if not filename.endswith('.py') and not filename.endswith('.pyo') and not filename.endswith('.pyc'):
            continue
        if not filename.startswith('service_'):
            continue
        name = str(filename[:filename.rfind('.')])
        if name in required_services:
            continue
        driver.disabled_services().add(name)
    driver.init()
    driver.enabled_services().clear()
    driver.enabled_services().add('service_http_transport')
    driver.enabled_services().add('service_http_connections')
    driver.enabled_services().add('service_gateway')
    driver.enabled_services().add('service_network')
    driver.start()
    # options = { 'idurl': my_id.getIDURL(),}
    # options['host'] = nameurl.GetName(my_id.getIDURL())+'@'+'somehost.org'
    # options['dht_port'] = int(settings.getDHTPort())
    # options['udp_port'] = int(settings.getUDPPort())
    # udp.listen(int(settings.getUDPPort()))
    # dht_service.init(settings.getDHTPort())
    # dht_service.connect()
    # udp_node.A('go-online', options)
    reactor.addSystemEventTrigger('before', 'shutdown', gateway.shutdown)
    gateway.init()
    gateway.start()

    def _ok_to_send(transport, oldstate, newstate):
        if newstate != 'LISTENING':
            return
        # [filename] [peer idurl]
        if len(sys.argv) >= 3:
            pass
            # bpio.WriteFile(sys.argv[1]+'.signed', p.Serialize())


#             def _try_reconnect():
#                 sess = udp_session.get_by_peer_id(sys.argv[2])
#                 reconnect = False
#                 if not sess:
#                     reconnect = True
#                     print 'sessions', udp_session.sessions_by_peer_id().keys()
#                     print map(lambda s: s.peer_id, udp_session.sessions().values())
#                 else:
#                     if sess.state != 'CONNECTED':
#                         print 'state: ', sess.state
#                         reconnect = True
#                 if reconnect:
#                     print 'reconnect', sess
#                     udp_session.add_pending_outbox_file(
#                         sys.argv[1] + '.signed', sys.argv[2], 'descr', Deferred(), False)
#                     udp_node.A('connect', sys.argv[2])
#                 reactor.callLater(0.5, _try_reconnect)
#
#             def _try_connect():
#                 if udp_node.A().state == 'LISTEN':
#                     print 'connect'
#                     gateway.stop_packets_timeout_loop()
#                     udp_session.add_pending_outbox_file(
#                         sys.argv[1] + '.signed', sys.argv[2], 'descr', Deferred(), False)
#                     udp_node.A('connect', sys.argv[2])
#                     reactor.callLater(5, _try_reconnect)
#                 else:
#                     reactor.callLater(1, _try_connect)
#             # _try_connect()
#
#             def _send(c):
#                 from bitdust.transport.udp import udp_stream
#                 for idurl in sys.argv[2:]:
#                     print '_send', udp_stream.streams().keys()
#                     p = signed.Packet(commands.Data(),
#                                       my_id.getIDURL(),
#                                       my_id.getIDURL(),
#                                       'packet%d' % c,
#                                       bpio.ReadBinaryFile(sys.argv[1]),
#                                       idurl)
#                     gateway.outbox(p)
#                 if c > 1:
#                     reactor.callLater(0.01, _send, c - 1)
#             reactor.callLater(0, _send, 15)

    gateway.add_transport_state_changed_callback(_ok_to_send)
    reactor.run()

if __name__ == '__main__':
    main()
