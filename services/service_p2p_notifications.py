#!/usr/bin/python
# service_p2p_notifications.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (service_p2p_notifications.py) is part of BitDust Software.
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

module:: service_p2p_notifications
"""

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return P2PNotificationsService()


class P2PNotificationsService(LocalService):

    service_name = 'service_p2p_notifications'
    config_path = 'services/p2p-notifications/enabled'

    def dependent_on(self):
        from main import settings
        depends = [
            'service_p2p_hookups',
        ]
        if settings.enablePROXY():
            depends.append('service_proxy_transport')
        return depends

    def start(self):
        from transport import callback
        from p2p import p2p_queue
        p2p_queue.init()
        callback.append_inbox_callback(self._on_inbox_packet_received)
        return True

    def stop(self):
        from transport import callback
        from p2p import p2p_queue
        callback.remove_inbox_callback(self._on_inbox_packet_received)
        p2p_queue.shutdown()
        return True

    def request(self, json_payload, newpacket, info):
        from logs import lg
        from lib import serialization
        from p2p import p2p_service
        from p2p import p2p_queue
        try:
            service_requests_list = json_payload['items']
        except:
            lg.warn("invlid json payload")
            return p2p_service.SendFail(newpacket, 'invlid json payload')
        service_responses_list = []
        for r_json in service_requests_list:
            resp = r_json.copy()
            r_scope = r_json.get('scope', '')
            r_action = r_json.get('action', '')
            try:
                if r_scope == 'queue':
                    if r_action == 'open':
                        resp['result'] = 'denied' if not p2p_queue.open_queue(
                            queue_id=r_json.get('queue_id'),
                        ) else 'OK'
                    elif r_action == 'close':
                        resp['result'] = 'denied' if not p2p_queue.close_queue(
                            queue_id=r_json.get('queue_id'),
                        ) else 'OK'
                elif r_scope == 'consumer':
                    if r_action == 'start':
                        resp['result'] = 'denied' if not p2p_queue.add_consumer(
                            consumer_id=r_json.get('consumer_id'),
                        ) else 'OK'
                    elif r_action == 'stop':
                        resp['result'] = 'denied' if not p2p_queue.remove_consumer(
                            consumer_id=r_json.get('consumer_id'),
                        ) else 'OK'
                    elif r_action == 'add_callback':
                        resp['result'] = 'denied' if not p2p_queue.add_callback_method(
                            consumer_id=r_json.get('consumer_id'),
                            callback_method=r_json.get('method'),
                        ) else 'OK'
                    elif r_action == 'remove_callback':
                        resp['result'] = 'denied' if not p2p_queue.remove_callback_method(
                            consumer_id=r_json.get('consumer_id'),
                            callback_method=r_json.get('method'),
                        ) else 'OK'
                    elif r_action == 'subscribe':
                        resp['result'] = 'denied' if not p2p_queue.subscribe_consumer(
                            consumer_id=r_json.get('consumer_id'),
                            queue_id=r_json.get('queue_id'),
                        ) else 'OK'
                    elif r_action == 'unsubscribe':
                        resp['result'] = 'denied' if not p2p_queue.unsubscribe_consumer(
                            consumer_id=r_json.get('consumer_id'),
                            queue_id=r_json.get('queue_id'),
                        ) else 'OK'
                elif r_scope == 'producer':
                    resp['result'] = 'denied'
                    resp['reason'] = 'remote requests for producing messages is not allowed'
                    if False:
                        # TODO: do we need that ?
                        if r_action == 'start':
                            resp['result'] = 'denied' if not p2p_queue.add_producer(
                                producer_id=r_json.get('producer_id'),
                            ) else 'OK'
                        elif r_action == 'stop':
                            resp['result'] = 'denied' if not p2p_queue.remove_producer(
                                producer_id=r_json.get('producer_id'),
                            ) else 'OK'
                        elif r_action == 'connect':
                            resp['result'] = 'denied' if not p2p_queue.connect_producer(
                                producer_id=r_json.get('producer_id'),
                                queue_id=r_json.get('queue_id'),
                            ) else 'OK'
                        elif r_action == 'disconnect':
                            resp['result'] = 'denied' if not p2p_queue.disconnect_producer(
                                producer_id=r_json.get('producer_id'),
                                queue_id=r_json.get('queue_id'),
                            ) else 'OK'
            except Exception as exc:
                resp['result'] = 'denied'
                resp['reason'] = str(exc)
            service_responses_list.append(resp)
            lg.out(self.debug_level, 'service_p2p_notifications.request  %s:%s  is  [%s] : %s' % (
                r_scope, r_action, resp['result'], resp.get('reason', 'OK'), ))
        payload = serialization.DictToBytes({'items': service_responses_list, }, values_to_text=True)
        return p2p_service.SendAck(newpacket, payload)

    def cancel(self, json_payload, newpacket, info):
        # TODO: work in progress
        return False

    def _on_inbox_packet_received(self, newpacket, info, status, error_message):
#         import json
#         from logs import lg
#         from main import events
        from p2p import commands
#         from p2p import p2p_service
        from p2p import p2p_queue
#         from userid import global_id
#         from userid import my_id
        if newpacket.Command != commands.Event():
            return False
        return p2p_queue.on_event_packet_received(newpacket, info, status, error_message)


#         try:
#             e_json = json.loads(newpacket.Payload)
#             event_id = e_json['event_id']
#             payload = e_json['payload']
#             queue_id = e_json.get('queue_id')
#             producer_id = e_json.get('producer_id')
#             message_id = e_json.get('message_id')
#             created = e_json.get('created')
#         except:
#             lg.warn("invlid json payload")
#             return False
#         if queue_id and producer_id and message_id:
#             # this message have an ID and producer so it came from a queue and needs to be consumed
#             # also add more info comming from the queue
#             lg.info('received event from the queue at %s' % queue_id)
#             payload.update(dict(
#                 queue_id=queue_id,
#                 producer_id=producer_id,
#                 message_id=message_id,
#                 created=created,
#             ))
#             events.send(event_id, data=payload)
#             p2p_service.SendAck(newpacket)
#             return True
#         # this message does not have nor ID nor producer so it came from another user directly
#         # lets' try to find a queue for that event and see if we need to publish it or not
#         queue_id = global_id.MakeGlobalQueueID(
#             queue_alias=event_id,
#             owner_id=global_id.MakeGlobalID(idurl=newpacket.OwnerID),
#             supplier_id=global_id.MakeGlobalID(idurl=my_id.getGlobalID()),
#         )
#         if queue_id not in p2p_queue.queue():
#             # such queue is not found locally, that means message is
#             # probably addressed to that node and needs to be consumed directly
#             lg.warn('received event was not delivered to any queue, consume now and send an Ack')
#             # also add more info comming from the queue
#             payload.update(dict(
#                 queue_id=queue_id,
#                 producer_id=producer_id,
#                 message_id=message_id,
#                 created=created,
#             ))
#             events.send(event_id, data=payload)
#             p2p_service.SendAck(newpacket)
#             return True
#         # found a queue for that message, pushing there
#         # TODO: add verification of producer's identity and signature
#         lg.info('pushing event to the queue %s on behalf of producer %s' % (queue_id, producer_id))
#         try:
#             p2p_queue.push_message(
#                 producer_id=producer_id,
#                 queue_id=queue_id,
#                 data=payload,
#                 creation_time=created,
#             )
#         except Exception as exc:
#             lg.warn(exc)
#             p2p_service.SendFail(newpacket, str(exc))
#             return True
#         p2p_service.SendAck(newpacket)
#         return True
