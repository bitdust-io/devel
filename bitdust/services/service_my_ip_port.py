#!/usr/bin/python
# service_my_ip_port.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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
from bitdust.services.local_service import LocalService


def create_service():
    return MyIPPortService()


class MyIPPortService(LocalService):

    service_name = 'service_my_ip_port'
    config_path = 'services/my-ip-port/enabled'
    start_suspended = True

    def init(self):
        self._my_address = None

    def dependent_on(self):
        return [
            'service_entangled_dht',
            'service_udp_datagrams',
        ]

    def start(self):
        from bitdust.stun import stun_client
        from bitdust.main import settings
        from bitdust.lib import misc
        stun_client.A('init', settings.getUDPPort())
        known_external_ip = misc.readExternalIP()
        if not known_external_ip or known_external_ip == '127.0.0.1':
            self._do_stun()
        return True

    def stop(self):
        from bitdust.stun import stun_client
        stun_client.A('shutdown')
        return True

    def on_suspend(self, *args, **kwargs):
        return True

    def on_resume(self, *args, **kwargs):
        from bitdust.stun import stun_client
        if not stun_client.A() or stun_client.A().state in [
            'STOPPED',
        ]:
            stun_client.A().dropMyExternalAddress()
            stun_client.A('start')
        return True

    def _do_stun(self):
        from bitdust.stun import stun_client
        stun_client.A().dropMyExternalAddress()
        stun_client.A('start', self._on_stun_result)

    def _on_stun_result(self, stun_result, nat_type, my_ip, details):
        from bitdust.logs import lg
        from twisted.internet import reactor  # @UnresolvedImport
        if stun_result != 'stun-success' or not my_ip or my_ip == '127.0.0.1':
            lg.warn('stun my external IP failed, retry after 10 seconds')
            reactor.callLater(10, self._do_stun)  # @UndefinedVariable
        else:
            lg.info('stun success  nat_type=%r, my_ip=%r, details=%r' % (nat_type, my_ip, details))
