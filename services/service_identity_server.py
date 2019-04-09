#!/usr/bin/python
# service_identity_server.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (service_identity_server.py) is part of BitDust Software.
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

module:: service_identity_server
"""

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return IdentityServerService()


class IdentityServerService(LocalService):

    service_name = 'service_identity_server'
    config_path = 'services/identity-server/enabled'

    def init(self):
        self.log_events = True

    def dependent_on(self):
        return [
            'service_tcp_connections',
        ]

    def installed(self):
        return True

    def enabled(self):
        from main import settings
        return settings.enableIdServer()

    def start(self):
        from userid import id_server
        from main import settings
        id_server.A('init', (settings.getIdServerWebPort(), settings.getIdServerTCPPort(), ))
        id_server.A('start')
        return True

    def stop(self):
        from userid import id_server
        id_server.A('stop')
        id_server.A('shutdown')
        return True
