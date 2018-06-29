#!/usr/bin/python
# service_network.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
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

from services.local_service import LocalService


def create_service():
    return NetworkService()


class NetworkService(LocalService):

    service_name = 'service_network'
    config_path = 'services/network/enabled'

    status = None

    def dependent_on(self):
        return []

    def start(self):
        from twisted.internet import task
        from p2p import network_connector

        network_connector.A('init')

        self.task = task.LoopingCall(self._do_check_network_interfaces)

        self.task.start(10)

        return True

    def stop(self):
        from p2p import network_connector
        network_connector.Destroy()

        self.task.stop()

        return True

    def _do_check_network_interfaces(self):
        from lib.net_misc import getNetworkInterfaces
        from p2p import network_connector

        interfaces = getNetworkInterfaces()

        if self.status != interfaces[0]:
            self.status = interfaces[0]
            network_connector.A('reconnect')
