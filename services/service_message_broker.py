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
    data_dir_required = True

    last_time_keys_synchronized = None

    def dependent_on(self):
        return [
            'service_private_messages',
        ]

    def start(self):
        from main import events
        from p2p import message_peddler
        message_peddler.A('start')
        self._do_connect_message_brokers_dht_layer()
        events.add_subscriber(self._on_dht_layer_connected, event_id='dht-layer-connected')
        return True

    def stop(self):
        from dht import dht_service
        from dht import dht_records
        from main import events
        from p2p import message_peddler
        events.remove_subscriber(self._on_dht_layer_connected, event_id='dht-layer-connected')
        dht_service.suspend(layer_id=dht_records.LAYER_MESSAGE_BROKERS)
        message_peddler.A('stop')
        return True

    def health_check(self):
        return True

    def request(self, json_payload, newpacket, info):
        from twisted.internet.defer import Deferred
        from logs import lg
        # from userid import global_id
        from p2p import p2p_service
        from p2p import message_peddler
        # customer_idurl = newpacket.OwnerID
        # customer_id = global_id.UrlToGlobalID(customer_idurl)
        try:
            action = json_payload['action']
            queue_id = json_payload['queue_id']
            consumer_id = json_payload['consumer_id']
            producer_id = json_payload['producer_id']
            group_key = json_payload['group_key']
            position = json_payload.get('position', -1)
        except:
            lg.warn("wrong payload: %r" % json_payload)
            return p2p_service.SendFail(newpacket, 'wrong payload')
        # TODO: validate signature and the key
        result = Deferred()
        if action == 'queue-connect':
            message_peddler.A(
                'queue-connect',
                group_key=group_key,
                queue_id=queue_id,
                consumer_id=consumer_id,
                producer_id=producer_id,
                position=position,
                request_packet=newpacket,
                result_defer=result,
            )
        elif action == 'queue-disconnect':
            message_peddler.A(
                'queue-disconnect',
                group_key=group_key,
                queue_id=queue_id,
                consumer_id=consumer_id,
                producer_id=producer_id,
                request_packet=newpacket,
                result_defer=result,
            )
        else:
            lg.warn("wrong action request" % newpacket.Payload)
            return p2p_service.SendFail(newpacket, 'wrong action request')
        return result

    def _do_connect_message_brokers_dht_layer(self):
        from logs import lg
        from dht import dht_service
        from dht import dht_records
        from dht import known_nodes
        known_seeds = known_nodes.nodes()
        d = dht_service.open_layer(
            layer_id=dht_records.LAYER_MESSAGE_BROKERS,
            seed_nodes=known_seeds,
            connect_now=True,
            attach=True,
        )
        d.addCallback(self._on_message_brokers_dht_layer_connected)
        d.addErrback(lambda *args: lg.err(str(args)))

    def _on_message_brokers_dht_layer_connected(self, ok):
        from logs import lg
        from dht import dht_service
        from dht import dht_records
        from userid import my_id
        lg.info('connected to DHT layer for message brokers: %r' % ok)
        if my_id.getLocalID():
            dht_service.set_node_data('idurl', my_id.getLocalID().to_text(), layer_id=dht_records.LAYER_MESSAGE_BROKERS)
        return ok

    def _on_dht_layer_connected(self, evt):
        if evt.data['layer_id'] == 0:
            self._do_connect_message_brokers_dht_layer()
