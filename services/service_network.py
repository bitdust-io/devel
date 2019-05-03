#!/usr/bin/python
# service_network.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (service_network.py) is part of BitDust Software.
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

module:: service_network
"""

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return NetworkService()


class NetworkService(LocalService):

    service_name = 'service_network'
    config_path = 'services/network/enabled'

    current_network_interfaces = None

    def dependent_on(self):
        return [
            # this is a top root service, everything in BitDust depends on networking
        ]

    def start(self):
        from twisted.internet import task
        from p2p import network_connector
        network_connector.A('init')
        self.task = task.LoopingCall(self._do_check_network_interfaces)
        self.task.start(20, now=False)
        return True

    def stop(self):
        from p2p import network_connector
        network_connector.Destroy()
        if self.task and self.task.running:
            self.task.stop()
            self.task = None
        return True

    def _do_check_network_interfaces(self):
        from lib.net_misc import getNetworkInterfaces
        from p2p import network_connector
        from logs import lg
        known_interfaces = getNetworkInterfaces()
        if '127.0.0.1' in known_interfaces:
            known_interfaces.remove('127.0.0.1')
        if self.current_network_interfaces is None:
            self.current_network_interfaces = known_interfaces
            lg.out(2, 'service_network._do_check_network_interfaces START UP: %s' % self.current_network_interfaces)
        else:
            if self.current_network_interfaces != known_interfaces:
                lg.out(2, 'service_network._do_check_network_interfaces recognized changes: %s -> %s' % (
                    self.current_network_interfaces, known_interfaces))
                self.current_network_interfaces = known_interfaces
                network_connector.A('check-reconnect')
