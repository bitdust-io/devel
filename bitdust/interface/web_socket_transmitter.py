#!/usr/bin/python
# api_router.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (api_router.py) is part of BitDust Software.
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
.. module:: api_router

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
from bitdust.lib import serialization

from bitdust.crypt import cipher

from bitdust.main import settings
from bitdust.main import config

#------------------------------------------------------------------------------

_WebSocketListener = None
_WebSocketTransports = {}
_Routes = {}

#------------------------------------------------------------------------------


def init():
    global _WebSocketListener
    if _WebSocketListener is not None:
        lg.warn('_WebSocketListener already initialized')
        return True
    load_routes()
    port = config.conf().getInt('services/api-router/port')
    try:
        ws = WrappedWebSocketFactory(WebSocketFactory())
        _WebSocketListener = listen('tcp:%d' % port, ws)
    except:
        lg.exc()
        return False
    if _Debug:
        lg.out(_DebugLevel, 'api_web_socket.init  _WebSocketListener=%r' % _WebSocketListener)
    return True


def shutdown():
    global _WebSocketListener
    if _WebSocketListener:
        if _Debug:
            lg.out(_DebugLevel, 'api_web_socket.shutdown calling _WebSocketListener.stopListening()')
        _WebSocketListener.stopListening()
        del _WebSocketListener
        _WebSocketListener = None
        if _Debug:
            lg.out(_DebugLevel, '    _WebSocketListener destroyed')
    else:
        lg.warn('_WebSocketListener is None')
    return True


#------------------------------------------------------------------------------


def routes(route_id=None):
    global _Routes
    if route_id is None:
        return _Routes
    return _Routes.get(route_id)


#------------------------------------------------------------------------------


def add_route(idurl):
    global _Routes
    route_id = None
    while not route_id or route_id in _Routes:
        route_id = cipher.generate_secret_text(5)
    # this is where Mobile device will be connecting
    route_url = 'ws://{}:{}/?r={}'.format(
        config.conf().getString('services/api-router/host').strip(),
        config.conf().getInt('services/api-router/port'),
        route_id,
    )
    # this is where BitDust node will be connecting
    internal_url = 'ws://{}:{}/?i={}'.format(
        config.conf().getString('services/api-router/host').strip(),
        config.conf().getInt('services/api-router/port'),
        route_id,
    )
    _Routes[route_id] = {
        'idurl': idurl,
        'route_id': route_id,
        'route_url': route_url,
        'internal_url': internal_url,
    }


def remove_route(route_id):
    global _Routes
    _Routes.pop(route_id, None)


#------------------------------------------------------------------------------


def load_routes():
    pass


#------------------------------------------------------------------------------


class WrappedWebSocketProtocol(txws.WebSocketProtocol):

    route_id = None
    is_client = None

    def validateHeaders(self):
        _, _, parameter = self.location.partition('?')
        param_name, _, route_id = parameter.partition('=')
        # SECURITY
        # TODO: add strict validation of the route_id
        if param_name in ('r', 'route', 'i', 'internal'):
            if not routes(route_id):
                lg.warn('rejected connection %r, route %r is unknown' % (self, route_id))
                return False
        self.is_client = param_name in ('r', 'route')
        self.route_id = route_id
        if _Debug:
            lg.args(_DebugLevel, route_id=route_id, proto=self)
        return txws.WebSocketProtocol.validateHeaders(self)


class WrappedWebSocketFactory(txws.WebSocketFactory):

    protocol = WrappedWebSocketProtocol


#------------------------------------------------------------------------------


class WebSocketProtocol(Protocol):

    _key = None

    def dataReceived(self, data):
        try:
            json_data = serialization.BytesToDict(data, keys_to_text=True, values_to_text=True, encoding='utf-8')
        except:
            lg.exc()
            return
        if _Debug:
            lg.dbg(_DebugLevel, 'received %d bytes from web socket at %r' % (len(data), self._key))
        if not do_process_incoming_message(self.transport.route_id, self.transport.is_client, json_data):
            lg.warn('failed processing incoming message from web socket: %r' % json_data)

    def connectionMade(self):
        global _WebSocketTransports
        Protocol.connectionMade(self)
        peer = self.transport.getPeer()
        self._key = (peer.type, peer.host, peer.port)
        peer_text = '%s://%s:%s' % (self._key[0], self._key[1], self._key[2])
        _WebSocketTransports[self._key] = self.transport
        if _Debug:
            lg.args(_DebugLevel, peer=peer_text, ws_connections=len(_WebSocketTransports))

    def connectionLost(self, *args, **kwargs):
        global _WebSocketTransports
        Protocol.connectionLost(self, *args, **kwargs)
        _WebSocketTransports.pop(self._key)
        peer_text = '%s://%s:%s' % (self._key[0], self._key[1], self._key[2])
        self._key = None
        if _Debug:
            lg.args(_DebugLevel, peer=peer_text, ws_connections=len(_WebSocketTransports))


#------------------------------------------------------------------------------


class WebSocketFactory(Factory):

    protocol = WebSocketProtocol

    def buildProtocol(self, addr):
        proto = Factory.buildProtocol(self, addr)
        return proto


#------------------------------------------------------------------------------


def do_process_incoming_message(route_id, is_client, json_data):
    if _Debug:
        lg.args(_DebugLevel, route_id=route_id, is_client=is_client, json_data=json_data)
    return True


#------------------------------------------------------------------------------


def push(route_id, json_data):
    global _WebSocketTransports
    if not _WebSocketTransports:
        lg.warn('there are currently no web socket transports open')
        return False
    raw_bytes = serialization.DictToBytes(json_data, encoding='utf-8')
    for _key, transp in _WebSocketTransports.items():
        try:
            transp.write(raw_bytes)
        except:
            lg.exc()
            continue
        if _Debug:
            lg.dbg(_DebugLevel, 'sent %d bytes to web socket %s' % (len(raw_bytes), '%s://%s:%s' % (_key[0], _key[1], _key[2])))
    if _Debug:
        lg.out(_DebugLevel, '***   API ROUTE PUSH  %d bytes' % len(raw_bytes))
    return True


#------------------------------------------------------------------------------

if __name__ == '__main__':
    from twisted.internet import reactor
    settings.init()
    lg.set_debug_level(24)
    _Routes['abcd1234'] = {'key': 'abcd1234'}
    init()
    reactor.run()  # @UndefinedVariable
