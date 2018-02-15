#!/usr/bin/python
# service_p2p_notifications.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
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

from services.local_service import LocalService


def create_service():
    return P2PNotificationsService()


class P2PNotificationsService(LocalService):

    service_name = 'service_p2p_notifications'
    config_path = 'services/p2p-notifications/enabled'

    def dependent_on(self):
        return [
            'service_p2p_hookups',
        ]

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
        import json
        from logs import lg
        from p2p import p2p_service
        from p2p import p2p_queue
        try:
            # service_info_json = json.loads(newpacket.Payload)
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
                lg.exc()
                resp['result'] = 'denied'
                resp['reason'] = str(exc)
            service_responses_list.append(resp)
        return p2p_service.SendAck(newpacket, json.dumps({'items': service_responses_list}))

    def cancel(self, json_payload, newpacket, info):
        # TODO: work in progress
        return False

    def _on_inbox_packet_received(self, newpacket, info, status, error_message):
        import json
        from logs import lg
        from main import events
        from p2p import commands
        from p2p import p2p_service
        from p2p import p2p_queue
        if newpacket.Command != commands.Event():
            return False
        try:
            e_json = json.loads(newpacket.Payload)
            event_id = e_json['event_id']
            payload = e_json['payload']
            producer_id = e_json.get('producer_id')
            message_id = e_json.get('message_id')
            created = e_json.get('created')
        except:
            lg.warn("invlid json payload")
            return False
        if producer_id and message_id:
            # this message have an ID and producer so it came from a queue and needs to be consumed
            events.send(event_id, data=payload, created=created)
            p2p_service.SendAck(newpacket)
            return True
        if event_id not in p2p_queue.queue():
            # this message does not have an ID or producer so needs to be published in the queue
            # but only if given queue is already existing on that node
            # otherwise it is probably addressed to that node and needs to be consumed directly
            lg.warn('received event was not delivered to any queue, consume now and send an Ack')
            events.send(event_id, data=payload, created=created)
            return True

        # TODO: add verification of producer's identity and signature
        try:
            p2p_queue.push_message(
                producer_id=producer_id,
                queue_id=event_id,
                data=payload,
                creation_time=created,
            )
        except Exception as exc:
            lg.warn(exc)
            p2p_service.SendFail(newpacket, str(exc))
            return True
        p2p_service.SendAck(newpacket)
        return True
