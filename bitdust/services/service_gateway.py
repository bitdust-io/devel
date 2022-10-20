#!/usr/bin/python
# service_gateway.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (service_gateway.py) is part of BitDust Software.
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

module:: service_gateway
"""

from __future__ import absolute_import
from bitdust.services.local_service import LocalService


def create_service():
    return GatewayService()


class GatewayService(LocalService):

    service_name = 'service_gateway'
    config_path = 'services/gateway/enabled'
    start_suspended = True

    def dependent_on(self):
        return [
            'service_network',
        ]

    def installed(self):
        from bitdust.userid import my_id
        if not my_id.isLocalIdentityReady():
            return False
        return True

    def network_configuration(self):
        from bitdust.crypt import key
        return {
            'session_key_type': key.SessionKeyType(),
        }

    def start(self):
        from bitdust.transport import packet_out
        from bitdust.transport import packet_in
        from bitdust.transport import gateway
        packet_out.init()
        packet_in.init()
        gateway.init()
        return True

    def stop(self):
        from bitdust.transport import packet_out
        from bitdust.transport import packet_in
        from bitdust.transport import gateway
        gateway.stop()
        gateway.shutdown()
        packet_out.shutdown()
        packet_in.shutdown()
        return True

    def on_suspend(self, *args, **kwargs):
        from bitdust.transport import gateway
        return gateway.stop()

    def on_resume(self, *args, **kwargs):
        from bitdust.transport import gateway
        if kwargs.get('cold_start') is True:
            return gateway.cold_start()
        return gateway.start()
