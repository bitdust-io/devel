#!/usr/bin/python
# service_broadcasting.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (service_broadcasting.py) is part of BitDust Software.
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

module:: service_broadcasting
"""

from __future__ import absolute_import
from services.local_service import LocalService


def create_service():
    return BroadcastingService()


class BroadcastingService(LocalService):

    service_name = 'service_broadcasting'
    config_path = 'services/broadcasting/enabled'

    scope = []  # set to [idurl1,idurl2,...] to receive only messages broadcasted from certain nodes
    # TODO: need to be able dynamically add/remove scope after start of the service
    # for now let's just listen for all broadcast messages (global scope)

    def dependent_on(self):
        return [
            'service_p2p_hookups',
            'service_nodes_lookup',
        ]

    def installed(self):
        # TODO: to be continue...
        return False

    def start(self):
        from twisted.internet.defer import Deferred
        from broadcast import broadcasters_finder
        from broadcast import broadcaster_node
        from broadcast import broadcast_listener
        from broadcast import broadcast_service
        from main.config import conf
        from main import settings
        self.starting_deferred = Deferred()
        broadcasters_finder.A('init')
        if settings.enableBroadcastRouting():
            broadcaster_node.A('init', broadcast_service.on_incoming_broadcast_message)
            broadcaster_node.A().addStateChangedCallback(
                self._on_broadcaster_node_switched)
        else:
            broadcast_listener.A('init', broadcast_service.on_incoming_broadcast_message)
            broadcast_listener.A().addStateChangedCallback(
                self._on_broadcast_listener_switched)
            broadcast_listener.A('connect', self.scope)
        conf().addCallback(
            'services/broadcasting/routing-enabled',
            self._on_broadcast_routing_enabled_disabled
        )
        return self.starting_deferred

    def stop(self):
        from broadcast import broadcaster_node
        from broadcast import broadcasters_finder
        from broadcast import broadcast_listener
        from main.config import conf
        broadcasters_finder.A('shutdown')
        if broadcaster_node.A() is not None:
            broadcaster_node.A().removeStateChangedCallback(
                self._on_broadcaster_node_switched)
            broadcaster_node.A('shutdown')
        if broadcast_listener.A() is not None:
            broadcast_listener.A().removeStateChangedCallback(
                self._on_broadcast_listener_switched)
            broadcast_listener.A('shutdown')
        conf().removeCallback('services/broadcasting/routing-enabled')
        return True

    def request(self, json_payload, newpacket, info):
        from logs import lg
        from p2p import p2p_service
        from main import settings
        # words = newpacket.Payload.split(' ')
        try:
            mode = json_payload['action']
        except:
            lg.exc()
            return p2p_service.SendFail(newpacket, 'invalid json payload')
        if mode != 'route' and mode != 'listen':
            lg.out(8, "service_broadcasting.request DENIED, wrong mode provided : %s" % mode)
            return p2p_service.SendFail(newpacket, 'invalid request')
        if not settings.enableBroadcastRouting():
            lg.out(8, "service_broadcasting.request DENIED, broadcast routing disabled")
            return p2p_service.SendFail(newpacket, 'broadcast routing disabled')
        from broadcast import broadcaster_node
        if not broadcaster_node.A():
            lg.out(8, "service_broadcasting.request DENIED, broadcast routing disabled")
            return p2p_service.SendFail(newpacket, 'broadcast routing disabled')
        if broadcaster_node.A().state not in ['BROADCASTING', 'OFFLINE', 'BROADCASTERS?', ]:
            lg.out(8, "service_broadcasting.request DENIED, current state is : %s" % broadcaster_node.A().state)
            return p2p_service.SendFail(newpacket, 'currently not broadcasting')
        if mode == 'route':
            broadcaster_node.A('new-broadcaster-connected', newpacket.OwnerID)
            lg.out(8, "service_broadcasting.request ACCEPTED, mode: %s" % mode)
            return p2p_service.SendAck(newpacket, 'accepted')
        if mode == 'listen':
            # TODO: fix!!!
            # broadcaster_node.A().add_listener(newpacket.OwnerID, ' '.join(words[2:]))
            lg.out(8, "service_broadcasting.request ACCEPTED, mode: %s" % mode)
            return p2p_service.SendAck(newpacket, 'accepted')
        return p2p_service.SendAck(newpacket, 'bad request')

    def health_check(self):
        from broadcast import broadcaster_node
        return broadcaster_node.A().state in ['BROADCASTING', ]

    def _on_broadcast_routing_enabled_disabled(self, path, value, oldvalue, result):
        from logs import lg
        from broadcast import broadcaster_node
        from broadcast import broadcast_listener
        from broadcast import broadcast_service
        lg.out(2, 'service_broadcasting._on_broadcast_routing_enabled_disabled : %s->%s : %s' % (
            oldvalue, value, path))
        if not value:
            if broadcaster_node.A() is not None:
                broadcaster_node.A().removeStateChangedCallback(
                    self._on_broadcaster_node_switched)
                broadcaster_node.A('shutdown')
            broadcast_listener.A('init', broadcast_service.on_incoming_broadcast_message)
            broadcast_listener.A().addStateChangedCallback(
                self._on_broadcast_listener_switched)
            broadcast_listener.A('connect', self.scope)
        else:
            if broadcast_listener.A() is not None:
                broadcast_listener.A().removeStateChangedCallback(
                    self._on_broadcast_listener_switched)
                broadcast_listener.A('shutdown')
            broadcaster_node.A('init', broadcast_service.on_incoming_broadcast_message)
            broadcaster_node.A().addStateChangedCallback(
                self._on_broadcaster_node_switched)

    def _on_broadcast_listener_switched(self, oldstate, newstate, evt, *args, **kwargs):
        from logs import lg
        from twisted.internet import reactor  # @UnresolvedImport
        from broadcast import broadcast_listener
        if self.starting_deferred:
            if newstate in ['LISTENING', 'OFFLINE', ]:
                self.starting_deferred.callback(newstate)
                self.starting_deferred = None
        if newstate == 'OFFLINE':
            reactor.callLater(60, broadcast_listener.A, 'connect', self.scope)  # @UndefinedVariable
            lg.out(8, 'service_broadcasting._on_broadcast_listener_switched will try to connect again after 1 minute')

    def _on_broadcaster_node_switched(self, oldstate, newstate, evt, *args, **kwargs):
        from logs import lg
        from twisted.internet import reactor  # @UnresolvedImport
        from broadcast import broadcaster_node
        if self.starting_deferred:
            if newstate in ['BROADCASTING', 'OFFLINE', ]:
                self.starting_deferred.callback(newstate)
                self.starting_deferred = None
        if newstate == 'OFFLINE' and oldstate != 'AT_STARTUP':
            reactor.callLater(60, broadcaster_node.A, 'reconnect')  # @UndefinedVariable
            lg.out(8, 'service_broadcasting._on_broadcaster_node_switched will try to reconnect again after 1 minute')


#     def cancel(self, json_payload, request, info):
#         from logs import lg
#         from p2p import p2p_service
#         words = request.Payload.split(' ')
#         try:
#             mode = words[1][:20]
#         except:
#             lg.exc()
#             return p2p_service.SendFail(request, 'wrong mode provided')
#         if mode == 'route' and False: # and not settings.getBroadcastRoutingEnabled():
#             # TODO check if this is enabled in settings
#             # so broadcaster_node should be existing already
#             lg.out(8, "service_broadcasting.request DENIED, broadcast routing disabled")
#             return p2p_service.SendFail(request, 'broadcast routing disabled')
#         from broadcast import broadcaster_node
#         if broadcaster_node.A().state not in ['BROADCASTING', ]:
#             lg.out(8, "service_broadcasting.request DENIED, current state is : %s" % broadcaster_node.A().state)
#             return p2p_service.SendFail(request, 'currently not broadcasting')
#         broadcaster_node.A('broadcaster-disconnected', request)
#         return p2p_service.SendAck(request, 'accepted')
