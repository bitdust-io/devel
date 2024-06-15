#!/usr/bin/python
# service_udp_datagrams.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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
from bitdust.services.local_service import LocalService


def create_service():
    return UDPDatagramsService()


class UDPDatagramsService(LocalService):

    service_name = 'service_udp_datagrams'
    config_path = 'services/udp-datagrams/enabled'
    start_suspended = True

    def dependent_on(self):
        return [
            'service_network',
        ]

    def start(self):
        from bitdust.logs import lg
        from bitdust.lib import udp
        from bitdust.main import settings
        from bitdust.main.config import conf
        udp_port = settings.getUDPPort()
        conf().addConfigNotifier('services/udp-datagrams/udp-port', self._on_udp_port_modified)
        if not udp.proto(udp_port):
            try:
                udp.listen(udp_port)
            except:
                lg.exc()
                return False
        return True

    def stop(self):
        from bitdust.lib import udp
        from bitdust.main import settings
        from bitdust.main.config import conf
        udp_port = settings.getUDPPort()
        if udp.proto(udp_port):
            udp.close(udp_port)
        conf().removeConfigNotifier('services/udp-datagrams/udp-port')
        return True

    def on_suspend(self, *args, **kwargs):
        from bitdust.lib import udp
        from bitdust.main import settings
        udp_port = settings.getUDPPort()
        if udp.proto(udp_port):
            udp.close(udp_port)
        return True

    def on_resume(self, *args, **kwargs):
        from bitdust.logs import lg
        from bitdust.lib import udp
        from bitdust.main import settings
        udp_port = settings.getUDPPort()
        if not udp.proto(udp_port):
            try:
                udp.listen(udp_port)
            except:
                lg.exc()
        return True

    def _on_udp_port_modified(self, path, value, oldvalue, result):
        from bitdust.p2p import network_connector
        network_connector.A('reconnect')
