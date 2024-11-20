#!/usr/bin/python
# service_web_socket_communicator.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (service_web_socket_communicator.py) is part of BitDust Software.
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
#
#
#
#
"""
..

module:: service_web_socket_communicator
"""

from __future__ import absolute_import
from bitdust.services.local_service import LocalService


def create_service():
    return WebSocketCommunicatorService()


class WebSocketCommunicatorService(LocalService):

    service_name = 'service_web_socket_communicator'
    config_path = 'services/web-socket-communicator/enabled'

    def dependent_on(self):
        return [
            'service_nodes_lookup',
        ]

    def start(self):
        from twisted.internet.defer import Deferred
        from bitdust.logs import lg
        from bitdust.services import driver
        from bitdust.main import events
        self.starting_deferred = Deferred()
        # self.starting_deferred.addErrback(lambda err: lg.warn('service %r was not started: %r' % (self.service_name, err.getErrorMessage() if err else 'unknown reason')))
        events.add_subscriber(self._on_dht_layer_connected, 'dht-layer-connected')
        if driver.is_on('service_entangled_dht'):
            self._do_join_web_socket_routers_dht_layer()
        return self.starting_deferred

    def stop(self):
        from twisted.internet.defer import succeed
        from bitdust.main import events
        events.remove_subscriber(self._on_dht_layer_connected, 'dht-layer-connected')
        return succeed(True)

    def _do_join_web_socket_routers_dht_layer(self):
        from bitdust.logs import lg
        from bitdust.dht import dht_service
        from bitdust.dht import dht_records
        from bitdust.dht import known_nodes
        lg.info('going to join web socket routers DHT layer: %d' % dht_records.LAYER_WEB_SOCKET_ROUTERS)
        known_seeds = known_nodes.nodes()
        d = dht_service.open_layer(
            layer_id=dht_records.LAYER_WEB_SOCKET_ROUTERS,
            seed_nodes=known_seeds,
            connect_now=True,
            attach=False,
        )
        d.addCallback(self._on_web_socket_routers_dht_layer_connected)
        d.addErrback(self._on_web_socket_routers_dht_layer_connect_failed)

    def _on_web_socket_routers_dht_layer_connected(self, ok):
        from bitdust.logs import lg
        from bitdust.interface import api_device
        lg.info('connected to DHT layer for web socket routers: %r' % ok)
        if ok:
            self.starting_deferred.callback(True)
        else:
            self.starting_deferred.errback(Exception('was not able to connect to web socket routers DHT layer'))
        self.starting_deferred = None
        if ok:
            api_device.start_routed_devices()
        return ok

    def _on_web_socket_routers_dht_layer_connect_failed(self, err):
        from bitdust.logs import lg
        lg.err('failed to connect to DHT layer for web socket routers: %r' % err)
        self.starting_deferred.errback(err)
        self.starting_deferred = None
        return None

    def _on_dht_layer_connected(self, evt):
        if evt.data['layer_id'] == 0:
            self._do_join_web_socket_routers_dht_layer()
