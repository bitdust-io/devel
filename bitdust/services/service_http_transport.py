#!/usr/bin/python
# service_http_transport.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (service_http_transport.py) is part of BitDust Software.
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

module:: service_http_transport
"""

from __future__ import absolute_import
from bitdust.services.local_service import LocalService


def create_service():
    return HTTPTransportService()


class HTTPTransportService(LocalService):

    service_name = 'service_http_transport'
    config_path = 'services/http-transport/enabled'
    proto = 'http'

    def enabled(self):
        # TODO: development just started... service disabled at the moment
        return False

    def dependent_on(self):
        return [
            'service_http_connections',
            'service_gateway',
        ]

    def installed(self):
        # TODO: to be continue...
        return False

    def start(self):
        from twisted.internet import reactor  # @UnresolvedImport
        from twisted.internet.defer import Deferred
        from bitdust.transport.http import http_interface
        from bitdust.transport import network_transport
        from bitdust.transport import gateway
        from bitdust.main.config import conf
        self.starting_deferred = Deferred()
        self.transport = network_transport.NetworkTransport('http', http_interface.GateInterface())
        self.transport.automat('init', (gateway.listener(), self._on_transport_state_changed))
        reactor.callLater(0, self.transport.automat, 'start')  # @UndefinedVariable
        conf().addConfigNotifier('services/http-transport/enabled', self._on_enabled_disabled)
        conf().addConfigNotifier('services/http-transport/receiving-enabled', self._on_receiving_enabled_disabled)
        return self.starting_deferred

    def stop(self):
        from bitdust.main.config import conf
        conf().removeConfigNotifier('services/http-transport/enabled')
        conf().removeConfigNotifier('services/http-transport/receiving-enabled')
        t = self.transport
        self.transport = None
        t.automat('shutdown')
        return True

    def _on_transport_state_changed(self, transport, oldstate, newstate):
        from bitdust.logs import lg
        lg.info('%s -> %s in %r  starting_deferred=%r' % (oldstate, newstate, transport, bool(self.starting_deferred)))
        if self.starting_deferred:
            if newstate in [
                'LISTENING',
            ]:
                self.starting_deferred.callback(newstate)
                self.starting_deferred = None
            elif newstate in [
                'OFFLINE',
            ]:
                self.starting_deferred.errback(Exception(newstate))
                self.starting_deferred = None

    def _on_enabled_disabled(self, path, value, oldvalue, result):
        from bitdust.p2p import network_connector
        from bitdust.logs import lg
        lg.out(2, 'service_http_transport._on_enabled_disabled : %s->%s : %s' % (oldvalue, value, path))
        network_connector.A('reconnect')

    def _on_receiving_enabled_disabled(self, path, value, oldvalue, result):
        from bitdust.p2p import network_connector
        from bitdust.logs import lg
        lg.out(2, 'service_http_transport._on_receiving_enabled_disabled : %s->%s : %s' % (oldvalue, value, path))
        network_connector.A('reconnect')
