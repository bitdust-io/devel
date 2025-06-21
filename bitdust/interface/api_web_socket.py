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

_Debug = False
_DebugLevel = 10

_APILogFileEnabled = False

#------------------------------------------------------------------------------

from twisted.application.strports import listen
from twisted.internet.defer import Deferred
from twisted.internet.protocol import Protocol, Factory
from twisted.python.failure import Failure

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.lib import txws
from bitdust.lib import serialization

from bitdust.system import local_fs

from bitdust.main import events
from bitdust.main import settings

from bitdust.interface import api

#------------------------------------------------------------------------------

_WebSocketListener = None
_WebSocketTransports = {}
_AllAPIMethods = []
_APISecret = None

#------------------------------------------------------------------------------


def init(port=None):
    global _WebSocketListener
    global _AllAPIMethods
    global _APILogFileEnabled
    _APILogFileEnabled = settings.config.conf().getBool('logs/api-enabled')
    if _WebSocketListener is not None:
        lg.warn('_WebSocketListener already initialized')
        return
    if not port:
        port = settings.DefaultWebSocketPort()
    try:
        ws = WrappedWebSocketFactory(WebSocketFactory())
        _WebSocketListener = listen('tcp:%d' % port, ws)
    except:
        lg.exc()
        return
    _AllAPIMethods = set(dir(api))
    _AllAPIMethods.difference_update(
        [
            # TODO: keep that list up to date when changing the api
            'reactor',
            'on_api_result_prepared',
            'Deferred',
            'ERROR',
            'Failure',
            'OK',
            'RESULT',
            '_Debug',
            '_DebugLevel',
            '_APILogFileEnabled',
            'strng',
            'sys',
            'time',
            'gc',
            'map',
            'os',
            '__builtins__',
            '__cached__',
            '__doc__',
            '__file__',
            '__loader__',
            '__name__',
            '__package__',
            '__spec__',
            'absolute_import',
            'driver',
            'filemanager',
            'jsn',
            'lg',
        ]
    )
    if _Debug:
        lg.out(_DebugLevel, 'api_web_socket.init  _WebSocketListener=%r with %d methods:\n%r' % (_WebSocketListener, len(_AllAPIMethods), _AllAPIMethods))
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


class WrappedWebSocketProtocol(txws.WebSocketProtocol):

    def validateHeaders(self):
        global _APISecret
        if _APISecret:
            access_granted = False
            _, _, api_secret_parameter = self.location.partition('?')
            param_name, _, api_secret_parameter = api_secret_parameter.partition('=')
            if param_name == 'a' or param_name == 'api_secret':
                if api_secret_parameter == _APISecret:
                    access_granted = True
            if not access_granted:
                events.send('web-socket-access-denied', data=dict())
                # self.loseConnection()
                return False
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
            lg.dbg(_DebugLevel, 'received %d bytes from web socket: %r' % (len(data), json_data))
        if not do_process_incoming_message(json_data):
            lg.warn('failed processing incoming message from web socket: %r' % json_data)

    def connectionMade(self):
        global _WebSocketTransports
        Protocol.connectionMade(self)
        peer = self.transport.getPeer()
        self._key = (peer.type, peer.host, peer.port)
        peer_text = '%s://%s:%s' % (self._key[0], self._key[1], self._key[2])
        _WebSocketTransports[self._key] = self.transport
        if _Debug:
            lg.args(_DebugLevel, key=self._key, ws_connections=len(_WebSocketTransports))
        events.send('web-socket-connected', data=dict(peer=peer_text))

    def connectionLost(self, *args, **kwargs):
        global _WebSocketTransports
        if _Debug:
            lg.args(_DebugLevel, key=self._key, ws_connections=len(_WebSocketTransports))
        Protocol.connectionLost(self, *args, **kwargs)
        _WebSocketTransports.pop(self._key)
        peer_text = '%s://%s:%s' % (self._key[0], self._key[1], self._key[2])
        self._key = None
        events.send('web-socket-disconnected', data=dict(peer=peer_text))


#------------------------------------------------------------------------------


class WebSocketFactory(Factory):

    protocol = WebSocketProtocol

    def buildProtocol(self, addr):
        """
        Only accepting connections from local machine!
        """
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
            lg.warn('api method name was not provided')
            return push({
                'type': 'api_call',
                'payload': {
                    'call_id': call_id,
                    'errors': ['api method name was not provided'],
                },
            })

        if method not in _AllAPIMethods:
            lg.warn('invalid api method name: %r' % method)
            return push({
                'type': 'api_call',
                'payload': {
                    'call_id': call_id,
                    'errors': ['invalid api method name'],
                },
            })

        if _Debug:
            lg.out(_DebugLevel, '*** %s  API WS IN  %s(%r)' % (call_id, method, kwargs))

        if _APILogFileEnabled:
            lg.out(0, '*** %s  WS IN  %s(%r)' % (call_id, method, kwargs), log_name='api', showtime=True)

        func = getattr(api, method)
        try:
            response = func(**kwargs)
        except Exception as err:
            lg.err(f'{method}({kwargs}) : {err}')
            return push({
                'type': 'api_call',
                'payload': {
                    'call_id': call_id,
                    'errors': [str(err)],
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
                        'errors': [err_msg],
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


def on_stream_message(message_json):
    return push({
        'type': 'stream_message',
        'payload': message_json,
    })


def on_online_status_changed(status_info):
    return push({
        'type': 'online_status',
        'payload': status_info,
    })


def on_model_changed(snapshot_object):
    return push({
        'type': 'model',
        'payload': snapshot_object.to_json(),
    })


#------------------------------------------------------------------------------


def push(json_data):
    global _WebSocketTransports
    if not _WebSocketTransports:
        # lg.warn('there are currently no web socket transports open')
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
        lg.out(_DebugLevel, '***   API WS PUSH  %d bytes' % len(raw_bytes))
    if _APILogFileEnabled:
        lg.out(
            0,
            '*** WS PUSH  %d bytes : %r' % (
                len(raw_bytes),
                json_data,
            ),
            log_name='api',
            showtime=True,
        )
    return True
