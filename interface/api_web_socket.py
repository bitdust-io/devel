#!/usr/bin/python
# api_web_socket.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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

_Debug = True
_DebugLevel = 10

_APILogFileEnabled = True

#------------------------------------------------------------------------------

from twisted.application.strports import listen
from twisted.internet.defer import Deferred
from twisted.internet.protocol import Protocol, Factory
from twisted.python.failure import Failure

#------------------------------------------------------------------------------

from logs import lg

from lib import txws
from lib import serialization

from system import local_fs

from main import events
from main import settings

from interface import api

#------------------------------------------------------------------------------

_WebSocketListener = None
_WebSocketTransport = None
_AllAPIMethods = []
_APISecret = None

#------------------------------------------------------------------------------

def init(port=None):
    global _WebSocketListener
    global _AllAPIMethods
    if _Debug:
        lg.out(_DebugLevel, 'api_web_socket.init  _WebSocketListener=%r' % _WebSocketListener)
    if _WebSocketListener is not None:
        lg.warn('_WebSocketListener already initialized')
        return
    if not port:
        port = settings.DefaultWebSocketPort()
    try:
        ws = BitDistWrappedWebSocketFactory(BitDustWebSocketFactory())
        _WebSocketListener = listen("tcp:%d" % port, ws)
    except:
        lg.exc()
        return
    _AllAPIMethods = set(dir(api))
    _AllAPIMethods.difference_update([
        # TODO: keep that list up to date when changing the api
        'on_api_result_prepared', 'Deferred', 'ERROR', 'Failure', 'OK', 'RESULT', '_Debug', '_DebugLevel',
        'strng', 'sys', 'time', 'gc', 'map', 'os',
        '__builtins__', '__cached__', '__doc__', '__file__', '__loader__', '__name__', '__package__', '__spec__',
        'absolute_import', 'driver', 'filemanager', 'jsn', 'lg',
        'event_listen', 'message_receive', 'process_debug', 
    ])
    read_api_secret()
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

def read_api_secret():
    global _APISecret
    _APISecret = local_fs.ReadTextFile(settings.APISecretFile())

#------------------------------------------------------------------------------

class BitDustWrappedWebSocketProtocol(txws.WebSocketProtocol):

    def validateHeaders(self):
        global _APISecret
        if _APISecret:
            _, _, api_secret_parameter = self.location.partition('?')
            _, _, api_secret_parameter = api_secret_parameter.partition('=')
            if api_secret_parameter != _APISecret:
                events.send('web-socket-access-denied', data=dict())
                self.loseConnection()
                return
        return txws.WebSocketProtocol.validateHeaders(self)


class BitDistWrappedWebSocketFactory(txws.WebSocketFactory):

    protocol = BitDustWrappedWebSocketProtocol


#------------------------------------------------------------------------------

class BitDustWebSocketProtocol(Protocol):

    def dataReceived(self, data):
        try:
            json_data = serialization.BytesToDict(data, keys_to_text=True, values_to_text=True)
        except:
            lg.exc()
            return
        if _Debug:
            lg.dbg(_DebugLevel, 'received %d bytes from web socket: %r' % (len(data), json_data))
        if not do_process_incoming_message(json_data):
            lg.warn('failed processing incoming message from web socket: %r' % json_data)

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

def do_process_incoming_message(json_data):
    global _AllAPIMethods
    command = json_data.get('command')
    if command == 'api_call':
        method = json_data.get('method', None)
        kwargs = json_data.get('kwargs', {})
        call_id = json_data.get('call_id', None)

        if not method:
            lg.warn('no api method provided in the call')
            return False

        if method not in _AllAPIMethods:
            lg.warn('wrong api method called: %r' % method)
            return False

        if _APILogFileEnabled:
            lg.out(0, '*** %s  WS IN  %s(%r)' % (
                call_id, method, kwargs), log_name='api')

        func = getattr(api, method)
        try:
            response = func(**kwargs)
        except Exception as err:
            lg.exc()
            return push({
                    'type': 'api_call',
                    'payload': {
                        'call_id': call_id,
                        'errors': [str(err), ],
                    },
                })

        if isinstance(response, Deferred):

            def _cb(r):
                return push({
                    'type': 'api_call',
                    'payload': {
                        'call_id': call_id,
                        'response': r,
                    },
                })

            def _eb(err):
                err_msg = err.getErrorMessage() if isinstance(err, Failure) else str(err)
                return push({
                    'type': 'api_call',
                    'payload': {
                        'call_id': call_id,
                        'errors': [err_msg, ],
                    },
                })
                
            response.addCallback(_cb)
            response.addErrback(_eb)
            return True

        return push({
            'type': 'api_call',
            'payload': {
                'call_id': call_id,
                'response': response,
            },
        })

    return False

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


def on_online_status_changed(status_info):
    return push({
        'type': 'online_status',
        'payload': status_info,
    })

#------------------------------------------------------------------------------

def push(json_data):
    global _WebSocketTransport
    if not _WebSocketTransport:
        return False
    raw_bytes = serialization.DictToBytes(json_data)
    _WebSocketTransport.write(raw_bytes)
    if _Debug:
        lg.dbg(_DebugLevel, 'sent %d bytes to web socket: %r' % (len(raw_bytes), json_data))
    if _APILogFileEnabled:
        lg.out(0, '*** WS PUSH  %d bytes : %r' % (len(json_data), json_data, ), log_name='api')
    return True
