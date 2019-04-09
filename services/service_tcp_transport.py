#!/usr/bin/python
# service_tcp_transport.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (service_tcp_transport.py) is part of BitDust Software.
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

module:: service_tcp_transport
"""

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return TCPTransportService()


class TCPTransportService(LocalService):

    service_name = 'service_tcp_transport'
    config_path = 'services/tcp-transport/enabled'
    proto = 'tcp'

    def dependent_on(self):
        return [
            'service_tcp_connections',
            'service_gateway',
        ]

    def start(self):
        from twisted.internet import reactor  # @UnresolvedImport
        from twisted.internet.defer import Deferred
        from transport.tcp import tcp_interface
        from transport import network_transport
        from transport import gateway
        from main.config import conf
        self.starting_deferred = Deferred()
        self.interface = tcp_interface.GateInterface()
        self.transport = network_transport.NetworkTransport('tcp', self.interface)
        self.transport.automat(
            'init', (gateway.listener(), self._on_transport_state_changed))
        reactor.callLater(0, self.transport.automat, 'start')  # @UndefinedVariable
        conf().addCallback('services/tcp-transport/enabled',
                           self._on_enabled_disabled)
        conf().addCallback('services/tcp-transport/receiving-enabled',
                           self._on_receiving_enabled_disabled)
        return self.starting_deferred

    def stop(self):
        from main.config import conf
        conf().removeCallback('services/tcp-transport/enabled')
        conf().removeCallback('services/tcp-transport/receiving-enabled')
        t = self.transport
        self.transport = None
        t.automat('shutdown')
        return True

    def installed(self):
        from logs import lg
        try:
            from transport.tcp import tcp_interface
        except:
            lg.exc()
            return False
        return True

    def _on_transport_state_changed(self, transport, oldstate, newstate):
        if self.starting_deferred:
            if newstate in ['LISTENING', 'OFFLINE', ]:
                self.starting_deferred.callback(newstate)
                self.starting_deferred = None
#        if self.transport:
#            from p2p import network_connector
#            network_connector.A('network-transport-state-changed', self.transport)

    def _on_enabled_disabled(self, path, value, oldvalue, result):
        from p2p import network_connector
        from logs import lg
        lg.out(2, 'service_tcp_transport._on_enabled_disabled : %s->%s : %s' % (
            oldvalue, value, path))
        network_connector.A('reconnect')

    def _on_receiving_enabled_disabled(self, path, value, oldvalue, result):
        from p2p import network_connector
        from logs import lg
        lg.out(2, 'service_tcp_transport._on_receiving_enabled_disabled : %s->%s : %s' % (
            oldvalue, value, path))
        network_connector.A('reconnect')
