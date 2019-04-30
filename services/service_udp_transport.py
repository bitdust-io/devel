#!/usr/bin/python
# service_udp_transport.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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
from services.local_service import LocalService


def create_service():
    return UDPTransportService()


class UDPTransportService(LocalService):

    service_name = 'service_udp_transport'
    config_path = 'services/udp-transport/enabled'
    proto = 'udp'

    def dependent_on(self):
        return [
            'service_udp_datagrams',
            'service_my_ip_port',
            'service_gateway',
        ]

    def start(self):
        from twisted.internet import reactor  # @UnresolvedImport
        from twisted.internet.defer import Deferred
        from transport.udp import udp_interface
        from transport import network_transport
        from transport import gateway
        from main.config import conf
        self.starting_deferred = Deferred()
        self.transport = network_transport.NetworkTransport('udp', udp_interface.GateInterface())
        self.transport.automat(
            'init', (gateway.listener(), self._on_transport_state_changed))
        reactor.callLater(0, self.transport.automat, 'start')  # @UndefinedVariable
        conf().addCallback('services/udp-transport/enabled',
                           self._on_enabled_disabled)
        conf().addCallback('services/udp-transport/receiving-enabled',
                           self._on_receiving_enabled_disabled)
        conf().addCallback('services/network/receive-limit',
                           self._on_network_receive_limit_modified)
        conf().addCallback('services/network/send-limit',
                           self._on_network_send_limit_modified)
        return self.starting_deferred

    def stop(self):
        from main.config import conf
        conf().removeCallback('services/udp-transport/enabled')
        conf().removeCallback('services/udp-transport/receiving-enabled')
        conf().removeCallback('services/network/receive-limit')
        conf().removeCallback('services/network/send-limit')
        t = self.transport
        self.transport = None
        t.automat('shutdown')
        return True

    def installed(self):
        return False
    # from logs import lg
        # try:
        #     from transport.udp import udp_interface
        # except:
        #     lg.exc()
        #     return False
        # return True

    def _on_transport_state_changed(self, transport, oldstate, newstate):
        if self.starting_deferred:
            if newstate == 'LISTENING':
                self.starting_deferred.callback(newstate)
                self.starting_deferred = None
            elif newstate == 'OFFLINE' and oldstate in ['STARTING', 'STOPPING', ]:
                self.starting_deferred.callback(newstate)
                self.starting_deferred = None

    def _on_enabled_disabled(self, path, value, oldvalue, result):
        from p2p import network_connector
        from logs import lg
        lg.out(
            2, 'service_udp_transport._on_enabled_disabled : %s->%s : %s' %
            (oldvalue, value, path))
        network_connector.A('reconnect')

    def _on_receiving_enabled_disabled(self, path, value, oldvalue, result):
        from p2p import network_connector
        from logs import lg
        lg.out(
            2, 'service_udp_transport._on_receiving_enabled_disabled : %s->%s : %s' %
            (oldvalue, value, path))
        network_connector.A('reconnect')

    def _on_network_receive_limit_modified(
            self, path, value, oldvalue, result):
        from transport.udp import udp_stream
        udp_stream.set_global_input_limit_bytes_per_sec(int(value))

    def _on_network_send_limit_modified(self, path, value, oldvalue, result):
        from transport.udp import udp_stream
        udp_stream.set_global_output_limit_bytes_per_sec(int(value))
