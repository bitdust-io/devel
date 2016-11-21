#!/usr/bin/python
# service_my_ip_port.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
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
.. module:: service_my_ip_port

"""

from services.local_service import LocalService


def create_service():
    return MyIPPortService()


class MyIPPortService(LocalService):

    service_name = 'service_my_ip_port'
    config_path = 'services/my-ip-port/enabled'

    def init(self):
        self._my_address = None

    def dependent_on(self):
        return ['service_entangled_dht',
                'service_udp_datagrams',
                ]

    def start(self):
        from twisted.internet import reactor
        from twisted.internet.defer import Deferred
        from stun import stun_client
        from main import settings
        stun_client.A('init', settings.getUDPPort())
        return True
        # d = Deferred()
        # reactor.callLater(0.5, stun_client.A, 'start',
        #     lambda result, typ, ip, details:
        #         self._on_stun_client_finished(result, typ, ip, details, d))
        # return d

    def stop(self):
        from stun import stun_client
        stun_client.A('shutdown')
        return True

#     def _on_stun_client_finished(self, result, typ, ip, details, result_defer):
#         from stun import stun_client
#         result_defer.callback(stun_client.A().getMyExternalAddress())
