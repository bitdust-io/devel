#!/usr/bin/python
# service_proxy_transport.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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
from services.local_service import LocalService


def create_service():
    return ProxyTransportService()


class ProxyTransportService(LocalService):

    service_name = 'service_proxy_transport'
    config_path = 'services/proxy-transport/enabled'
    proto = 'proxy'

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
        from logs import lg
        from transport.proxy import proxy_interface
        from transport import network_transport
        from transport import gateway
        from main.config import conf
        if len(self._available_transports()) == 0:
            lg.warn('no transports available')
            return False
        self._check_reset_original_identity()
        self.starting_deferred = Deferred()
        self.transport = network_transport.NetworkTransport('proxy', proxy_interface.GateInterface())
        self.transport.automat(
            'init', (gateway.listener(), self._on_transport_state_changed))
        reactor.callLater(0, self.transport.automat, 'start')  # @UndefinedVariable
        conf().addCallback('services/proxy-transport/enabled',
                           self._on_enabled_disabled)
        conf().addCallback('services/proxy-transport/sending-enabled',
                           self._on_sending_enabled_disabled)
        conf().addCallback('services/proxy-transport/receiving-enabled',
                           self._on_receiving_enabled_disabled)
        return self.starting_deferred
        # return True

    def stop(self):
        from twisted.internet.defer import succeed
        from main.config import conf
        conf().removeCallback('services/proxy-transport/enabled')
        conf().removeCallback('services/proxy-transport/sending-enabled')
        conf().removeCallback('services/proxy-transport/receiving-enabled')
        t = self.transport
        self.transport = None
        t.automat('shutdown')
        return succeed(True)

    def installed(self):
        try:
            from transport.proxy import proxy_interface
        except:
            from logs import lg
            lg.exc()
            return False
        return True

    def _available_transports(self):
        from main import settings
        atransports = []
        if settings.enableTCP() and settings.enableTCPreceiving() and settings.enableTCPsending():
            atransports.append('service_tcp_transport')
        if settings.enableUDP() and settings.enableUDPreceiving() and settings.enableUDPsending():
            atransports.append('service_udp_transport')
        return atransports

    def _reset_my_original_identity(self, skip_transports=[]):
        # from userid import my_id
        from main.config import conf
        from logs import lg
        lg.warn('RESET my-original-identity')
        conf().setData('services/proxy-transport/my-original-identity', '')
        conf().setString('services/proxy-transport/current-router', '')
        # my_id.rebuildLocalIdentity(skip_transports=skip_transports)

    def _check_reset_original_identity(self):
        from logs import lg
        from lib import misc
        from lib import strng
        from main.config import conf
        from userid import identity
        from userid import my_id
        orig_ident_xmlsrc = conf().getData(
            'services/proxy-transport/my-original-identity', '').strip()
        current_router_idurl = conf().getString(
            'services/proxy-transport/current-router', '').strip()
        if current_router_idurl:
            current_router_idurl = strng.to_bin(current_router_idurl.split(' ')[0])
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
        if orig_ident.getIDURL() != my_id.getLocalID():
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

    def _on_transport_state_changed(self, transport, oldstate, newstate):
        from p2p import p2p_connector
        if self.starting_deferred:
            if newstate == 'LISTENING' and oldstate != 'LISTENING':
                self.starting_deferred.callback(newstate)
                self.starting_deferred = None
                p2p_connector.A('check-synchronize')
            if newstate == 'OFFLINE' and oldstate in ['STARTING', 'STOPPING', ]:
                self.starting_deferred.callback(newstate)
                self.starting_deferred = None
                p2p_connector.A('check-synchronize')

    def _on_enabled_disabled(self, path, value, oldvalue, result):
        from p2p import network_connector
        network_connector.A('reconnect')

    def _on_receiving_enabled_disabled(self, path, value, oldvalue, result):
        from p2p import network_connector
        network_connector.A('reconnect')

    def _on_sending_enabled_disabled(self, path, value, oldvalue, result):
        from p2p import network_connector
        network_connector.A('reconnect')
