#!/usr/bin/python
# service_web_socket_router.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (service_web_socket_router.py) is part of BitDust Software.
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

module:: service_web_socket_router
"""

from __future__ import absolute_import
from bitdust.services.local_service import LocalService


def create_service():
    return WebSocketRouterService()


class WebSocketRouterService(LocalService):

    service_name = 'service_web_socket_router'
    config_path = 'services/web-socket-router/enabled'

    def dependent_on(self):
        return [
            'service_p2p_hookups',
        ]

    def attached_dht_layers(self):
        from bitdust.dht import dht_records
        return [
            dht_records.LAYER_WEB_SOCKET_ROUTERS,
        ]

    def start(self):
        from bitdust.logs import lg
        from bitdust.services import driver
        from bitdust.main import events
        from bitdust.interface import web_socket_transmitter
        web_socket_transmitter.init()
        if driver.is_on('service_entangled_dht'):
            self._do_connect_web_socket_routers_dht_layer()
        else:
            lg.warn('service service_entangled_dht is OFF')
        events.add_subscriber(self._on_dht_layer_connected, 'dht-layer-connected')
        return True

    def stop(self):
        from bitdust.services import driver
        from bitdust.main import events
        from bitdust.interface import web_socket_transmitter
        events.remove_subscriber(self._on_dht_layer_connected, 'dht-layer-connected')
        if driver.is_on('service_entangled_dht'):
            from bitdust.dht import dht_service
            from bitdust.dht import dht_records
            dht_service.suspend(layer_id=dht_records.LAYER_WEB_SOCKET_ROUTERS)
        web_socket_transmitter.shutdown()
        return True

    def _do_connect_web_socket_routers_dht_layer(self):
        from bitdust.logs import lg
        from bitdust.dht import dht_service
        from bitdust.dht import dht_records
        from bitdust.dht import known_nodes
        known_seeds = known_nodes.nodes()
        d = dht_service.connect(
            seed_nodes=known_seeds,
            layer_id=dht_records.LAYER_WEB_SOCKET_ROUTERS,
            attach=True,
        )
        d.addCallback(self._on_dht_web_socket_routers_layer_connected)
        d.addErrback(lambda *args: lg.err(str(args)))

    def _on_dht_web_socket_routers_layer_connected(self, ok):
        from bitdust.logs import lg
        from bitdust.dht import dht_service
        from bitdust.dht import dht_records
        from bitdust.interface import web_socket_transmitter
        lg.info('connected to DHT layer for web socket routers: %r' % ok)
        dht_service.set_node_data('location', web_socket_transmitter.location(), layer_id=dht_records.LAYER_WEB_SOCKET_ROUTERS)
        return ok

    def _on_dht_layer_connected(self, evt):
        from bitdust.dht import dht_records
        if evt.data['layer_id'] == 0:
            self._do_connect_web_socket_routers_dht_layer()
        elif evt.data['layer_id'] == dht_records.LAYER_WEB_SOCKET_ROUTERS:
            self._on_dht_web_socket_routers_layer_connected(True)
