#!/usr/bin/python
# service_p2p_hookups.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (service_p2p_hookups.py) is part of BitDust Software.
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

module:: service_p2p_hookups
"""

from services.local_service import LocalService


def create_service():
    return P2PHookupsService()


class P2PHookupsService(LocalService):

    service_name = 'service_p2p_hookups'
    config_path = 'services/p2p-hookups/enabled'

    def dependent_on(self):
        from main import settings
        depends = ['service_gateway',
                   'service_identity_propagate', ]
        if settings.enableTCP():
            depends.append('service_tcp_transport')
        if settings.enableUDP():
            depends.append('service_udp_transport')
#         if settings.enablePROXY():
#             depends.append('service_proxy_transport')
        return depends

    def start(self):
        from transport import callback
        from p2p import contact_status
        from p2p import p2p_service
        from p2p import p2p_connector
        from p2p import network_connector
        from twisted.internet.defer import Deferred
        p2p_service.init()
        contact_status.init()
        self._starting_defer = Deferred()
        p2p_connector.A('init')
        p2p_connector.A().addStateChangedCallback(
            self._on_p2p_connector_switched)
        network_connector.A().addStateChangedCallback(
            self._on_network_connector_switched)
        callback.append_inbox_callback(self._on_inbox_packet_received)
        callback.append_inbox_callback(p2p_service.inbox)
        return True

    def stop(self):
        from transport import callback
        from p2p import contact_status
        from p2p import p2p_service
        from p2p import p2p_connector
        from p2p import network_connector
        callback.remove_inbox_callback(self._on_inbox_packet_received)
        callback.remove_inbox_callback(p2p_service.inbox)
        if network_connector.A():
            network_connector.A().removeStateChangedCallback(
                self._on_network_connector_switched)
        p2p_connector.A().removeStateChangedCallback(
            self._on_p2p_connector_switched)
        contact_status.shutdown()
        p2p_connector.Destroy()
        p2p_service.shutdown()
        return True

    def _on_inbox_packet_received(self, newpacket, info, status, error_message):
        from p2p import commands
        if newpacket.Command == commands.Event():
            return self._on_event(newpacket)
        elif newpacket.Command == commands.RequestService():
            return self._send_request_service(newpacket, info)
        elif newpacket.Command == commands.CancelService():
            return self._send_cancel_service(newpacket, info)
        return False

    def _send_request_service(self, newpacket, info):
        from twisted.internet.defer import Deferred
        from logs import lg
        from services import driver
        from p2p import p2p_service
        from transport import packet_out
        if len(newpacket.Payload) > 1024 * 10:
            p2p_service.SendFail(newpacket, 'too long payload')
            return False
        words = newpacket.Payload.split(' ')
        if len(words) < 1:
            lg.warn("got wrong payload in %s" % newpacket)
            p2p_service.SendFail(newpacket, 'wrong payload')
            return False
        service_name = words[0]
        self.log(self.debug_level, "service_p2p_hookups.RequestService %s : %s" % (newpacket.OwnerID, service_name))
        if not driver.is_exist(service_name):
            lg.warn("got wrong payload in %s" % service_name)
            p2p_service.SendFail(newpacket, 'service %s not exist' % service_name)
            return False
        if not driver.is_on(service_name):
            p2p_service.SendFail(newpacket, 'service %s is off' % service_name)
            return False
        try:
            result = driver.request(service_name, newpacket, info)
        except:
            lg.exc()
            p2p_service.SendFail(newpacket, 'request processing failed with exception')
            return False
        if not result:
            self.log(self.debug_level, "service_p2p_hookups._send_request_service SKIP request %s" % service_name)
            return False
        if isinstance(result, Deferred):
            self.log(self.debug_level, "service_p2p_hookups._send_request_service fired delayed execution")
        elif isinstance(result, packet_out.PacketOut):
            self.log(self.debug_level, "service_p2p_hookups._send_request_service outbox packet sent")
        return True

    def _send_cancel_service(self, newpacket, info):
        from twisted.internet.defer import Deferred
        from logs import lg
        from services import driver
        from p2p import p2p_service
        from transport import packet_out
        if len(newpacket.Payload) > 1024 * 10:
            p2p_service.SendFail(newpacket, 'too long payload')
            return False
        words = newpacket.Payload.split(' ')
        if len(words) < 1:
            lg.warn("got wrong payload in %s" % newpacket)
            p2p_service.SendFail(newpacket, 'wrong payload')
            return False
        service_name = words[0]
        self.log(self.debug_level, "service_p2p_hookups.CancelService %s : %s" % (newpacket.OwnerID, service_name))
        # TODO: add validation
        if not driver.is_exist(service_name):
            lg.warn("got wrong payload in %s" % newpacket)
            p2p_service.SendFail(newpacket, 'service %s not exist' % service_name)
            return False
        if not driver.is_on(service_name):
            p2p_service.SendFail(newpacket, 'service %s is off' % service_name)
            return False
        try:
            result = driver.cancel(service_name, newpacket, info)
        except:
            lg.exc()
            p2p_service.SendFail(newpacket, 'request processing failed with exception')
            return False
        if not result:
            self.log(self.debug_level, "service_p2p_hookups._send_cancel_service SKIP request %s" % service_name)
            return False
        if isinstance(result, Deferred):
            self.log(self.debug_level, "service_p2p_hookups._send_cancel_service fired delayed execution")
        elif isinstance(result, packet_out.PacketOut):
            self.log(self.debug_level, "service_p2p_hookups._send_cancel_service outbox packet sent")
        return True

    def _on_event(self, newpacket):
        from logs import lg
        from p2p import p2p_service
        from main import events
        if len(newpacket.Payload) > 1024 * 10:
            p2p_service.SendFail(newpacket, 'too long payload')
            return False
        try:
            import json
            message_json = json.loads(newpacket.Payload)
            message_json['event_id']
            message_json['event_data']
        except:
            lg.exc()
            p2p_service.SendFail(newpacket, 'invalid payload')
            return False
        events.send(message_json['event_id'], message_json['event_data'])
        p2p_service.SendAck(newpacket, response=message_json['event_id'])
        return True

    def _on_p2p_connector_switched(self, oldstate, newstate, evt, args):
        if newstate == 'INCOMMING?':
            if self._starting_defer is not None:
                self._starting_defer.callback(newstate)
                self._starting_defer = None
        from p2p import network_connector
        from system import tray_icon
        if network_connector.A():
            tray_icon.state_changed(network_connector.A().state, newstate)

    def _on_network_connector_switched(self, oldstate, newstate, evt, args):
        from p2p import p2p_connector
        from system import tray_icon
        if oldstate != newstate:
            if newstate == 'CONNECTED' or newstate == 'DISCONNECTED':
                p2p_connector.A('network_connector.state', newstate)
                tray_icon.state_changed(newstate, p2p_connector.A().state)
