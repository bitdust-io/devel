#!/usr/bin/env python
# routed_web_socket.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (routed_web_socket.py) is part of BitDust Software.
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
.. module:: routed_web_socket
.. role:: red

BitDust routed_web_socket() Automat

EVENTS:
    * :red:`api-message`
    * :red:`auth-error`
    * :red:`client-code-input-received`
    * :red:`client-pub-key-received`
    * :red:`lookup-failed`
    * :red:`router-disconnected`
    * :red:`routers-connected`
    * :red:`routers-failed`
    * :red:`routers-selected`
    * :red:`server-code-failed`
    * :red:`start`
    * :red:`stop`
    * :red:`timer-1min`
    * :red:`timer-5min`
    * :red:`valid-server-code-received`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

import os
import time
import base64

try:
    import thread
except ImportError:
    import _thread as thread

try:
    from queue import Queue, Empty
except:
    from Queue import Queue, Empty  # @UnresolvedImport

#------------------------------------------------------------------------------

from twisted.internet import reactor
from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

from bitdust_forks import websocket

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.lib import jsn
from bitdust.lib import strng
from bitdust.lib import serialization

from bitdust.crypt import rsa_key
from bitdust.crypt import cipher
from bitdust.crypt import hashes

from bitdust.dht import dht_records

from bitdust.main import events
from bitdust.main import config

from bitdust.p2p import lookup

from bitdust.services import driver

#------------------------------------------------------------------------------

_IncomingAPIMessageCallback = None
_IncomingRoutedMessageCallback = None

_WebSocketApp = {}
_WebSocketQueue = {}
_WebSocketReady = {}
_WebSocketClosed = {}
_WebSocketStarted = {}
_WebSocketConnecting = {}

_LastCallID = {}
_PendingCalls = {}
_CallbacksQueue = {}
_RegisteredCallbacks = {}

#------------------------------------------------------------------------------


def SetIncomingAPIMessageCallback(cb):
    global _IncomingAPIMessageCallback
    _IncomingAPIMessageCallback = cb


def ExecuteIncomingAPIMessageCallback(instance, json_message):
    global _IncomingAPIMessageCallback
    return _IncomingAPIMessageCallback(instance, json_message)


#------------------------------------------------------------------------------


def start_client(url, callbacks={}):
    global _WebSocketStarted
    global _WebSocketConnecting
    global _WebSocketQueue
    global _RegisteredCallbacks
    global _PendingCalls
    if is_started(url):
        raise Exception('already started')
    if _Debug:
        lg.args(_DebugLevel + 4, url=url)
    _RegisteredCallbacks[url] = callbacks or {}
    _WebSocketConnecting[url] = True
    _WebSocketStarted[url] = True
    _PendingCalls[url] = []
    _WebSocketQueue[url] = Queue(maxsize=1000)
    websocket_thread_id = thread.start_new_thread(websocket_thread, (url, ))
    requests_thread_id = thread.start_new_thread(sending_thread, (url, _WebSocketQueue[url]))
    if _Debug:
        lg.args(_DebugLevel + 4, websocket_thread_id=websocket_thread_id, requests_thread_id=requests_thread_id)


def stop_client(url):
    global _WebSocketStarted
    global _WebSocketQueue
    global _WebSocketConnecting
    global _RegisteredCallbacks
    if not is_started(url):
        raise Exception('has not been started')
    if _Debug:
        lg.args(_DebugLevel + 4, url=url)
    _RegisteredCallbacks.pop(url, None)
    _WebSocketStarted[url] = False
    _WebSocketConnecting[url] = False
    while True:
        try:
            raw_data, _ = ws_queue(url).get_nowait()
            if _Debug:
                lg.dbg(_DebugLevel + 4, 'in %s cleaned unfinished call: %r' % (url, raw_data))
        except Empty:
            break
    _WebSocketQueue[url].put_nowait((None, None))
    _ws = ws(url)
    if _ws:
        _ws.close()
    else:
        if _Debug:
            lg.dbg(_DebugLevel + 4, 'websocket %s already closed' % url)


def shutdown_clients():
    global _WebSocketQueue
    for url in list(_WebSocketQueue.keys()):
        if is_started(url):
            stop_client(url)


#------------------------------------------------------------------------------


def ws(url):
    global _WebSocketApp
    return _WebSocketApp.get(url)


def ws_queue(url):
    global _WebSocketQueue
    return _WebSocketQueue.get(url)


def is_ready(url):
    global _WebSocketReady
    return _WebSocketReady.get(url)


def is_closed(url):
    global _WebSocketClosed
    return _WebSocketClosed.get(url, True)


def is_started(url):
    global _WebSocketStarted
    return _WebSocketStarted.get(url)


def is_connecting(url):
    global _WebSocketConnecting
    return _WebSocketConnecting.get(url)


def registered_callbacks(url):
    global _RegisteredCallbacks
    return _RegisteredCallbacks.get(url) or {}


def count_running_threads():
    global _WebSocketApp
    return len(_WebSocketApp)


#------------------------------------------------------------------------------


def on_open(ws_inst):
    global _WebSocketReady
    global _WebSocketClosed
    global _WebSocketConnecting
    global _PendingCalls
    url = ws_inst.url
    _WebSocketReady[url] = True
    _WebSocketClosed[url] = False
    _WebSocketConnecting[url] = False
    if _Debug:
        lg.args(_DebugLevel + 4, url=url, ws_inst=ws_inst, pending_calls=len(_PendingCalls))
    cb = registered_callbacks(url).get('on_open')
    if cb:
        reactor.callFromThread(cb, ws_inst)  # @UndefinedVariable
    for raw_data, tm in (_PendingCalls.get(url, []) or []):
        ws_queue(url).put_nowait((raw_data, tm))
    _PendingCalls[url].clear()


