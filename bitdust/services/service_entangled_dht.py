#!/usr/bin/python
# service_entangled_dht.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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
from bitdust.services.local_service import LocalService


def create_service():
    return EntangledDHTService()


class EntangledDHTService(LocalService):

    service_name = 'service_entangled_dht'
    config_path = 'services/entangled-dht/enabled'
    start_suspended = True

    def dependent_on(self):
        return [
            'service_udp_datagrams',
        ]

    def network_configuration(self):
        import re
        from bitdust.main import config
        from bitdust_forks.entangled.kademlia import constants  # @UnresolvedImport
        from bitdust.main import network_config
        network_info = network_config.read_network_config_file()
        known_dht_nodes_str = config.conf().getString('services/entangled-dht/known-nodes').strip()
        known_dht_nodes = []
        if known_dht_nodes_str:
            for dht_node_str in re.split('\n|;|,| ', known_dht_nodes_str):
                if dht_node_str.strip():
                    try:
                        dht_node = dht_node_str.strip().split(':')
                        dht_node_host = dht_node[0].strip()
                        dht_node_port = int(dht_node[1].strip())
                    except:
                        continue
                    known_dht_nodes.append({
                        'host': dht_node_host,
                        'udp_port': dht_node_port,
                    })
        if not known_dht_nodes:
            known_dht_nodes = network_info['service_entangled_dht']['known_nodes']
        return {
            'bucket_size': constants.k,
            'default_age': constants.dataExpireSecondsDefaut,
            'max_age': constants.dataExpireTimeout,
            'parallel_calls': constants.alpha,
            'refresh_timeout': constants.refreshTimeout,
            'rpc_timeout': constants.rpcTimeout,
            'known_nodes': known_dht_nodes,
        }

    def start(self):
        from twisted.internet.defer import Deferred, succeed
        from bitdust.logs import lg
        from bitdust.dht import dht_records
        from bitdust.dht import dht_service
        from bitdust.dht import known_nodes
        from bitdust.main import settings
        from bitdust.main.config import conf
        conf().addConfigNotifier('services/entangled-dht/udp-port', self._on_udp_port_modified)
        known_seeds = known_nodes.nodes()
        dht_layers = list(dht_records.LAYERS_REGISTRY.keys())
        dht_service.init(
            udp_port=settings.getDHTPort(),
            dht_dir_path=settings.ServiceDir('service_entangled_dht'),
            open_layers=dht_layers,
        )
        lg.info('DHT known seed nodes are : %r   DHT layers are : %r' % (known_seeds, dht_layers))
        self.starting_deferred = Deferred()
        d = dht_service.connect(
            seed_nodes=known_seeds,
            layer_id=0,
            attach=True,
        )
        d.addCallback(self._on_connected)
        d.addErrback(self._on_connect_failed)
        return self.starting_deferred or succeed(True)

    def stop(self):
        from bitdust.dht import dht_records
        from bitdust.dht import dht_service
        from bitdust.main.config import conf
        for layer_id in dht_records.LAYERS_REGISTRY.keys():
            dht_service.close_layer(layer_id)
        dht_service.node().remove_rpc_callback('request')
        dht_service.node().remove_rpc_callback('store')
        conf().removeConfigNotifier('services/entangled-dht/udp-port')
        dht_service.disconnect()
        dht_service.shutdown()
        return True

    def on_suspend(self, *args, **kwargs):
        from bitdust.dht import dht_service
        dht_service.disconnect()
        return True

    def on_resume(self, *args, **kwargs):
        from bitdust.dht import dht_service
        dht_service.reconnect()
        return True

    def health_check(self):
        return True

    def _on_connected(self, ok):
        from twisted.internet.defer import DeferredList
        from bitdust.logs import lg
        from bitdust.dht import dht_service
        from bitdust.dht import known_nodes
        from bitdust.main.config import conf
        from bitdust.services import driver
        lg.info('DHT node connected    ID0=[%s] : %r' % (dht_service.node().layers[0], ok))
        dht_service.node().add_rpc_callback('store', self._on_dht_rpc_store)
        dht_service.node().add_rpc_callback('request', self._on_dht_rpc_request)
        known_seeds = known_nodes.nodes()
        dl = []
        attached_layers = conf().getString('services/entangled-dht/attached-layers', default='')
        if attached_layers:
            attached_layers = list(filter(None, map(lambda v: int(str(v).strip()), attached_layers.split(','))))
        else:
            attached_layers = []
        lg.info('reading attached DHT layers from configuration: %r' % attached_layers)
        all_services_attached_layers = driver.get_attached_dht_layers().values()
        combined_services_attached_layers = set()
        count_combined = len(list(map(combined_services_attached_layers.update, all_services_attached_layers)))
        services_attached_layers = list(combined_services_attached_layers)
        lg.info('combined attached DHT layers from %d services: %r' % (count_combined, services_attached_layers))
        attached_layers = list(set(attached_layers + services_attached_layers))
        lg.info('DHT layers to be attached at startup: %r' % attached_layers)
        for layer_id in attached_layers:
            dl.append(dht_service.open_layer(
                layer_id=layer_id,
                seed_nodes=known_seeds,
                connect_now=True,
                attach=True,
            ))
        if dl:
            d = DeferredList(dl)
            d.addCallback(self._on_layers_attached)
            d.addErrback(self._on_connect_failed)
        else:
            if self.starting_deferred and not self.starting_deferred.called:
                self.starting_deferred.callback(True)
        return ok

    def _on_layers_attached(self, ok):
        if self.starting_deferred and not self.starting_deferred.called:
            self.starting_deferred.callback(True)
        return ok

    def _on_connect_failed(self, err):
        from bitdust.logs import lg
        lg.err('DHT connect failed : %r' % err)
        if self.starting_deferred and not self.starting_deferred.called:
            self.starting_deferred.errback(err)
        return err

    def _on_udp_port_modified(self, path, value, oldvalue, result):
        from bitdust.p2p import network_connector
        from bitdust.logs import lg
        lg.info('DHT udp port modified %s->%s : %s' % (oldvalue, value, path))
        if network_connector.A():
            network_connector.A('reconnect')

    def _on_dht_rpc_store(self, key, value, originalPublisherID, age, expireSeconds, **kwargs):
        from bitdust.dht import dht_service
        return dht_service.validate_before_store(key, value, originalPublisherID, age, expireSeconds, **kwargs)

    def _on_dht_rpc_request(self, key, **kwargs):
        from bitdust.dht import dht_service
        return dht_service.validate_before_request(key, **kwargs)
