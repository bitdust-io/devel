#!/usr/bin/python
# service_joint_postman.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (service_joint_postman.py) is part of BitDust Software.
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

module:: service_joint_postman
"""

from __future__ import absolute_import
from bitdust.services.local_service import LocalService


def create_service():
    return JointPostmanService()


class JointPostmanService(LocalService):

    service_name = 'service_joint_postman'
    config_path = 'services/joint-postman/enabled'
    data_dir_required = True

    last_time_keys_synchronized = None

    def dependent_on(self):
        return [
            'service_private_messages',
            'service_customer_family',
        ]

    def start(self):
        from bitdust.stream import postman
        postman.init()
        return True

    def stop(self):
        from bitdust.stream import postman
        postman.shutdown()
        return True

    def request(self, json_payload, newpacket, info):
        from twisted.internet.defer import Deferred
        from bitdust.logs import lg
        from bitdust.p2p import p2p_service
        from bitdust.stream import postman
        from bitdust.userid import global_id
        try:
            action = json_payload['action']
        except:
            lg.exc()
            return p2p_service.SendFail(newpacket, 'invalid payload')
        # TODO: validate signature and the key
        if action == 'queue-connect':  #  or action == 'queue-connect-follow':
            try:
                consumer_id = global_id.latest_glob_id(json_payload.get('consumer_id'))
                producer_id = global_id.latest_glob_id(json_payload.get('producer_id'))
                group_key_info = json_payload.get('group_key')
            except:
                lg.warn('wrong payload: %r' % json_payload)
                return p2p_service.SendFail(newpacket, 'wrong payload')
            result_defer = Deferred()
            postman.on_queue_connect_request(newpacket, result_defer, consumer_id, producer_id, group_key_info)
            return result_defer
        lg.warn('wrong action request' % newpacket.Payload)
        return p2p_service.SendFail(newpacket, 'wrong action request')

    def cancel(self, json_payload, newpacket, info):
        from twisted.internet.defer import Deferred
        from bitdust.logs import lg
        from bitdust.p2p import p2p_service
        from bitdust.stream import postman
        try:
            action = json_payload['action']
            queue_id = json_payload.get('queue_id', None)
            consumer_id = json_payload['consumer_id']
            producer_id = json_payload['producer_id']
            group_key_info = json_payload['group_key']
        except:
            lg.warn('wrong payload: %r' % json_payload)
            return p2p_service.SendFail(newpacket, 'wrong payload')
        # TODO: validate signature and the key
        if action == 'queue-disconnect':
            result_defer = Deferred()
            postman.on_queue_disconnect_request(newpacket, result_defer, consumer_id, producer_id, group_key_info, queue_id)
            return result_defer
        lg.warn('wrong action request' % newpacket.Payload)
        return p2p_service.SendFail(newpacket, 'wrong action request')
