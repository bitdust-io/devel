#!/usr/bin/python
#service_proxy_transport.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
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
.. module:: service_proxy_transport

"""

from services.local_service import LocalService

def create_service():
    return ProxyTransportService()
    
class ProxyTransportService(LocalService):
    
    service_name = 'service_proxy_transport'
    config_path = 'services/proxy-transport/enabled'
    proto = 'proxy'
    
    def dependent_on(self):
        from main import settings
        depends = ['service_identity_propagate', 
                   'service_entangled_dht',]
        if settings.enableTCP():
            depends.append('service_tcp_transport')
        if settings.enableUDP():
            depends.append('service_udp_transport')
        return depends

    def start(self):
        from twisted.internet import reactor
        from twisted.internet.defer import Deferred
        from transport.proxy import proxy_interface
        from transport import network_transport
        from transport import gateway
        from main.config import conf
        if not self._check_update_current_router():
            return False
        self.starting_deferred = Deferred()
        self.interface = proxy_interface.GateInterface()
        self.transport = network_transport.NetworkTransport(
            'proxy', self.interface)
        self.transport.automat('init',
            (gateway.listener(), self._on_transport_state_changed))
        reactor.callLater(0, self.transport.automat, 'start')
        conf().addCallback('services/proxy-transport/enabled', 
                           self._on_enabled_disabled)
        conf().addCallback('services/proxy-transport/sending-enabled', 
                           self._on_sending_enabled_disabled)
        conf().addCallback('services/proxy-transport/receiving-enabled', 
                           self._on_receiving_enabled_disabled)
        return self.starting_deferred
    
    def stop(self):
        from main.config import conf
        conf().removeCallback('services/proxy-transport/enabled') 
        conf().removeCallback('services/proxy-transport/sending-enabled') 
        conf().removeCallback('services/proxy-transport/receiving-enabled') 
        t = self.transport
        self.transport = None
        self.interface = None
        t.automat('shutdown')
        return True
    
    def installed(self):
        try:
            from transport.proxy import proxy_interface
        except:
            from logs import lg
            lg.exc()
            return False
        return True

    def _check_update_current_router(self):
        from main.config import conf
        from logs import lg
        orig_ident = conf().getData('services/proxy-transport/my-original-identity').strip() != ''
        current_router = conf().getString('services/proxy-transport/current-router').strip() != ''
        if (current_router and not orig_ident) or (not current_router and orig_ident):
            lg.warn('current-router: %s, my-original-identity: %s' % (
                current_router, orig_ident, ))
            conf().setData('services/proxy-transport/my-original-identity', '') 
            conf().setString('services/proxy-transport/current-router', '')
            return False
        return True

    def _on_transport_state_changed(self, transport, oldstate, newstate):
        if self.starting_deferred:
            if newstate in ['LISTENING', 'OFFLINE',]:
                self.starting_deferred.callback(newstate)
                self.starting_deferred = None
        if newstate == 'LISTENING':
            from p2p import p2p_connector
            p2p_connector.A('check-synchronize')
            
    def _on_enabled_disabled(self, path, value, oldvalue, result):
        from p2p import p2p_connector
        p2p_connector.A('check-synchronize')
        
    def _on_receiving_enabled_disabled(self, path, value, oldvalue, result):
        from p2p import p2p_connector
        p2p_connector.A('check-synchronize')
        
    def _on_sending_enabled_disabled(self, path, value, oldvalue, result):
        from p2p import p2p_connector
        p2p_connector.A('check-synchronize')