def on_close(ws_inst):
    global _WebSocketReady
    global _WebSocketClosed
    global _WebSocketConnecting
    url = ws_inst.url
    _WebSocketReady[url] = False
    _WebSocketClosed[url] = True
    _WebSocketConnecting[url] = False
    if _Debug:
        lg.dbg(_DebugLevel + 4, 'websocket %s closed %s' % (url, time.time()))
    cb = registered_callbacks(url).get('on_close')
    if cb:
        reactor.callFromThread(cb, ws_inst)  # @UndefinedVariable


def on_ping(ws_inst, data):
    url = ws_inst.url
    if _Debug:
        lg.dbg(_DebugLevel + 4, 'websocket PING %s: %r' % (url, data))


def on_pong(ws_inst, data):
    url = ws_inst.url
    # if _Debug:
    #     lg.dbg(_DebugLevel, 'websocket PONG %s: %r' % (url, data))


def on_incoming_message(ws_inst, message):
    global _IncomingRoutedMessageCallback
    url = ws_inst.url
    try:
        json_data = serialization.BytesToDict(message, keys_to_text=True, values_to_text=True, encoding='utf-8')
    except:
        lg.exc()
        return False
    if _Debug:
        lg.args(_DebugLevel + 4, url=url, json_data=json_data)
    if not _IncomingRoutedMessageCallback:
        lg.warn('incoming web socket message was ignored, callback was already released')
        return False
    reactor.callFromThread(_IncomingRoutedMessageCallback, url, json_data)  # @UndefinedVariable
    return True


def on_error(ws_inst, err):
    url = ws_inst.url
    if _Debug:
        lg.args(_DebugLevel + 4, ws_inst=ws_inst, url=url, err=err)
    cb = registered_callbacks(url).get('on_error')
    if cb:
        reactor.callFromThread(cb, ws_inst, err)  # @UndefinedVariable


def on_fail(err, result_callback=None):
    if _Debug:
        lg.args(_DebugLevel + 4, err=err)
    if result_callback:
        reactor.callFromThread(result_callback, err)  # @UndefinedVariable


#------------------------------------------------------------------------------


def sending_thread(router_host, active_queue):
    if _Debug:
        lg.args(_DebugLevel + 4, router_host=router_host)
    while True:
        if not is_started(router_host):
            if _Debug:
                lg.dbg(_DebugLevel + 4, '\nrequests thread %s is finishing because websocket is not started' % router_host)
            break
        raw_data, tm = active_queue.get()
        if raw_data is None:
            if _Debug:
                lg.dbg(_DebugLevel + 4, '\nrequests thread %s received empty request, about to stop the thread now' % router_host)
            break
        if not ws(router_host):
            on_fail(Exception('websocket is closed'))
            continue
        if _Debug:
            lg.args(_DebugLevel + 4, router_host=router_host, size=len(raw_data), raw_data=raw_data)
        ws(router_host).send(raw_data)
    if _Debug:
        lg.dbg(_DebugLevel + 4, '\nrequests thread %s finished' % router_host)


def websocket_thread(url):
    global _WebSocketApp
    global _WebSocketClosed
    websocket.enableTrace(_Debug)
    while is_started(url):
        _WebSocketClosed[url] = False
        if _Debug:
            lg.dbg(_DebugLevel + 4, 'websocket thread url=%r' % url)
        _WebSocketApp[url] = websocket.WebSocketApp(
            url=url,
            on_message=on_incoming_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open,
            on_ping=on_ping,
            on_pong=on_pong,
        )
        try:
            ws(url).run_forever(ping_interval=5*60, ping_timeout=15)
        except Exception as exc:
            _WebSocketApp[url] = None
            if _Debug:
                lg.dbg(_DebugLevel + 4, '\n    WS Thread ERROR: %r' % exc)
            time.sleep(5)
        if _WebSocketApp.get(url):
            _WebSocketApp.pop(url, None)
        if not is_started(url):
            break
        time.sleep(5)
    _WebSocketApp.pop(url, None)


#------------------------------------------------------------------------------


def verify_state(router_host):
    global _WebSocketReady
    if is_closed(router_host):
        _WebSocketReady[router_host] = False
        if _Debug:
            lg.dbg(_DebugLevel, 'WS CALL REFUSED, websocket %s already closed' % router_host)
        if is_connecting(router_host):
            if _Debug:
                lg.dbg(_DebugLevel, 'websocket %s closed but still connecting' % router_host)
            return 'closed'
        return 'closed'
    if is_ready(router_host):
        return 'ready'
    if is_connecting(router_host):
        return 'connecting'
    if is_started(router_host):
        return 'connecting'
    return 'not-started'


#------------------------------------------------------------------------------


def router_send(router_host, raw_data):
    global _PendingCalls
    st = verify_state(router_host)
    if _Debug:
        lg.args(_DebugLevel, router_host=router_host, st=st, sz=len(raw_data))
    if st == 'ready':
        ws_queue(router_host).put_nowait((raw_data, time.time()))
        return True
    if st == 'closed':
        lg.warn('websocket is already closed')
        return False
    if st == 'connecting':
        if _Debug:
            lg.dbg(_DebugLevel, 'websocket %s still connecting, remember pending request' % router_host)
        _PendingCalls[router_host].append((raw_data, time.time()))
        return True
    if st == 'not-started':
        if _Debug:
            lg.dbg(_DebugLevel, 'websocket %s was not started' % router_host)
        return False
    raise Exception('unexpected state %r' % st)


#------------------------------------------------------------------------------


