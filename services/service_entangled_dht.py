#!/usr/bin/python
# service_entangled_dht.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
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

from services.local_service import LocalService


def create_service():
    return EntangledDHTService()


class EntangledDHTService(LocalService):

    service_name = 'service_entangled_dht'
    config_path = 'services/entangled-dht/enabled'

    def dependent_on(self):
        return ['service_udp_datagrams',
                ]

    def start(self):
        from dht import dht_service
        from main import settings
        from main.config import conf
        dht_service.init(settings.getDHTPort(), settings.DHTDBFile())
        dht_service.connect()
        conf().addCallback('services/entangled-dht/udp-port',
                           self._on_udp_port_modified)
        return True

    def stop(self):
        from dht import dht_service
        from main.config import conf
        conf().removeCallback('services/entangled-dht/udp-port')
        dht_service.disconnect()
        dht_service.shutdown()
        return True

    def _on_udp_port_modified(self, path, value, oldvalue, result):
        from p2p import network_connector
        from logs import lg
        lg.out(2, 'service_entangled_dht._on_udp_port_modified %s->%s : %s' % (
            oldvalue, value, path))
        if network_connector.A():
            network_connector.A('reconnect')
