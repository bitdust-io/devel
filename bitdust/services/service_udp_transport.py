#!/usr/bin/python
# service_udp_transport.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (service_udp_transport.py) is part of BitDust Software.
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

module:: service_udp_transport
"""

from __future__ import absolute_import
from bitdust.services.local_service import LocalService


def create_service():
    return UDPTransportService()


class UDPTransportService(LocalService):

    service_name = 'service_udp_transport'
    config_path = 'services/udp-transport/enabled'
    proto = 'udp'
    stop_when_failed = True

    def dependent_on(self):
        return [
            'service_udp_datagrams',
            'service_my_ip_port',
            'service_gateway',
        ]

    def start(self):
        from twisted.internet import reactor  # @UnresolvedImport
        from twisted.internet.defer import Deferred
        from bitdust.transport.udp import udp_interface
        from bitdust.transport import network_transport
        from bitdust.transport import gateway
        from bitdust.main.config import conf
        self.starting_deferred = Deferred()
        self.transport = network_transport.NetworkTransport('udp', udp_interface.GateInterface())
        self.transport.automat('init', (gateway.listener(), self._on_transport_state_changed))
        reactor.callLater(0, self.transport.automat, 'start')  # @UndefinedVariable
        conf().addConfigNotifier('services/udp-transport/enabled', self._on_enabled_disabled)
        conf().addConfigNotifier('services/udp-transport/receiving-enabled', self._on_receiving_enabled_disabled)
        conf().addConfigNotifier('services/network/receive-limit', self._on_network_receive_limit_modified)
        conf().addConfigNotifier('services/network/send-limit', self._on_network_send_limit_modified)
        return self.starting_deferred

    def stop(self):
        from bitdust.main.config import conf
        conf().removeConfigNotifier('services/udp-transport/enabled')
        conf().removeConfigNotifier('services/udp-transport/receiving-enabled')
        conf().removeConfigNotifier('services/network/receive-limit')
        conf().removeConfigNotifier('services/network/send-limit')
        t = self.transport
        self.transport = None
        t.automat('shutdown')
        return True

    def installed(self):
        return False
        # from bitdust.logs import lg
        # try:
        #     from bitdust.transport.udp import udp_interface
        # except:
        #     lg.exc()
        #     return False
        # return True

    def _on_transport_state_changed(self, transport, oldstate, newstate):
        from bitdust.logs import lg
        lg.info('%s -> %s in %r  starting_deferred=%r' % (oldstate, newstate, transport, bool(self.starting_deferred)))
        if self.starting_deferred:
            if newstate in [
                'LISTENING',
            ] and oldstate != newstate:
                self.starting_deferred.callback(True)
                self.starting_deferred = None
            elif newstate in [
                'OFFLINE',
            ] and oldstate != newstate and oldstate not in [
                'INIT',
            ]:
                self.starting_deferred.errback(Exception(newstate))
                self.starting_deferred = None

    def _on_enabled_disabled(self, path, value, oldvalue, result):
        from bitdust.p2p import network_connector
        from bitdust.logs import lg
        lg.out(2, 'service_udp_transport._on_enabled_disabled : %s->%s : %s' % (oldvalue, value, path))
        network_connector.A('reconnect')

    def _on_receiving_enabled_disabled(self, path, value, oldvalue, result):
        from bitdust.p2p import network_connector
        from bitdust.logs import lg
        lg.out(2, 'service_udp_transport._on_receiving_enabled_disabled : %s->%s : %s' % (oldvalue, value, path))
        network_connector.A('reconnect')

    def _on_network_receive_limit_modified(self, path, value, oldvalue, result):
        from bitdust.transport.udp import udp_stream
        udp_stream.set_global_input_limit_bytes_per_sec(int(value))

    def _on_network_send_limit_modified(self, path, value, oldvalue, result):
        from bitdust.transport.udp import udp_stream
        udp_stream.set_global_output_limit_bytes_per_sec(int(value))