class RoutedWebSocket(automat.Automat):

    """
    This class implements all the functionality of ``routed_web_socket()`` state machine.
    """

    timers = {
        'timer-1min': (60, ['READY']),
        'timer-5min': (300, ['CLIENT_PUB?']),
    }

    def __init__(self, debug_level=_DebugLevel, log_events=_Debug, log_transitions=_Debug, publish_events=False, **kwargs):
        """
        Builds `routed_web_socket()` state machine.
        """
        self.device_key_object = kwargs.pop('device_object')
        self.device_name = self.device_key_object.label
        self.encrypt_auth_info_callback = kwargs.pop('encrypt_auth_info_callback')
        self.authorized_routers = {}
        self.selected_routers = []
        self.routers_first_connect_results = {}
        self.active_router_url = None
        self.handshaked_routers = []
        self.server_code = None
        self.client_connected = False
        self.max_router_connections = config.conf().getInt('services/web-socket-communicator/max-connections', default=5)
        self.min_router_connections = config.conf().getInt('services/web-socket-communicator/min-connections', default=3)
        super(RoutedWebSocket, self).__init__(
            name='routed_web_socket',
            state='AT_STARTUP',
            debug_level=debug_level,
            log_events=log_events,
            log_transitions=log_transitions,
            publish_events=publish_events,
            **kwargs,
        )

    def __repr__(self):
        """
        Will return something like: "network_connector(CONNECTED)".
        """
        return '%s[%s%s|%s|%d|%s](%s)' % (
            self.id,
            '*' if self.client_connected else '',
            len(self.handshaked_routers),
            len(self.authorized_routers),
            count_running_threads(),
            self.active_router_url or '?',
            self.state,
        )

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `routed_web_socket()` state were changed.
        """
        if event == 'auth-error':
            if oldstate in ('CLIENT_PUB?', 'SERVER_CODE?', 'CLIENT_CODE?'):
                events.send('web-socket-handshake-failed', data=self.to_json())

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in the `routed_web_socket()`
        but automat state was not changed.
        """

    def to_json(self, short=True):
        active_routers = dict()
        for router_host, router_id in self.authorized_routers.items():
            internal_route_url = '{}/?i={}'.format(router_host, router_id)
            active_routers[router_host] = ws(internal_route_url)
        ret = super().to_json(short=short)
        ret.update(
            {
                'url': self.active_router_url,
                'connected_routers': self.handshaked_routers,
                'active_routers': active_routers,
                'server_code': self.server_code,
                'device_name': self.device_name,
                'client_connected': self.client_connected,
            }
        )
        return ret

    #------------------------------------------------------------------------------

    def on_incoming_message_callback(self, url, json_data):
        if _Debug:
            lg.args(_DebugLevel, url=url, json_data=json_data)
        if json_data.get('route_id') and json_data.get('result'):
            self._on_web_socket_router_first_response(url, json_data)
            return True
        cmd = json_data.get('cmd')
        if cmd == 'api':
            if self.state != 'READY':
                lg.warn('received api request, but web socket is not ready yet')
                self.automat('auth-error')
                return False
            if self.active_router_url and self.active_router_url != url:
                lg.warn('active web socket router %r switched to %r' % (self.active_router_url, url))
            self.active_router_url = url
            if not self.client_connected:
                reactor.callLater(0, self._do_publish_routers)  # @UndefinedVariable
            self.client_connected = True
            self.event('api-message', url=url, json_data=json_data)
            return True
        if cmd == 'handshake-accepted' or cmd == 'router-handshake-accepted':
            if self.state not in ['WEB_SOCKET?', 'CLIENT_PUB?', 'READY']:
                lg.warn('received handshake-accepted signal from %r, but web socket is currently in state: %s' % (url, self.state))
                return False
            route_url = json_data.get('route_url')
            if not route_url:
                return False
            self._on_web_socket_router_handshake_accepted(
                internal_route_url=url,
                external_route_url=route_url,
            )
            return True
        if cmd == 'client-public-key':
            try:
                client_key_object = rsa_key.RSAKey()
                client_key_object.fromString(json_data.get('client_public_key'))
            except:
                lg.exc()
                self.automat('auth-error')
                return False
            if self.active_router_url and self.active_router_url != url:
                lg.warn('active web socket router %r switched to %r' % (self.active_router_url, url))
            self.active_router_url = url
            self.automat('client-pub-key-received', client_key_object=client_key_object)
            return True
        if cmd == 'server-code':
            if self.state != 'SERVER_CODE?':
                lg.warn('received server code, but web socket is currently in state: %s' % self.state)
                return False
            try:
                signature = json_data['signature']
                encrypted_server_code = json_data['server_code']
            except:
                lg.exc()
                self.automat('server-code-failed')
                return False
            return self.on_server_code_received(signature=signature, encrypted_server_code=encrypted_server_code)
        if cmd == 'client-disconnected':
            self.client_connected = False
            return True
        return False

    def on_outgoing_message(self, json_data):
        # if _Debug:
        #     lg.args(_DebugLevel, client_connected=self.client_connected, d=json_data)
        if json_data.get('cmd') == 'push':
            if not self.client_connected:
                return False
        if self.state != 'READY':
            if _Debug:
                lg.dbg(_DebugLevel, 'skip sending api message to the client, %r state is %r' % (self, self.state))
            return False
        return self._do_push_encrypted(json_data)

    def on_server_code_received(self, signature, encrypted_server_code):
        try:
            orig_encrypted_server_code = base64.b64decode(strng.to_bin(encrypted_server_code))
            received_server_code_salted = strng.to_text(self.device_key_object.decrypt(orig_encrypted_server_code))
            received_server_code = received_server_code_salted.split('-')[0]
        except:
            lg.exc()
            self.automat('server-code-failed')
            return False
        if _Debug:
            lg.args(_DebugLevel, received_server_code_salted=received_server_code_salted)
        hashed_server_code = hashes.sha1(strng.to_bin(received_server_code_salted))
        if not self.client_key_object.verify(signature, hashed_server_code):
            lg.err('signature verification error, received server code is not valid')
            self.automat('server-code-failed')
            return False
        if received_server_code != self.server_code:
            lg.warn('received server code %r is not matching with generated code %r' % (received_server_code, self.server_code))
            self.automat('server-code-failed')
            return False
        if _Debug:
            lg.args(_DebugLevel, received_server_code=received_server_code)
        self.automat('valid-server-code-received')
        return True

    def on_client_code_input_received(self, client_code):
        if _Debug:
            lg.args(_DebugLevel, client_code=client_code)
        self.automat('client-code-input-received', client_code=client_code)

    #------------------------------------------------------------------------------

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <https://github.com/vesellov/visio2python>`_ tool.
        """
        #---READY---
        if self.state == 'READY':
            if event == 'api-message':
                self.doProcess(*args, **kwargs)
            elif event == 'client-pub-key-received':
                self.state = 'SERVER_CODE?'
                self.doSaveClientPublicKey(*args, **kwargs)
                self.doGenerateAuthToken(*args, **kwargs)
                self.doGenerateServerCode(*args, **kwargs)
                self.doSendServerPubKey(*args, **kwargs)
            elif event == 'auth-error' or event == 'stop':
                self.state = 'CLOSED'
                self.doRemoveAuthToken(event, *args, **kwargs)
                self.doDisconnectRouters(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'router-disconnected':
                self.state = 'ROUTERS?'
                self.doLookupRequestRouters(*args, **kwargs)
            elif event == 'timer-1min':
                self.doVerifyRouters(*args, **kwargs)
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'start' and not self.isKnownRouters(*args, **kwargs):
                self.state = 'ROUTERS?'
                self.doInit(*args, **kwargs)
                self.doLookupRequestRouters(*args, **kwargs)
            elif event == 'start' and self.isKnownRouters(*args, **kwargs):
                self.state = 'WEB_SOCKET?'
                self.doInit(*args, **kwargs)
                self.doConnectRouters(*args, **kwargs)
        #---ROUTERS?---
        elif self.state == 'ROUTERS?':
            if event == 'routers-selected':
                self.state = 'WEB_SOCKET?'
                self.doConnectRouters(*args, **kwargs)
            elif event == 'stop' or event == 'lookup-failed':
                self.state = 'CLOSED'
                self.doDisconnectRouters(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---WEB_SOCKET?---
        elif self.state == 'WEB_SOCKET?':
            if event == 'routers-connected' and not self.isAuthenticated(*args, **kwargs):
                self.state = 'CLIENT_PUB?'
                self.doSaveRouters(*args, **kwargs)
                self.doNotifyListening(*args, **kwargs)
            elif event == 'routers-connected' and self.isAuthenticated(*args, **kwargs):
                self.state = 'READY'
                self.doSaveRouters(*args, **kwargs)
                self.doLoadAuthInfo(*args, **kwargs)
                self.doNotifyListening(*args, **kwargs)
            elif event == 'routers-failed':
                self.state = 'ROUTERS?'
                self.doLookupRequestRouters(*args, **kwargs)
            elif event == 'stop':
                self.state = 'CLOSED'
                self.doDisconnectRouters(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---CLIENT_PUB?---
        elif self.state == 'CLIENT_PUB?':
            if event == 'client-pub-key-received':
                self.state = 'SERVER_CODE?'
                self.doSaveClientPublicKey(*args, **kwargs)
                self.doGenerateAuthToken(*args, **kwargs)
                self.doGenerateServerCode(*args, **kwargs)
                self.doSendServerPubKey(*args, **kwargs)
            elif event == 'auth-error' or event == 'stop':
                self.state = 'CLOSED'
                self.doRemoveAuthToken(event, *args, **kwargs)
                self.doDisconnectRouters(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'router-disconnected':
                self.state = 'ROUTERS?'
                self.doLookupRequestRouters(*args, **kwargs)
            elif event == 'timer-5min':
                self.doVerifyRouters(*args, **kwargs)
        #---SERVER_CODE?---
        elif self.state == 'SERVER_CODE?':
            if event == 'auth-error' or event == 'stop':
                self.state = 'CLOSED'
                self.doRemoveAuthToken(event, *args, **kwargs)
                self.doDisconnectRouters(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'valid-server-code-received':
                self.state = 'CLIENT_CODE?'
                self.doWaitClientCodeInput(*args, **kwargs)
            elif event == 'client-pub-key-received':
                self.doSaveClientPublicKey(*args, **kwargs)
                self.doGenerateAuthToken(*args, **kwargs)
                self.doGenerateServerCode(*args, **kwargs)
                self.doSendServerPubKey(*args, **kwargs)
            elif event == 'router-disconnected':
                self.state = 'ROUTERS?'
                self.doLookupRequestRouters(*args, **kwargs)
            elif event == 'server-code-failed':
                self.state = 'CLIENT_PUB?'
                self.doEraseServerCode(*args, **kwargs)
        #---CLIENT_CODE?---
        elif self.state == 'CLIENT_CODE?':
            if event == 'client-code-input-received':
                self.state = 'READY'
                self.doSaveAuthInfo(*args, **kwargs)
                self.doSendClientCode(*args, **kwargs)
            elif event == 'client-pub-key-received':
                self.state = 'SERVER_CODE?'
                self.doSaveClientPublicKey(*args, **kwargs)
                self.doGenerateAuthToken(*args, **kwargs)
                self.doGenerateServerCode(*args, **kwargs)
                self.doSendServerPubKey(*args, **kwargs)
            elif event == 'auth-error' or event == 'stop':
                self.state = 'CLOSED'
                self.doRemoveAuthToken(event, *args, **kwargs)
                self.doDisconnectRouters(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'router-disconnected':
                self.state = 'ROUTERS?'
                self.doLookupRequestRouters(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def isAuthenticated(self, *args, **kwargs):
        """
        Condition method.
        """
        if not self.device_key_object:
            return False
        if not self.device_key_object.meta.get('auth_token'):
            return False
        return True

    def isKnownRouters(self, *args, **kwargs):
        """
        Condition method.
        """
        authorized_routers = self.device_key_object.meta.get('authorized_routers', {}) or {}
        if not authorized_routers:
            for router_host, route_id in self.device_key_object.meta.get('connected_routers', {}) or {}:
                if route_id:
                    authorized_routers[router_host] = route_id
        if _Debug:
            lg.args(_DebugLevel, authorized_routers=authorized_routers)
        return len(authorized_routers) >= self.min_router_connections

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        global _IncomingRoutedMessageCallback
        _IncomingRoutedMessageCallback = self.on_incoming_message_callback
        _authorized_routers = self.device_key_object.meta.get('authorized_routers', {}) or {}
        if not _authorized_routers:
            for router_host, route_id in self.device_key_object.meta.get('connected_routers', {}).items():
                if route_id:
                    _authorized_routers[router_host] = route_id
        self.authorized_routers = {}
        for router_host, route_id in _authorized_routers.items():
            if route_id:
                self.authorized_routers[router_host] = route_id
        self.routers_first_connect_results = {}
        self.active_router_url = None
        self.auth_token = None
        self.session_key = None
        self.client_key_object = None
        self.listening_callback = kwargs.get('listening_callback')
        self.client_code_input_callback = kwargs.get('client_code_input_callback')

    def doLookupRequestRouters(self, *args, **kwargs):
        """
        Action method.
        """
        # TODO: introduce a delay to slow down reconnections
        force_dht_lookup = kwargs.get('force_dht_lookup')
        known_routers = kwargs.get('known_routers')
        alive_routers = kwargs.get('alive_routers') or []
        if _Debug:
            lg.args(_DebugLevel, force_dht_lookup=force_dht_lookup, known=known_routers, alive=alive_routers, authorized=self.authorized_routers)
        if force_dht_lookup:
            self.router_lookups = 0
            self.selected_routers = list(alive_routers)
            self._do_lookup_next_router()
            return
        if not known_routers:
            known_routers = self.authorized_routers.copy()
        self.router_lookups = 0
        self.selected_routers = list(alive_routers)
        for router_host, route_id in known_routers.items():
            if len(self.selected_routers) >= self.min_router_connections:
                break
            if route_id:
                if router_host not in self.selected_routers:
                    self.selected_routers.append(router_host)
        self._do_lookup_next_router()

    def doConnectRouters(self, *args, **kwargs):
        """
        Action method.
        """
        target_routers = kwargs.get('target_routers') or {}
        if not target_routers or len(target_routers) < self.min_router_connections:
            for router_host, router_id in self.authorized_routers.items():
                if len(target_routers) >= self.min_router_connections:
                    break
                if router_id:
                    target_routers[router_host] = router_id
        self.connecting_routers = []
        self.handshaked_routers = []
        previous_active_router_url = self.active_router_url
        self.active_router_url = None
        if _Debug:
            lg.args(_DebugLevel, target_routers=target_routers)
        anything_connecting = False
        something_already_connected = []
        for router_host, route_id in target_routers.items():
            if not route_id:
                continue
            internal_route_url = '{}/?i={}'.format(router_host, route_id)
            external_route_url = '{}/?r={}'.format(router_host, route_id)
            if is_started(internal_route_url):
                something_already_connected.append(internal_route_url)
                if external_route_url not in self.handshaked_routers:
                    self.handshaked_routers.append(external_route_url)
                else:
                    lg.warn('router %r was already handshaked' % router_host)
            else:
                self.connecting_routers.append(internal_route_url)
                start_client(url=internal_route_url, callbacks={
                    'on_open': self._on_web_socket_router_connection_opened,
                    'on_error': self._on_web_socket_router_connection_error,
                })
                anything_connecting = True
        if _Debug:
            lg.args(_DebugLevel, connecting=self.connecting_routers, already_connected=something_already_connected, handshaked=len(self.handshaked_routers))
        if not anything_connecting:
            if not something_already_connected:
                self.automat('routers-failed', force_dht_lookup=True)
            else:
                for internal_route_url in something_already_connected:
                    router_host, _, route_id = internal_route_url.rpartition('/?i=')
                    if self.authorized_routers.get(router_host):
                        external_route_url = '{}/?r={}'.format(router_host, route_id)
                        if external_route_url not in self.handshaked_routers:
                            self.handshaked_routers.append(external_route_url)
                        if previous_active_router_url == internal_route_url:
                            self.active_router_url = internal_route_url
                if not self.active_router_url:
                    self.active_router_url = something_already_connected[0]
                self.automat('routers-connected')

    def doDisconnectRouters(self, event, *args, **kwargs):
        """
        Action method.
        """
        # TODO: notify about failed result
        if _Debug:
            lg.args(_DebugLevel, event=event, authorized_routers=self.authorized_routers)
        if event == 'auth-error':
            return
        for router_host, route_id in self.authorized_routers.items():
            if not route_id:
                continue
            route_url = '{}/?i={}'.format(router_host, route_id)
            if is_started(route_url):
                stop_client(route_url)
        self.handshaked_routers = []
        self.routers_first_connect_results = {}
        self.active_router_url = None
        if event == 'lookup-failed':
            if self.listening_callback:
                reactor.callLater(0, self.listening_callback, False)  # @UndefinedVariable

    def doSaveRouters(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_save_routers()

    def doVerifyRouters(self, *args, **kwargs):
        """
        Action method.
        """
        alive_routers = []
        dead_routers = []
        active_router_is_alive = False
        for external_route_url in self.handshaked_routers:
            router_host, _, route_id = external_route_url.rpartition('/?r=')
            internal_route_url = '{}/?i={}'.format(router_host, route_id)
            if ws(internal_route_url):
                alive_routers.append(router_host)
                if internal_route_url == self.active_router_url:
                    active_router_is_alive = True
            else:
                dead_routers.append(router_host)
        if not active_router_is_alive:
            self.automat('router-disconnected', alive_routers=alive_routers, dead_routers=dead_routers, force_dht_lookup=True)
            return
        if len(alive_routers) < self.max_router_connections:
            if len(alive_routers) < self.min_router_connections:
                self.automat('router-disconnected', alive_routers=alive_routers, dead_routers=dead_routers, force_dht_lookup=True)

    def doLoadAuthInfo(self, *args, **kwargs):
        """
        Action method.
        """
        self.auth_token = self.device_key_object.meta['auth_token']
        self.session_key = base64.b64decode(strng.to_bin(self.device_key_object.meta['session_key']))
        self.client_key_object = rsa_key.RSAKey()
        self.client_key_object.fromString(self.device_key_object.meta['client_public_key'])

    def doSaveAuthInfo(self, *args, **kwargs):
        """
        Action method.
        """
        self.server_code = None
        self.device_key_object.meta['auth_token'] = self.auth_token
        self.device_key_object.meta['session_key'] = strng.to_text(base64.b64encode(self.session_key))
        self.device_key_object.meta['client_public_key'] = self.client_key_object.toPublicString()
        self.device_key_object.save()
        lg.info('device %s is now authenticated' % self.device_name)

    def doSaveClientPublicKey(self, *args, **kwargs):
        """
        Action method.
        """
        self.client_key_object = kwargs.get('client_key_object')

    def doGenerateServerCode(self, *args, **kwargs):
        """
        Action method.
        """
        BITDUST_WEB_SOCKET_SERVER_CODE_GENERATED = os.environ.get('BITDUST_WEB_SOCKET_SERVER_CODE_GENERATED', None)
        if BITDUST_WEB_SOCKET_SERVER_CODE_GENERATED:
            self.server_code = BITDUST_WEB_SOCKET_SERVER_CODE_GENERATED.strip()
        else:
            self.server_code = cipher.generate_digits(4, as_text=True)
        events.send('web-socket-handshake-started', data=self.to_json())
        if _Debug:
            lg.args(_DebugLevel, server_code=self.server_code)

    def doEraseServerCode(self, *args, **kwargs):
        """
        Action method.
        """
        self.server_code = None

    def doSendServerPubKey(self, *args, **kwargs):
        """
        Action method.
        """
        confirmation_code = cipher.generate_secret_text(32)
        server_public_key = self.device_key_object.toPublicString()
        server_public_key_base = strng.to_bin(server_public_key + '-' + confirmation_code)
        hashed_server_public_key_base = hashes.sha1(server_public_key_base)
        if _Debug:
            lg.args(_DebugLevel, confirmation_code=confirmation_code)
        # TODO: consider encrypting server public key and confirmation code with client public key
        self._do_push({
            'cmd': 'server-public-key',
            'server_public_key': server_public_key,
            'confirm': confirmation_code,
            'signature': strng.to_text(self.device_key_object.sign(hashed_server_public_key_base)),
        })

    def doSendClientCode(self, *args, **kwargs):
        """
        Action method.
        """
        auth_info, signature = self.encrypt_auth_info_callback(
            client_code=kwargs['client_code'],
            auth_token=self.auth_token,
            session_key=self.session_key,
            client_public_key_object=self.client_key_object,
            device_key_object=self.device_key_object,
        )
        self._do_push({
            'cmd': 'client-code',
            'auth': auth_info,
            'signature': signature,
            'listeners': self.handshaked_routers,
        })

    def doWaitClientCodeInput(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.args(_DebugLevel, args=args, kwargs=kwargs)
        self.server_code = None
        events.send('web-socket-handshake-proceeding', data=self.to_json())
        BITDUST_WEB_SOCKET_CLIENT_CODE_INPUT = os.environ.get('BITDUST_WEB_SOCKET_CLIENT_CODE_INPUT', None)
        if BITDUST_WEB_SOCKET_CLIENT_CODE_INPUT:
            self.on_client_code_input_received(BITDUST_WEB_SOCKET_CLIENT_CODE_INPUT.strip())
            return
        if self.client_code_input_callback:
            self.client_code_input_callback(self.on_client_code_input_received, self.device_name)
            return
        lg.warn('client code input callback was not defined')

    def doGenerateAuthToken(self, *args, **kwargs):
        """
        Action method.
        """
        self.auth_token = cipher.generate_secret_text(10)
        self.session_key = cipher.make_key()

    def doRemoveAuthToken(self, event, *args, **kwargs):
        """
        Action method.
        """
        self.device_key_object.save()
        if _Debug:
            lg.args(_DebugLevel, event=event)
        if event == 'auth-error':
            self.server_code = None
            self.device_key_object.meta['auth_token'] = None
            self.device_key_object.meta['session_key'] = None
            self.device_key_object.meta['client_public_key'] = None
            self.device_key_object.save()

    def doProcess(self, *args, **kwargs):
        """
        Action method.
        """
        json_data = kwargs['json_data']
        if self.auth_token != json_data.get('auth'):
            lg.err('received unauthorized API message for device %r' % self.device_name)
            self.automat('auth-error')
            return
        try:
            raw_data = cipher.decrypt_json(json_data['payload'], self.session_key, from_dict=True)
        except:
            lg.exc()
            self.automat('auth-error')
            return
        try:
            api_message_payload = serialization.BytesToDict(raw_data, keys_to_text=True, values_to_text=True, encoding='utf-8')
        except:
            lg.exc()
            self.automat('auth-error')
            return
        api_message_payload['call_id'] = json_data.get('call_id')
        if _Debug:
            lg.args(_DebugLevel, payload=api_message_payload)
        if not ExecuteIncomingAPIMessageCallback(self, api_message_payload):
            lg.warn('incoming api message was not processed')

    def doNotifyListening(self, *args, **kwargs):
        """
        Action method.
        """
        if self.listening_callback:
            reactor.callLater(0, self.listening_callback, True)  # @UndefinedVariable
        if self.client_connected:
            reactor.callLater(0, self._do_publish_routers)  # @UndefinedVariable

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        global _IncomingRoutedMessageCallback
        _IncomingRoutedMessageCallback = None
        self.destroy()

    #------------------------------------------------------------------------------

    def _on_web_socket_router_connection_opened(self, ws_inst):
        if _Debug:
            lg.args(_DebugLevel, ws_inst=ws_inst)
        url = ws_inst.url
        if not url:
            lg.warn('missed connecting web router: %r' % url)
            return
        if url in self.connecting_routers:
            self.connecting_routers.remove(url)
        router_send(
            router_host=ws_inst.url,
            raw_data=jsn.dumps({
                'cmd': 'handshake',
                'internal': True,
            }),
        )

    def _on_web_socket_router_connection_error(self, ws_inst, err):
        url = ws_inst.url
        if not url:
            lg.warn('missed connecting web router: %r' % url)
            return
        if is_started(url):
            try:
                stop_client(url)
            except:
                lg.exc()
        internal_route_url = url
        if internal_route_url in self.connecting_routers:
            self.connecting_routers.remove(internal_route_url)
        router_host, _, route_id = internal_route_url.rpartition('/?i=')
        external_route_url = '{}/?r={}'.format(router_host, route_id)
        if external_route_url in self.handshaked_routers:
            self.handshaked_routers.remove(external_route_url)
        if self.active_router_url == internal_route_url:
            lg.err('active web socket router %s was disconnected' % self.active_router_url)
            self.active_router_url = None
        if router_host in self.selected_routers:
            self.selected_routers.remove(router_host)
        handshaked_count = len(self.handshaked_routers)
        if _Debug:
            lg.args(_DebugLevel, ws_inst=ws_inst, err=err, connecting=len(self.connecting_routers), handshaked=handshaked_count)
        if not self.connecting_routers:
            if handshaked_count > 0 and self.active_router_url:
                self.automat('routers-connected')
            else:
                if self.state == 'WEB_SOCKET?':
                    self.automat('routers-failed')
                else:
                    alive_routers = []
                    dead_routers = []
                    for external_route_url in self.handshaked_routers:
                        router_host, _, route_id = external_route_url.rpartition('/?r=')
                        internal_route_url = '{}/?i={}'.format(router_host, route_id)
                        if ws(internal_route_url):
                            alive_routers.append(router_host)
                        else:
                            dead_routers.append(router_host)
                    self.automat('router-disconnected', alive_routers=alive_routers, dead_routers=dead_routers, force_dht_lookup=True)

    def _on_web_socket_router_handshake_accepted(self, internal_route_url, external_route_url):
        if _Debug:
            lg.args(_DebugLevel, internal_route_url=internal_route_url, external_route_url=external_route_url)
        if not self.active_router_url and internal_route_url:
            self.active_router_url = internal_route_url
            lg.info('connected active web socket router %r' % self.active_router_url)
        router_host, _, route_id = external_route_url.rpartition('/?r=')
        route_already_handshaked = False
        for known_route in self.handshaked_routers:
            if known_route.startswith(router_host):
                route_already_handshaked = True
        if not route_already_handshaked:
            self.handshaked_routers.append(external_route_url)
        else:
            lg.warn('router %s was already handshaked' % router_host)
        handshaked_count = len(self.handshaked_routers)
        if router_host in self.authorized_routers:
            if route_id == self.authorized_routers[router_host]:
                lg.info('web socket router %r handshake accepted' % router_host)
            else:
                lg.warn('web socket router %r previously known route ID is not matching' % router_host)
        else:
            lg.info('new web socket router %r handshake accepted' % router_host)
        self.authorized_routers[router_host] = route_id
        if _Debug:
            lg.args(_DebugLevel, connecting=len(self.connecting_routers), handshaked=handshaked_count, active=self.active_router_url, router_host=router_host)
        if not self.connecting_routers:
            if handshaked_count > 0:
                if self.state in ['CLIENT_PUB?', 'READY']:
                    self._do_save_routers()
                else:
                    self.automat('routers-connected')
            else:
                self.automat('routers-failed')

    def _on_router_lookup_failed(self, err):
        if _Debug:
            lg.args(_DebugLevel, err=err)
        reactor.callLater(0, self._lookup_next_router)  # @UndefinedVariable
        return None

    def _on_dht_nodes_lookup_finished(self, results):
        if _Debug:
            lg.args(_DebugLevel, results=results)
        if self.state != 'ROUTERS?':
            lg.warn('internal state was changed during router lookup, SKIP next lookup')
            return None
        for url in results:
            if len(self.selected_routers) >= self.max_router_connections:
                reactor.callLater(0, self._do_lookup_next_router)  # @UndefinedVariable
                return None
            if url not in self.selected_routers:
                self.selected_routers.append(url)
        reactor.callLater(0, self._do_lookup_next_router)  # @UndefinedVariable
        return None

    def _on_web_socket_location_dht_response(self, response, result):
        if _Debug:
            lg.out(_DebugLevel, 'RoutedWebSocket._on_web_socket_location_dht_response : %r' % response)
        responded_location = response.get('location')
        if not responded_location:
            result.errback(Exception('websocket location observe failed'))
            return response
        result.callback(responded_location)
        return response

    def _on_web_socket_router_first_response(self, url, resp):
        if is_started(url):
            try:
                stop_client(url)
            except:
                lg.exc()
        # if self.routers_first_connect_results.get(url):
        #     lg.warn('web socket router at %s was already connected' % url)
        #     if len(self.routers_first_connect_results) >= self.max_router_connections:
        #         self.automat('routers-selected', target_routers=self.routers_first_connect_results)
        #     return None
        route_id = None
        result = None
        try:
            route_id = resp['route_id']
            result = resp['result']
        except:
            lg.exc()
        router_host = url
        if result == 'accepted':
            self.routers_first_connect_results[router_host] = route_id
        else:
            self.routers_first_connect_results[router_host] = None
            if router_host in self.authorized_routers:
                self.authorized_routers.pop(router_host)
                lg.warn('router first connection was rejected, marked router %r as non-authorized' % router_host)
        if _Debug:
            lg.args(_DebugLevel, router_host=router_host, result=result, route_id=route_id, first_results=self.routers_first_connect_results)
        if len(self.routers_first_connect_results) >= self.min_router_connections:
            self.automat('routers-selected', target_routers=self.routers_first_connect_results)
        return None

    def _on_web_socket_router_first_connection_opened(self, ws_inst):
        authorized_route_id = self.authorized_routers.get(ws_inst.url) or None
        if _Debug:
            lg.args(_DebugLevel, ws_inst=ws_inst, authorized_route_id=authorized_route_id)
        router_send(
            router_host=ws_inst.url,
            raw_data=jsn.dumps({
                'cmd': 'connect-request',
                'route_id': authorized_route_id,
            }),
        )

    def _on_web_socket_router_first_connection_error(self, ws_inst, err):
        if _Debug:
            lg.args(_DebugLevel, ws_inst=ws_inst, err=err)
        url = ws_inst.url
        if is_started(url):
            try:
                stop_client(url)
            except:
                lg.exc()
        router_host = url
        if str(err).count('Connection is already closed') or isinstance(err, websocket.WebSocketConnectionClosedException):
            if router_host in self.authorized_routers:
                self.authorized_routers.pop(router_host)
                lg.warn('router first connection closed error, marked router %r as non-authorized' % router_host)
        self.routers_first_connect_results[router_host] = None
        if _Debug:
            lg.args(_DebugLevel, first_results=self.routers_first_connect_results)
        if len(self.routers_first_connect_results) >= self.min_router_connections:
            self.automat('routers-selected', target_routers=self.routers_first_connect_results)
        return None

    #------------------------------------------------------------------------------

    def _do_save_routers(self):
        _authorized_routers = {}
        for external_route_url in self.handshaked_routers:
            router_host, _, route_id = external_route_url.rpartition('/?r=')
            _authorized_routers[router_host] = route_id
        for router_host, route_id in self.authorized_routers.items():
            if len(_authorized_routers) >= self.max_router_connections:
                break
            if route_id and router_host not in _authorized_routers:
                _authorized_routers[router_host] = route_id
        if _Debug:
            lg.args(_DebugLevel, old=self.authorized_routers, new=_authorized_routers)
        self.authorized_routers = _authorized_routers
        self.device_key_object.meta['authorized_routers'] = self.authorized_routers
        self.device_key_object.meta['url'] = self.active_router_url
        self.device_key_object.save()

    def _do_publish_routers(self):
        if _Debug:
            lg.args(_DebugLevel, handshaked_routers=self.handshaked_routers)
        self._do_push_encrypted(json_data={
            'cmd': 'publish-routers',
            'listeners': self.handshaked_routers,
            # TODO: remove the following line later
            'routers': self.handshaked_routers,
            'authorized_routers': self.authorized_routers,
        })

    def _do_routers_send_first_connect_request(self):
        if _Debug:
            lg.args(_DebugLevel, selected_routers=self.selected_routers)
        something_sent = False
        self.routers_first_connect_results = {}
        counter = 0
        for router_host in self.selected_routers:
            if not is_started(router_host):
                start_client(url=router_host, callbacks={
                    'on_open': self._on_web_socket_router_first_connection_opened,
                    'on_error': self._on_web_socket_router_first_connection_error,
                })
                something_sent = True
            else:
                self.routers_first_connect_results[router_host] = self.authorized_routers.get(router_host)
            counter += 1
            if counter >= self.min_router_connections:
                break
        if not something_sent:
            if len(self.routers_first_connect_results) >= self.min_router_connections:
                self.automat('routers-selected', target_routers=self.routers_first_connect_results)
            else:
                self.automat('lookup-failed')

    def _do_lookup_next_router(self):
        if _Debug:
            lg.args(_DebugLevel, lookups=self.router_lookups, first_connected=len(self.routers_first_connect_results), selected=self.selected_routers)
        if len(self.selected_routers) >= self.min_router_connections:
            reactor.callLater(0, self._do_routers_send_first_connect_request)  # @UndefinedVariable
            return
        if self.router_lookups >= 10:  # TODO: read from settings
            if len(self.selected_routers) >= self.min_router_connections:
                reactor.callLater(0, self._do_routers_send_first_connect_request)  # @UndefinedVariable
                return
            self.automat('lookup-failed')
            return
        if not driver.is_on('service_nodes_lookup'):
            lg.err('service_nodes_lookup() is not started, not possible to lookup web socket routers')
            self.automat('lookup-failed')
            return
        self.router_lookups += 1
        lookup_task = lookup.start(
            is_idurl=False,
            layer_id=dht_records.LAYER_WEB_SOCKET_ROUTERS,
            observe_method=self._do_observe_dht_node,
        )
        if lookup_task.result_defer:
            lookup_task.result_defer.addCallback(self._on_dht_nodes_lookup_finished)
            lookup_task.result_defer.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='RoutedWebSocket._do_lookup_next_router')
            lookup_task.result_defer.addErrback(lambda err: self.automat('lookup-failed'))
        else:
            reactor.callLater(5, self._do_lookup_next_router)  # @UndefinedVariable

    def _do_observe_dht_node(self, node, layer_id):
        if _Debug:
            lg.out(_DebugLevel, 'RoutedWebSocket._do_observe_dht_node   %s  layer_id=%d' % (node, layer_id))
        result = Deferred()
        d = node.request('location', layerID=layer_id)
        d.addCallback(self._on_web_socket_location_dht_response, result)
        d.addErrback(result.errback)
        return result

    def _do_push(self, json_data):
        if not self.active_router_url:
            lg.warn('no active web socket router is currently connected')
            return False
        raw_data = jsn.dumps(json_data)
        router_send(router_host=self.active_router_url, raw_data=raw_data)
        if _Debug:
            lg.out(_DebugLevel, '***   API %s PUSH %d bytes: %r' % (self.device_name, len(raw_data), json_data))
        return True

    def _do_push_encrypted(self, json_data):
        if not self.active_router_url:
            lg.warn('no active web socket router is currently connected')
            return False
        json_data['salt'] = cipher.generate_secret_text(10)
        cmd = json_data.pop('cmd', None)
        call_id = None
        if 'payload' in json_data:
            call_id = json_data['payload'].pop('call_id', None)
        raw_bytes = serialization.DictToBytes(json_data, encoding='utf-8')
        encrypted_json_data = cipher.encrypt_json(raw_bytes, self.session_key, to_dict=True)
        if call_id:
            encrypted_json_data['call_id'] = call_id
        if cmd:
            encrypted_json_data['cmd'] = cmd
        encrypted_raw_data = serialization.DictToBytes(encrypted_json_data, encoding='utf-8', to_text=True)
        router_send(router_host=self.active_router_url, raw_data=encrypted_raw_data)
        if _Debug:
            lg.out(_DebugLevel, '***   API %s PUSH %d encrypted bytes: %r' % (self.device_name, len(encrypted_raw_data), encrypted_json_data))
        return True
