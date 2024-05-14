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
        # from bitdust.main import events
        # events.add_subscriber(self._on_my_identity_url_changed, 'my-identity-url-changed')
        return True

    def stop(self):
        # from bitdust.main import events
        # events.remove_subscriber(self._on_my_identity_url_changed, 'my-identity-url-changed')
        return True

    def request(self, json_payload, newpacket, info):
        from twisted.internet.defer import Deferred
        from bitdust.logs import lg
        from bitdust.p2p import p2p_service
        from bitdust.stream import message_peddler
        from bitdust.userid import id_url
        try:
            action = json_payload['action']
        except:
            lg.exc()
            return p2p_service.SendFail(newpacket, 'invalid payload')
        # TODO: validate signature and the key
        if action == 'queue-connect':  #  or action == 'queue-connect-follow':
            try:
                # queue_id = json_payload.get('queue_id')
                consumer_id = json_payload.get('consumer_id')
                producer_id = json_payload.get('producer_id')
                group_key_info = json_payload.get('group_key')
                # position = int(json_payload.get('position', -1))
                # archive_folder_path = json_payload.get('archive_folder_path', None)
                # last_sequence_id = json_payload.get('last_sequence_id', -1)
                # known_brokers = json_payload.get('known_brokers', {}) or {}
                # known_brokers = {int(k): id_url.field(v) for k, v in known_brokers.items()}
            except:
                lg.warn('wrong payload: %r' % json_payload)
                return p2p_service.SendFail(newpacket, 'wrong payload')
            result_defer = Deferred()
            from bitdust.stream import postman
            postman.on_queue_connect_request(newpacket, result_defer, consumer_id, producer_id, group_key_info)
            return result_defer
            # message_peddler.A(
            #     event='connect' if action == 'queue-connect' else 'follow',
            #     queue_id=queue_id,
            #     consumer_id=consumer_id,
            #     producer_id=producer_id,
            #     group_key=group_key,
            #     position=position,
            #     archive_folder_path=archive_folder_path,
            #     last_sequence_id=last_sequence_id,
            #     known_brokers=known_brokers,
            #     request_packet=newpacket,
            #     result_defer=result,
            # )
        # elif action == 'broker-verify':
        #     try:
        #         customer_id = json_payload['customer_id']
        #         broker_id = json_payload['broker_id']
        #         position = json_payload['position']
        #         known_streams = json_payload['streams']
        #         known_brokers = {int(k): id_url.field(v) for k, v in json_payload['known_brokers'].items()}
        #     except:
        #         lg.warn('wrong payload: %r' % json_payload)
        #         return p2p_service.SendFail(newpacket, 'wrong payload')
        #     message_peddler.A(
        #         event='broker-reconnect',
        #         customer_id=customer_id,
        #         broker_id=broker_id,
        #         position=position,
        #         known_streams=known_streams,
        #         known_brokers=known_brokers,
        #         request_packet=newpacket,
        #         result_defer=result,
        #     )
        lg.warn('wrong action request' % newpacket.Payload)
        return p2p_service.SendFail(newpacket, 'wrong action request')
        # return result

    # def cancel(self, json_payload, newpacket, info):
    #     from twisted.internet.defer import Deferred
    #     from bitdust.logs import lg
    #     from bitdust.p2p import p2p_service
    #     from bitdust.stream import message_peddler
    #     try:
    #         action = json_payload['action']
    #         queue_id = json_payload.get('queue_id', None)
    #         consumer_id = json_payload['consumer_id']
    #         producer_id = json_payload['producer_id']
    #         group_key = json_payload['group_key']
    #     except:
    #         lg.warn('wrong payload: %r' % json_payload)
    #         return p2p_service.SendFail(newpacket, 'wrong payload')
    #     # TODO: validate signature and the key
    #     result = Deferred()
    #     if action == 'queue-disconnect':
    #         message_peddler.A(
    #             event='disconnect',
    #             queue_id=queue_id,
    #             consumer_id=consumer_id,
    #             producer_id=producer_id,
    #             group_key=group_key,
    #             request_packet=newpacket,
    #             result_defer=result,
    #         )
    #     else:
    #         lg.warn('wrong action request' % newpacket.Payload)
    #         return p2p_service.SendFail(newpacket, 'wrong action request')
    #     return result

    # def _do_connect_message_brokers_dht_layer(self):
    #     from bitdust.logs import lg
    #     from bitdust.dht import dht_service
    #     from bitdust.dht import dht_records
    #     from bitdust.dht import known_nodes
    #     known_seeds = known_nodes.nodes()
    #     d = dht_service.open_layer(
    #         layer_id=dht_records.LAYER_MESSAGE_BROKERS,
    #         seed_nodes=known_seeds,
    #         connect_now=True,
    #         attach=True,
    #     )
    #     d.addCallback(self._on_message_brokers_dht_layer_connected)
    #     d.addErrback(lambda *args: lg.err(str(args)))

    # def _on_message_brokers_dht_layer_connected(self, ok):
    #     from bitdust.logs import lg
    #     from bitdust.dht import dht_service
    #     from bitdust.dht import dht_records
    #     from bitdust.userid import my_id
    #     lg.info('connected to DHT layer for message brokers: %r' % ok)
    #     if my_id.getIDURL():
    #         dht_service.set_node_data('idurl', my_id.getIDURL().to_text(), layer_id=dht_records.LAYER_MESSAGE_BROKERS)
    #     return ok

    # def _on_dht_layer_connected(self, evt):
    #     from bitdust.dht import dht_records
    #     if evt.data['layer_id'] == 0:
    #         self._do_connect_message_brokers_dht_layer()
    #     elif evt.data['layer_id'] == dht_records.LAYER_MESSAGE_BROKERS:
    #         self._on_message_brokers_dht_layer_connected(True)

    # def _on_my_identity_url_changed(self, evt):
    #     from bitdust.stream import message_peddler
    #     message_peddler.A('stop')
    #     message_peddler.close_all_streams()
    #     message_peddler.check_rotate_queues()
