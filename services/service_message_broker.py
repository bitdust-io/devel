#!/usr/bin/python
# service_message_broker.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (service_message_broker.py) is part of BitDust Software.
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

module:: service_message_broker
"""

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return MessageBrokerService()


class MessageBrokerService(LocalService):

    service_name = 'service_message_broker'
    config_path = 'services/message-broker/enabled'

    last_time_keys_synchronized = None

    def dependent_on(self):
        return [
            'service_keys_registry',
            'service_entangled_dht',
        ]

    def start(self):
        return True

    def stop(self):
        return True

    def health_check(self):
        return True

    def request(self, json_payload, newpacket, info):
        from logs import lg
        from p2p import p2p_service
        from userid import global_id
        customer_idurl = newpacket.OwnerID
        customer_id = global_id.UrlToGlobalID(customer_idurl)
        try:
            queue_id = int(json_payload['queue_id'])
        except:
            lg.warn("wrong payload" % newpacket.Payload)
            return p2p_service.SendFail(newpacket, 'wrong payload')
        # TODO: ...
