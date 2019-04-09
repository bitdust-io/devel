#!/usr/bin/python
# service_my_ip_port.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (service_my_ip_port.py) is part of BitDust Software.
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

module:: service_my_ip_port
"""

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return MyIPPortService()


class MyIPPortService(LocalService):

    service_name = 'service_my_ip_port'
    config_path = 'services/my-ip-port/enabled'

    def init(self):
        self._my_address = None

    def dependent_on(self):
        return [
            'service_entangled_dht',
            'service_udp_datagrams',
        ]

    def start(self):
        from stun import stun_client
        from main import settings
        stun_client.A('init', settings.getUDPPort())
        return True

    def stop(self):
        from stun import stun_client
        stun_client.A('shutdown')
        return True
