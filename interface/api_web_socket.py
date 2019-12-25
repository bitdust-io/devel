#!/usr/bin/python
# api_web_socket.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (api_web_socket.py) is part of BitDust Software.
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

module:: api_web_socket
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

from twisted.internet.protocol import Protocol, Factory
from twisted.application.strports import listen

#------------------------------------------------------------------------------

from logs import lg

from lib import txws
from lib import serialization

from main import events
from main import settings

#------------------------------------------------------------------------------

_WebSocketListener = None
_WebSocketTransport = None

#------------------------------------------------------------------------------

def init(port=None):
    global _WebSocketListener
    if _Debug:
        lg.out(_DebugLevel, 'api_web_socket.init  _WebSocketListener=%r' % _WebSocketListener)
    if _WebSocketListener is not None:
        lg.warn('_WebSocketListener already initialized')
    else:
        if not port:
            port = settings.DefaultWebSocketPort()
        try:
            ws = txws.WebSocketFactory(BitDustWebSocketFactory())
            _WebSocketListener = listen("tcp:%d" % port, ws)
        except:
            lg.exc()
    events.add_subscriber(on_event, event_id='*')


def shutdown():
    global _WebSocketListener
    events.remove_subscriber(on_event, event_id='*')
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

#------------------------------------------------------------------------------

class BitDustWebSocketProtocol(Protocol):

    def dataReceived(self, data):
        if _Debug:
            lg.dbg(_DebugLevel, 'received %d bytes from web socket' % len(len(data)))

    def connectionMade(self):
        Protocol.connectionMade(self)
        global _WebSocketTransport
        _WebSocketTransport = self.transport
        peer = _WebSocketTransport.getPeer()
        events.send('web-socket-connected', data=dict(peer='%s://%s:%s' % (peer.type, peer.host, peer.port)))

    def connectionLost(self, *args, **kwargs):
        Protocol.connectionLost(self, *args, **kwargs)
        global _WebSocketTransport
        _WebSocketTransport = None
        events.send('web-socket-disconnected', data=dict())

#------------------------------------------------------------------------------

class BitDustWebSocketFactory(Factory):

    protocol = BitDustWebSocketProtocol

    def buildProtocol(self, addr):
        """
        Only accepting connections from local machine!
        """
        global _WebSocketTransport
        if _WebSocketTransport:
            lg.warn('refused connection to web socket - another connection already made')
            return None
        if addr.host != '127.0.0.1':
            lg.err('refused connection from remote host: %r' % addr.host)
            return None
        proto = Factory.buildProtocol(self, addr)
        return proto

#------------------------------------------------------------------------------

def on_event(evt):
    return push({
        'type': 'event',
        'payload': {
            'event_id': evt.event_id,
            'data': evt.data,
        },
    })


def on_private_message(message_json):
    return push({
        'type': 'private_message',
        'payload': message_json,
    })

#------------------------------------------------------------------------------

def push(json_data):
    global _WebSocketTransport
    if not _WebSocketTransport:
        return False
    raw_bytes = serialization.DictToBytes(json_data)
    _WebSocketTransport.write(raw_bytes)
    if _Debug:
        lg.dbg(_DebugLevel, 'sent %d bytes to web socket' % len(raw_bytes))
    return True
