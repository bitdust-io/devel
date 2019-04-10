#!/usr/bin/python
# service_http_connections.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (service_http_connections.py) is part of BitDust Software.
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

module:: service_http_connections
"""

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return HTTPConnectionsService()


class HTTPConnectionsService(LocalService):

    service_name = 'service_http_connections'
    config_path = 'services/http-connections/enabled'

    def dependent_on(self):
        return [
            'service_network',
        ]

    def start(self):
        from main.config import conf
        conf().addCallback('services/http-connections/http-port', self._on_http_port_modified)
        return True

    def stop(self):
        from main.config import conf
        conf().removeCallback('services/http-connections/http-port')
        return True

    def _on_http_port_modified(self, path, value, oldvalue, result):
        from p2p import network_connector
        from logs import lg
        lg.out(2, 'service_http_connections._on_http_port_modified : %s->%s : %s' % (oldvalue, value, path))
        network_connector.A('reconnect')
