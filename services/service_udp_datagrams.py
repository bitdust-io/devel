#!/usr/bin/python
# service_udp_datagrams.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (service_udp_datagrams.py) is part of BitDust Software.
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

module:: service_udp_datagrams
"""

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return UDPDatagramsService()


class UDPDatagramsService(LocalService):

    service_name = 'service_udp_datagrams'
    config_path = 'services/udp-datagrams/enabled'

    def dependent_on(self):
        return [
            'service_network',
        ]

    def start(self):
        from logs import lg
        from lib import udp
        from main import settings
        from main.config import conf
        udp_port = settings.getUDPPort()
        conf().addCallback('services/udp-datagrams/udp-port',
                           self._on_udp_port_modified)
        if not udp.proto(udp_port):
            try:
                udp.listen(udp_port)
            except:
                lg.exc()
                return False
        return True

    def stop(self):
        from lib import udp
        from main import settings
        from main.config import conf
        udp_port = settings.getUDPPort()
        if udp.proto(udp_port):
            udp.close(udp_port)
        conf().removeCallback('services/udp-datagrams/udp-port')
        return True

    def _on_udp_port_modified(self, path, value, oldvalue, result):
        from p2p import network_connector
        from logs import lg
        lg.out(
            2, 'service_udp_datagrams._on_udp_port_modified : %s->%s : %s' %
            (oldvalue, value, path))
        network_connector.A('reconnect')
