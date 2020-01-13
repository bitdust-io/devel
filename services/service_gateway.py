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
from services.local_service import LocalService


def create_service():
    return GatewayService()


class GatewayService(LocalService):

    service_name = 'service_gateway'
    config_path = 'services/gateway/enabled'

    def dependent_on(self):
        return [
            'service_network',
        ]

    def installed(self):
        from userid import my_id
        if not my_id.isLocalIdentityReady():
            return False
        return True

    def network_configuration(self):
        from crypt import key
        return {
            'session_key_type': key.SessionKeyType(),
        }

    def start(self):
        from transport import packet_out
        from transport import packet_in
        from transport import gateway
        from transport import callback
        from transport import bandwidth
        from services import driver
        from userid import my_id 
        packet_out.init()
        packet_in.init()
        gateway.init()
        bandwidth.init()
        callback.insert_inbox_callback(0, bandwidth.INfile)
        callback.add_finish_file_sending_callback(bandwidth.OUTfile)
#         if driver.is_on('service_entangled_dht'):
#             from dht import dht_service
#             dht_service.set_node_data('idurl', my_id.getLocalID().to_text())
        return True

    def stop(self):
        from transport import packet_out
        from transport import packet_in
        from transport import gateway
        from transport import callback
        from transport import bandwidth
        callback.remove_inbox_callback(bandwidth.INfile)
        callback.remove_finish_file_sending_callback(bandwidth.OUTfile)
        d = gateway.stop()
        bandwidth.shutdown()
        gateway.shutdown()
        packet_out.shutdown()
        packet_in.shutdown()
        return d
