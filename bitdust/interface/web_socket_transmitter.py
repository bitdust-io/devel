#!/usr/bin/python
# web_socket_transmitter.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (web_socket_transmitter.py) is part of BitDust Software.
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
.. module:: web_socket_transmitter

Secure remote routed connection to access BitDust nodes from mobile devices.
"""

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

from twisted.application.strports import listen
from twisted.internet.protocol import Protocol, Factory

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.lib import txws
from bitdust.lib import strng
from bitdust.lib import serialization

from bitdust.crypt import cipher

from bitdust.main import config

#------------------------------------------------------------------------------

_WebSocketListener = None
_WebSocketTransports = {}
_WebSocketRouterLocation = None
_Routes = {}
_MaxRoutesNumber = 100

#------------------------------------------------------------------------------


def init():
    global _WebSocketListener
    global _WebSocketRouterLocation
    if _WebSocketListener is not None:
        lg.warn('_WebSocketListener already initialized')
        return True
    host = config.conf().getString('services/web-socket-router/host').strip()
    port = config.conf().getInt('services/web-socket-router/port')
    _WebSocketRouterLocation = 'ws://{}:{}'.format(host, port)
    load_routes()
    try:
        ws = WrappedWebSocketFactory(WebSocketFactory())
        _WebSocketListener = listen('tcp:%d' % port, ws)
    except:
        lg.exc()
        return False
    if _Debug:
        lg.out(_DebugLevel, 'web_socket_transmitter.init  _WebSocketListener=%r' % _WebSocketListener)
    return True


def shutdown():
    global _WebSocketListener
    global _WebSocketRouterLocation
    if _WebSocketListener:
        if _Debug:
            lg.out(_DebugLevel, 'web_socket_transmitter.shutdown calling _WebSocketListener.stopListening()')
        _WebSocketListener.stopListening()
        del _WebSocketListener
        _WebSocketListener = None
        if _Debug:
            lg.out(_DebugLevel, '    _WebSocketListener destroyed')
    else:
        lg.warn('_WebSocketListener is None')
    _WebSocketRouterLocation = None
    return True


#------------------------------------------------------------------------------


def location():
    global _WebSocketRouterLocation
    return _WebSocketRouterLocation


def routes(route_id=None):
    global _Routes
    if route_id is None:
        return _Routes
    return _Routes.get(route_id)


#------------------------------------------------------------------------------

def validate_route_id(route_id):
    # SECURITY
    # TODO: add more strict validation of the route_id
    rid = strng.to_text(route_id)
    if len(rid) != 8:
        raise Exception('invalid route_id length')
    return rid

#------------------------------------------------------------------------------

def add_route():
    global _Routes
    route_id = None
    while not route_id or route_id in _Routes:
        route_id = cipher.generate_secret_text(5)
    # this is where Mobile device will be connecting
    route_url = 'ws://{}:{}/?r={}'.format(
        config.conf().getString('services/web-socket-router/host').strip(),
        config.conf().getInt('services/web-socket-router/port'),
        route_id,
    )
    # this is where BitDust node will be connecting
    internal_url = 'ws://{}:{}/?i={}'.format(
        config.conf().getString('services/web-socket-router/host').strip(),
        config.conf().getInt('services/web-socket-router/port'),
        route_id,
    )
    _Routes[route_id] = {
        'route_id': route_id,
        'route_url': route_url,
        'external_transport': None,
        'internal_url': internal_url,
        'internal_transport': None,
    }
    if _Debug:
        lg.args(_DebugLevel, route_id=route_id, routes=len(_Routes))
    return route_id


def remove_route(route_id):
    global _Routes
    _Routes.pop(route_id, None)
    if _Debug:
        lg.args(_DebugLevel, route_id=route_id, routes=len(_Routes))


#------------------------------------------------------------------------------


def load_routes():
    pass


#------------------------------------------------------------------------------


class WrappedWebSocketProtocol(txws.WebSocketProtocol):

    route_id = None
    direction = None

    def validateHeaders(self):
        _, _, parameter = self.location.partition('?')
        if not parameter:
            return txws.WebSocketProtocol.validateHeaders(self)
        param_name, _, route_id = parameter.partition('=')
        try:
            validate_route_id(route_id)
        except:
            lg.exc()
            return False
        if param_name in ('r', 'route', 'i', 'internal'):
            if not routes(route_id):
                lg.warn('rejected connection %r, route %r is unknown' % (self, route_id))
                return False
        else:
            lg.warn('rejected connection %r, invalid input parameters' % self)
            return False
        if route_id:
            self.direction = 'internal' if param_name in ('i', 'internal') else 'external'
            self.route_id = route_id
            if self.route_id in routes():
                routes(self.route_id)[self.direction+'_transport'] = self
                if _Debug:
                    lg.dbg(_DebugLevel, 'registered %s transport %s for route %s' % (self.direction, self, self.route_id))
            else:
                lg.warn('route %s was not registered' % self.route_id)
                return False
        if _Debug:
            lg.args(_DebugLevel, route_id=self.route_id, direction=self.direction, transport=self)
        return txws.WebSocketProtocol.validateHeaders(self)


class WrappedWebSocketFactory(txws.WebSocketFactory):

    protocol = WrappedWebSocketProtocol


#------------------------------------------------------------------------------


class WebSocketProtocol(Protocol):

    _key = None

    def dataReceived(self, raw_data):
        if _Debug:
            lg.args(_DebugLevel, raw_data=raw_data)
        try:
            json_data = serialization.BytesToDict(raw_data, keys_to_text=True, values_to_text=True, encoding='utf-8')
        except:
            lg.exc()
            return
        if _Debug:
            lg.dbg(_DebugLevel, 'received %d bytes from web socket at %r' % (len(raw_data), self._key))
        if not do_process_incoming_message(self.transport, json_data, raw_data):
            lg.warn('failed processing incoming message from web socket: %r' % json_data)
            self.transport.loseConnection()

    def connectionMade(self):
        global _WebSocketTransports
        Protocol.connectionMade(self)
        peer = self.transport.getPeer()
        self._key = (peer.type, peer.host, peer.port)
        peer_text = '%s://%s:%s' % (self._key[0], self._key[1], self._key[2])
        _WebSocketTransports[self._key] = self.transport
        if _Debug:
            lg.args(_DebugLevel, peer=peer_text, transport=self.transport, ws_connections=len(_WebSocketTransports))

    def connectionLost(self, *args, **kwargs):
        if _Debug:
            lg.args(_DebugLevel, args=args, kwargs=kwargs)
        global _WebSocketTransports
        Protocol.connectionLost(self, *args, **kwargs)
        _WebSocketTransports.pop(self._key)
        peer_text = '%s://%s:%s' % (self._key[0], self._key[1], self._key[2])
        self._key = None
        route_id = None
        direction = None
        try:
            route_id = self.transport.route_id
            direction = self.transport.direction
        except:
            lg.exc()
        cleaned = False
        if route_id and direction:
            if routes(route_id):
                if routes(route_id).get(direction+'_transport'):
                    routes(route_id)[direction+'_transport'] = None
                    cleaned = True
        if _Debug:
            lg.args(_DebugLevel, peer=peer_text, transport=self.transport, ws_connections=len(_WebSocketTransports), route_id=route_id, direction=direction, cleaned=cleaned)


#------------------------------------------------------------------------------


class WebSocketFactory(Factory):

    protocol = WebSocketProtocol

    def buildProtocol(self, addr):
        proto = Factory.buildProtocol(self, addr)
        return proto


#------------------------------------------------------------------------------

def do_process_incoming_message(transport, json_data, raw_data):
    global _MaxRoutesNumber
    route_id = transport.route_id
    direction = transport.direction
    if _Debug:
        lg.args(_DebugLevel, route_id=route_id, direction=direction, json_data=json_data)
    if route_id is None and direction is None:
        if json_data.get('cmd') == 'connect-request':
            if len(routes()) >= _MaxRoutesNumber:
                if _Debug:
                    lg.dbg(_DebugLevel, 'request for a new route from %r was rejected: too many routes are currently registered' % transport)
                return False
            route_id = add_route()
            route_info = routes(route_id)
            json_response = {
                'result': 'accepted',
                'route_id': route_id, 
            }
            response_raw_data = serialization.DictToBytes(json_response, encoding='utf-8')
            try:
                transport.write(response_raw_data)
            except:
                lg.exc()
                return False
            if _Debug:
                lg.out(_DebugLevel, '    wrote %d bytes to %s/%s at %r' % (len(response_raw_data), route_id, direction, transport))
            return True
        return False
    if not route_id:
        lg.warn('unknown route ID: %r' % transport)
        return False
    if not direction:
        lg.warn('route direction was not identified: %r' % transport)
        return False
    cmd = json_data.get('cmd')
    if cmd == 'handshake':
        if json_data.get('internal') and direction == 'internal':
            route_info = routes(route_id)
            route_url = route_info['route_url'] if route_info else None
            if not route_url:
                lg.warn('route info for %r was not found' % route_id)
                return False
            json_response = {
                "cmd": "handshake-accepted",
                "route_url": route_url,
            }
            response_raw_data = serialization.DictToBytes(json_response, encoding='utf-8')
            try:
                transport.write(response_raw_data)
            except:
                lg.exc()
                return False
            if _Debug:
                lg.out(_DebugLevel, '    wrote %d bytes to %s/%s at %r' % (len(response_raw_data), route_id, direction, transport))
            return True
    call_id = json_data.get('call_id')
    if call_id or (cmd in ('api', 'response', 'push', 'server-public-key', 'client-public-key', 'server-code', 'client-code', )):
        route_info = routes(route_id)
        if _Debug:
            lg.args(_DebugLevel, direction=direction, route_info=route_info)
        if not route_info:
            lg.warn('route info for %r was not found' % route_id)
            return False
        if direction == 'external':
            internal_transport = route_info.get('internal_transport')
            if not internal_transport:
                lg.warn('internal transport for route %r is not connected' % route_id)
                return False
            try:
                internal_transport.write(raw_data)
            except:
                lg.exc()
                return False
            if _Debug:
                lg.out(_DebugLevel, '    wrote %d bytes to %s/%s at %r' % (len(raw_data), route_id, 'internal', internal_transport))
            return True
        if direction == 'internal':
            external_transport = route_info.get('external_transport')
            if not external_transport:
                lg.warn('external transport for route %r is not connected' % route_id)
                return False
            try:
                external_transport.write(raw_data)
            except:
                lg.exc()
                return False
            if _Debug:
                lg.out(_DebugLevel, '    wrote %d bytes to %s/%s at %r' % (len(raw_data), route_id, 'external', external_transport))
            return True
        lg.warn('unexpected direction: %r' % direction)
    return False
