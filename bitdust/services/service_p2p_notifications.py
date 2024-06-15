#!/usr/bin/python
# service_p2p_notifications.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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
from bitdust.services.local_service import LocalService


def create_service():
    return P2PNotificationsService()


class P2PNotificationsService(LocalService):

    service_name = 'service_p2p_notifications'
    config_path = 'services/p2p-notifications/enabled'

    def dependent_on(self):
        from bitdust.main import settings
        depends = [
            'service_p2p_hookups',
        ]
        if settings.enablePROXY():
            depends.append('service_proxy_transport')
        return depends

    def start(self):
        from twisted.internet.task import LoopingCall
        from bitdust.transport import callback
        from bitdust.stream import p2p_queue
        p2p_queue.init()
        callback.append_inbox_callback(self._on_inbox_packet_received)
        self.reconnect_task = LoopingCall(self._on_check_network_connect)
        self.reconnect_task.start(30, now=False)
        return True

    def stop(self):
        from bitdust.transport import callback
        from bitdust.stream import p2p_queue
        if self.reconnect_task and self.reconnect_task.running:
            self.reconnect_task.stop()
        self.reconnect_task = None
        callback.remove_inbox_callback(self._on_inbox_packet_received)
        p2p_queue.shutdown()
        return True

    def request(self, json_payload, newpacket, info):
        from bitdust.logs import lg
        from bitdust.lib import serialization
        from bitdust.p2p import p2p_service
        from bitdust.stream import p2p_queue
        try:
            service_requests_list = json_payload['items']
        except:
            lg.exc()
            return p2p_service.SendFail(newpacket, 'invalid payload')
        service_responses_list = []
        for r_json in service_requests_list:
            resp = r_json.copy()
            r_scope = r_json.get('scope', '')
            r_action = r_json.get('action', '')
            try:
                if r_scope == 'queue':
                    if r_action == 'open':
                        resp['result'] = 'denied' if not p2p_queue.open_queue(queue_id=r_json.get('queue_id')) else 'OK'
                    elif r_action == 'close':
                        resp['result'] = 'denied' if not p2p_queue.close_queue(queue_id=r_json.get('queue_id')) else 'OK'
                elif r_scope == 'consumer':
                    if r_action == 'start':
                        resp['result'] = 'denied' if not p2p_queue.add_consumer(consumer_id=r_json.get('consumer_id')) else 'OK'
                    elif r_action == 'stop':
                        resp['result'] = 'denied' if not p2p_queue.remove_consumer(consumer_id=r_json.get('consumer_id')) else 'OK'
                    elif r_action == 'add_callback':
                        resp['result'] = 'denied' if not p2p_queue.add_callback_method(
                            consumer_id=r_json.get('consumer_id'),
                            callback_method=r_json.get('method'),
                            interested_queues_list=r_json.get('queues') or None,
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
                            resp['result'] = 'denied' if not p2p_queue.add_producer(producer_id=r_json.get('producer_id')) else 'OK'
                        elif r_action == 'stop':
                            resp['result'] = 'denied' if not p2p_queue.remove_producer(producer_id=r_json.get('producer_id')) else 'OK'
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
            lg.out(self.debug_level, 'service_p2p_notifications.request  %s:%s  is  [%s] : %s' % (r_scope, r_action, resp['result'], resp.get('reason', 'OK')))
        payload = serialization.DictToBytes({'items': service_responses_list}, values_to_text=True)
        return p2p_service.SendAck(newpacket, payload)

    def cancel(self, json_payload, newpacket, info):
        # TODO: work in progress
        return False

    def _on_inbox_packet_received(self, newpacket, info, status, error_message):
        from bitdust.p2p import commands
        from bitdust.stream import p2p_queue
        if newpacket.Command != commands.Event():
            return False
        return p2p_queue.on_event_packet_received(newpacket, info, status, error_message)

    def _on_check_network_connect(self):
        from bitdust.p2p import network_service
        from bitdust.userid import my_id
        if my_id.isLocalIdentityReady():
            network_service.connected(wait_timeout=0.1)
        return None
