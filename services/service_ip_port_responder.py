#!/usr/bin/python
# service_ip_port_responder.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (service_ip_port_responder.py) is part of BitDust Software.
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
.. module:: service_ip_port_responder

"""

from services.local_service import LocalService


def create_service():
    return IPPortResponderService()


class IPPortResponderService(LocalService):

    service_name = 'service_ip_port_responder'
    config_path = 'services/ip-port-responder/enabled'

    def dependent_on(self):
        return ['service_udp_datagrams',
                'service_entangled_dht',
                ]

    def start(self):
        from stun import stun_server
        from main import settings
        udp_port = int(settings.getUDPPort())
        stun_server.A('start', udp_port)
        return True

    def stop(self):
        from stun import stun_server
        stun_server.A('stop')
        stun_server.Destroy()
        return True
