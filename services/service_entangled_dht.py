#!/usr/bin/python
# service_entangled_dht.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (service_entangled_dht.py) is part of BitDust Software.
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

module:: service_entangled_dht
"""

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return EntangledDHTService()


class EntangledDHTService(LocalService):

    service_name = 'service_entangled_dht'
    config_path = 'services/entangled-dht/enabled'

    def dependent_on(self):
        return [
            'service_udp_datagrams',
        ]

    def start(self):
        from logs import lg
        from dht import dht_service
        from dht import known_nodes
        from main import settings
        from main.config import conf
        from userid import my_id
        conf().addCallback('services/entangled-dht/udp-port', self._on_udp_port_modified)
        dht_service.init(udp_port=settings.getDHTPort(), db_file_path=settings.DHTDBFile())
        known_seeds = known_nodes.nodes()
        lg.info('known seed nodes are : %r' % known_seeds)        
        d = dht_service.connect(seed_nodes=known_seeds)
        d.addCallback(self._on_connected)
        d.addErrback(self._on_connect_failed)
        if my_id.getLocalID():
            dht_service.set_node_data('idurl', my_id.getLocalID())
        return d

    def stop(self):
        from dht import dht_service
        from main.config import conf
        dht_service.node().remove_rpc_callback('request')
        dht_service.node().remove_rpc_callback('store')
        conf().removeCallback('services/entangled-dht/udp-port')
        dht_service.disconnect()
        dht_service.shutdown()
        return True

    def health_check(self):
        return True

    def _on_connected(self, nodes):
        from dht import dht_service
        from logs import lg
        lg.out(self.debug_level, 'service_entangled_dht._on_connected    nodes: %r' % nodes)
        lg.out(self.debug_level, '        DHT node is active, ID=[%s]' % dht_service.node().id)
        dht_service.node().add_rpc_callback('store', self._on_dht_rpc_store)
        dht_service.node().add_rpc_callback('request', self._on_dht_rpc_request)
        return nodes

    def _on_connect_failed(self, err):
        from logs import lg
        lg.out(self.debug_level, 'service_entangled_dht._on_connect_failed : %r' % err)
        return err

    def _on_udp_port_modified(self, path, value, oldvalue, result):
        from p2p import network_connector
        from logs import lg
        lg.out(2, 'service_entangled_dht._on_udp_port_modified %s->%s : %s' % (
            oldvalue, value, path))
        if network_connector.A():
            network_connector.A('reconnect')

    def _on_dht_rpc_store(self, key, value, originalPublisherID, age, expireSeconds, **kwargs):
        from dht import dht_service
        return dht_service.validate_before_store(key, value, originalPublisherID, age, expireSeconds, **kwargs)
    
    def _on_dht_rpc_request(self, key, **kwargs):
        from dht import dht_service
        return dht_service.validate_before_request(key, **kwargs)
