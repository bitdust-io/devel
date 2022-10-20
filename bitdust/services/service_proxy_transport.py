#!/usr/bin/python
# service_proxy_transport.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (service_proxy_transport.py) is part of BitDust Software.
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

module:: service_proxy_transport
"""

from __future__ import absolute_import
from bitdust.services.local_service import LocalService


def create_service():
    return ProxyTransportService()


class ProxyTransportService(LocalService):

    service_name = 'service_proxy_transport'
    config_path = 'services/proxy-transport/enabled'
    proto = 'proxy'
    transport = None
    stop_when_failed = True

    def init(self):
        self.starting_deferred = None

    def dependent_on(self):
        depends = [
            'service_identity_propagate',
            'service_nodes_lookup',
        ]
        depends.extend(self._available_transports())
        return depends

    def start(self):
        from twisted.internet import reactor  # @UnresolvedImport
        from twisted.internet.defer import Deferred
        from bitdust.logs import lg
        from bitdust.transport.proxy import proxy_interface
        from bitdust.transport import network_transport
        from bitdust.transport import gateway
        from bitdust.services import driver
        from bitdust.main import events
        from bitdust.main.config import conf
        if len(self._available_transports()) == 0:
            lg.warn('no transports available')
            return False
        events.add_subscriber(self._on_dht_layer_connected, 'dht-layer-connected')
        self._check_reset_original_identity()
        self.starting_deferred = Deferred()
        self.transport = network_transport.NetworkTransport('proxy', proxy_interface.GateInterface())
        conf().addConfigNotifier('services/proxy-transport/enabled', self._on_enabled_disabled)
        conf().addConfigNotifier('services/proxy-transport/sending-enabled', self._on_sending_enabled_disabled)
        conf().addConfigNotifier('services/proxy-transport/receiving-enabled', self._on_receiving_enabled_disabled)
        if driver.is_on('service_entangled_dht'):
            self._do_join_proxy_routers_dht_layer()
        else:
            self.transport.automat('init', (gateway.listener(), self._on_transport_state_changed))
            reactor.callLater(0, self.transport.automat, 'start')  # @UndefinedVariable
        return self.starting_deferred

    def stop(self):
        from twisted.internet.defer import succeed
        from bitdust.main import events
        from bitdust.main.config import conf
        events.remove_subscriber(self._on_dht_layer_connected, 'dht-layer-connected')
        conf().removeConfigNotifier('services/proxy-transport/enabled')
        conf().removeConfigNotifier('services/proxy-transport/sending-enabled')
        conf().removeConfigNotifier('services/proxy-transport/receiving-enabled')
        t = self.transport
        self.transport = None
        t.automat('shutdown')
        return succeed(True)

    def installed(self):
        try:
            from bitdust.transport.proxy import proxy_interface
        except:
            from bitdust.logs import lg
            lg.exc()
            return False
        return True

    def health_check(self):
        from bitdust.services import driver
        all_deps_are_ok = True
        for dep_name in self.dependent_on():
            if not driver.is_enabled(dep_name):
                all_deps_are_ok = False
                break
            if not driver.is_on(dep_name):
                all_deps_are_ok = False
                break
        if not all_deps_are_ok:
            return False
        return self.state == 'ON'

    def _available_transports(self):
        from bitdust.main import settings
        atransports = []
        if settings.enableTCP() and settings.enableTCPreceiving() and settings.enableTCPsending():
            atransports.append('service_tcp_transport')
        if settings.enableUDP() and settings.enableUDPreceiving() and settings.enableUDPsending():
            atransports.append('service_udp_transport')
        return atransports

    def _reset_my_original_identity(self):
        from bitdust.userid import my_id
        from bitdust.main.config import conf
        from bitdust.logs import lg
        lg.warn('RESET my-original-identity')
        conf().setData('services/proxy-transport/my-original-identity', '')
        conf().setString('services/proxy-transport/current-router', '')
        my_id.rebuildLocalIdentity()

    def _check_reset_original_identity(self):
        from bitdust.logs import lg
        from bitdust.lib import misc
        from bitdust.lib import strng
        from bitdust.main.config import conf
        from bitdust.userid import identity
        from bitdust.userid import my_id
        from bitdust.userid import id_url
        orig_ident_xmlsrc = conf().getData('services/proxy-transport/my-original-identity', '').strip()
        current_router_idurl = conf().getString('services/proxy-transport/current-router', '').strip()
        if current_router_idurl:
            current_router_idurl = id_url.field(current_router_idurl.split(' ')[0])
        if not orig_ident_xmlsrc:
            if current_router_idurl:
                lg.warn('"current-router" is %s, but "my-original-identity" is empty' % current_router_idurl)
            else:
                lg.warn('"current-router" and "my-original-identity" is empty')
            self._reset_my_original_identity()
            return
        orig_ident = identity.identity(xmlsrc=orig_ident_xmlsrc)
        if not orig_ident.isCorrect() or not orig_ident.Valid():
            lg.warn('"my-original-identity" config has not valid value')
            self._reset_my_original_identity()
            return
        if orig_ident.getIDURL() != my_id.getIDURL():
            lg.warn('"my-original-identity" source is not equal to local identity source')
            self._reset_my_original_identity()
            return
        externalIP = strng.to_bin(misc.readExternalIP())
        if externalIP and strng.to_bin(orig_ident.getIP()) != externalIP:
            lg.warn('external IP was changed : reset "my-original-identity" config')
            self._reset_my_original_identity()
            return
        if not current_router_idurl:
            lg.warn('"my-original-identity" config is correct, but current router is empty')
            self._reset_my_original_identity()
        all_orig_contacts_present_in_local_identity = True
        for orig_contact in orig_ident.getContacts():
            if orig_contact not in my_id.getLocalIdentity().getContacts():
                all_orig_contacts_present_in_local_identity = False
        if all_orig_contacts_present_in_local_identity:
            lg.warn('all of "my-original-identity" contacts is found in local identity: need to RESET!')
            self._reset_my_original_identity()

    def _do_join_proxy_routers_dht_layer(self):
        from bitdust.logs import lg
        from bitdust.dht import dht_service
        from bitdust.dht import dht_records
        from bitdust.dht import known_nodes
        lg.info('going to join proxy routers DHT layer: %d' % dht_records.LAYER_PROXY_ROUTERS)
        known_seeds = known_nodes.nodes()
        d = dht_service.open_layer(
            layer_id=dht_records.LAYER_PROXY_ROUTERS,
            seed_nodes=known_seeds,
            connect_now=True,
            attach=False,
        )
        d.addCallback(self._on_proxy_routers_dht_layer_connected)
        d.addErrback(self._on_proxy_routers_dht_layer_connect_failed)

    def _on_proxy_routers_dht_layer_connected(self, ok):
        from twisted.internet import reactor  # @UnresolvedImport
        from bitdust.logs import lg
        from bitdust.dht import dht_service
        from bitdust.dht import dht_records
        from bitdust.transport import gateway
        from bitdust.userid import my_id
        lg.info('connected to DHT layer for proxy routers: %r' % ok)
        if my_id.getIDURL():
            dht_service.set_node_data('idurl', my_id.getIDURL().to_text(), layer_id=dht_records.LAYER_PROXY_ROUTERS)
        if self.transport:
            if self.starting_deferred and not self.starting_deferred.called:
                self.transport.automat('init', (gateway.listener(), self._on_transport_state_changed))
                reactor.callLater(0, self.transport.automat, 'start')  # @UndefinedVariable
        return ok

    def _on_proxy_routers_dht_layer_connect_failed(self, err):
        from bitdust.logs import lg
        from bitdust.transport import gateway
        lg.err('failed to connect to DHT layer: %r' % err)
        if self.starting_deferred and not self.starting_deferred.called:
            self.transport.automat('init', (gateway.listener(), self._on_transport_state_changed))
            reactor.callLater(0, self.transport.automat, 'start')  # @UndefinedVariable

    def _on_transport_state_changed(self, transport, oldstate, newstate):
        from bitdust.logs import lg
        from bitdust.p2p import p2p_connector
        lg.info('%s -> %s in %r  starting_deferred=%r' % (oldstate, newstate, transport, bool(self.starting_deferred)))
        if self.starting_deferred:
            if newstate == 'LISTENING' and oldstate != newstate:
                self.starting_deferred.callback(True)
                self.starting_deferred = None
                p2p_connector.A('check-synchronize')
            if newstate == 'OFFLINE' and oldstate != newstate and oldstate not in [
                'INIT',
            ]:
                self.starting_deferred.errback(Exception(newstate))
                self.starting_deferred = None
                p2p_connector.A('check-synchronize')

    def _on_enabled_disabled(self, path, value, oldvalue, result):
        from bitdust.p2p import network_connector
        network_connector.A('reconnect')

    def _on_receiving_enabled_disabled(self, path, value, oldvalue, result):
        from bitdust.p2p import network_connector
        network_connector.A('reconnect')

    def _on_sending_enabled_disabled(self, path, value, oldvalue, result):
        from bitdust.p2p import network_connector
        network_connector.A('reconnect')

    def _on_dht_layer_connected(self, evt):
        from bitdust.dht import dht_records
        if evt.data['layer_id'] == 0:
            self._do_join_proxy_routers_dht_layer()
        elif evt.data['layer_id'] == dht_records.LAYER_PROXY_ROUTERS:
            self._on_proxy_routers_dht_layer_connected(True)
