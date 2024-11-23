#!/usr/bin/env python
# api_routed_device.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (api_routed_device.py) is part of BitDust Software.
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
.. module:: api_routed_device
.. role:: red

BitDust api_routed_device() Automat

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
    * :red:`start`
    * :red:`stop`
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
        lg.args(_DebugLevel, url=url)
    _RegisteredCallbacks[url] = callbacks or {}
    _WebSocketConnecting[url] = True
    _WebSocketStarted[url] = True
    _PendingCalls[url] = {}
    _WebSocketQueue[url] = Queue(maxsize=100)
    reactor.callInThread(websocket_thread, url)  # @UndefinedVariable
    reactor.callInThread(sending_thread, url, _WebSocketQueue[url])  # @UndefinedVariable


def stop_client(url):
    global _WebSocketStarted
    global _WebSocketQueue
    global _WebSocketConnecting
    global _RegisteredCallbacks
    if not is_started(url):
        raise Exception('has not been started')
    if _Debug:
        lg.args(_DebugLevel, url=url)
    _RegisteredCallbacks.pop(url, None)
    _WebSocketStarted[url] = False
    _WebSocketConnecting[url] = False
    while True:
        try:
            raw_data, _, _, _ = ws_queue(url).get_nowait()
            if _Debug:
                lg.dbg(_DebugLevel, 'in %s cleaned unfinished call: %r' % (url, raw_data))
        except Empty:
            break
    _WebSocketQueue[url].put_nowait((None, None))
    if ws(url):
        if _Debug:
            lg.dbg(_DebugLevel, 'websocket %s already closed' % url)
        ws(url).close()


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
    return _RegisteredCallbacks.get(url)


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
        lg.args(_DebugLevel, url=url, ws_inst=ws_inst, pending_calls=len(_PendingCalls))
    cb = registered_callbacks(url).get('on_open')
    if cb:
        reactor.callFromThread(cb, ws_inst)  # @UndefinedVariable
    for raw_data, tm in _PendingCalls[url]:
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
        lg.dbg(_DebugLevel, 'websocket %s closed %s' % (url, time.time()))
    cb = registered_callbacks(url).get('on_close')
    if cb:
        reactor.callFromThread(cb, ws_inst)  # @UndefinedVariable


def on_incoming_message(ws_inst, message):
    global _IncomingRoutedMessageCallback
    url = ws_inst.url
    try:
        json_data = serialization.BytesToDict(message, keys_to_text=True, values_to_text=True, encoding='utf-8')
    except:
        lg.exc()
        return False
    if _Debug:
        lg.args(_DebugLevel, url=url, json_data=json_data)
    if not _IncomingRoutedMessageCallback:
        lg.warn('incoming web socket message was ignored, callback was already released')
        return False
    reactor.callFromThread(_IncomingRoutedMessageCallback, url, json_data)  # @UndefinedVariable
    return True


def on_error(ws_inst, err):
    if _Debug:
        lg.args(_DebugLevel, ws_inst=ws_inst, err=err)
    cb = registered_callbacks().get('on_error')
    if cb:
        reactor.callFromThread(cb, ws_inst, err)  # @UndefinedVariable


def on_fail(err, result_callback=None):
    if _Debug:
        lg.args(_DebugLevel, err=err)
    if result_callback:
        reactor.callFromThread(result_callback, err)  # @UndefinedVariable


#------------------------------------------------------------------------------


def sending_thread(url, active_queue):
    if _Debug:
        lg.args(_DebugLevel, url=url)
    while True:
        if not is_started(url):
            if _Debug:
                lg.dbg(_DebugLevel, '\nrequests thread %s is finishing because websocket is not started' % url)
            break
        raw_data, tm = active_queue.get()
        if raw_data is None:
            if _Debug:
                lg.dbg(_DebugLevel, '\nrequests thread %s received empty request, about to stop the thread now' % url)
            break
        if not ws(url):
            on_fail(Exception('websocket is closed'))
            continue
        if _Debug:
            lg.args(_DebugLevel, url=url, size=len(raw_data), raw_data=raw_data)
        ws(url).send(raw_data)
    if _Debug:
        lg.dbg(_DebugLevel, '\nrequests thread %s finished' % url)


def websocket_thread(url):
    global _WebSocketApp
    global _WebSocketClosed
    websocket.enableTrace(False)
    while is_started(url):
        _WebSocketClosed[url] = False
        if _Debug:
            lg.dbg(_DebugLevel, 'websocket thread url=%r' % url)
        _WebSocketApp[url] = websocket.WebSocketApp(
            url=url,
            on_message=on_incoming_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open,
        )
        try:
            ws(url).run_forever(ping_interval=10)
        except Exception as exc:
            _WebSocketApp[url] = None
            if _Debug:
                lg.dbg(_DebugLevel, '\n    WS Thread ERROR: %r' % exc)
            time.sleep(1)
        if _WebSocketApp.get(url):
            _WebSocketApp.pop(url, None)
        if not is_started(url):
            break
        time.sleep(1)
    _WebSocketApp.pop(url, None)


#------------------------------------------------------------------------------


def verify_state(url):
    global _WebSocketReady
    if is_closed(url):
        _WebSocketReady[url] = False
        if _Debug:
            lg.dbg(_DebugLevel, 'WS CALL REFUSED, websocket %s already closed' % url)
        if is_connecting(url):
            if _Debug:
                lg.dbg(_DebugLevel, 'websocket %s closed but still connecting' % url)
            return 'closed'
        return 'closed'
    if is_ready(url):
        return 'ready'
    if is_connecting(url):
        return 'connecting'
    if is_started(url):
        return 'connecting'
    return 'not-started'


#------------------------------------------------------------------------------


def ws_send(url, raw_data):
    global _PendingCalls
    st = verify_state(url)
    if _Debug:
        lg.args(_DebugLevel, url=url, st=st)
    if st == 'ready':
        ws_queue(url).put_nowait((raw_data, time.time()))
        return True
    if st == 'closed':
        lg.warn('websocket is already closed')
        return False
    if st == 'connecting':
        if _Debug:
            lg.dbg(_DebugLevel, 'websocket %s still connecting, remember pending request' % url)
        _PendingCalls[url].append((
            raw_data,
            time.time(),
        ))
        return True
    if st == 'not-started':
        if _Debug:
            lg.dbg(_DebugLevel, 'websocket %s was not started' % url)
        return False
    raise Exception('unexpected state %r' % st)


#------------------------------------------------------------------------------


class RoutedWebSocket(automat.Automat):

    """
    This class implements all the functionality of ``api_routed_device()`` state machine.
    """

    def __init__(self, debug_level=_DebugLevel, log_events=_Debug, log_transitions=_Debug, publish_events=False, **kwargs):
        """
        Builds `api_routed_device()` state machine.
        """
        super(RoutedWebSocket, self).__init__(name='routed_web_socket', state='AT_STARTUP', debug_level=debug_level, log_events=log_events, log_transitions=log_transitions, publish_events=publish_events, **kwargs)

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of `api_routed_device()` machine.
        """
        # TODO: read known routers from local file
        self.selected_routers = []
        self.connected_routers = {}
        self.active_router_url = None
        self.handshaked_routers = []

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `api_routed_device()` state were changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in the `api_routed_device()`
        but automat state was not changed.
        """

    def to_json(self, short=True):
        ret = super().to_json(short=short)
        ret.update({
            'active_router': self.active_router_url,
            'connected_routers': self.handshaked_routers,
        })
        return ret

    #------------------------------------------------------------------------------

    def on_incoming_message(self, url, json_data):
        if _Debug:
            lg.args(_DebugLevel, url=url, inp=json_data)
        if json_data.get('route_id'):
            self._on_web_socket_router_first_response(url, json_data)
            return True
        cmd = json_data.get('cmd')
        if cmd == 'api':
            self.active_router_url = url
            self.event('api-message', url=url, json_data=json_data)
            return True
        if cmd == 'handshake-accepted':
            route_url = json_data.get('route_url')
            if not route_url:
                return False
            self._on_web_socket_handshake_accepted(url, route_url)
            return True
        if cmd == 'client-public-key':
            try:
                client_key_object = rsa_key.RSAKey()
                client_key_object.fromString(json_data.get('client_public_key'))
            except:
                lg.exc()
                self.automat('auth-error')
                return False
            self.active_router_url = url
            self.automat('client-pub-key-received', client_key_object=client_key_object)
            return True
        if cmd == 'server-code':
            try:
                signature = json_data['signature']
                encrypted_server_code = json_data['server_code']
            except:
                lg.exc()
                self.automat('auth-error')
                return False
            self.on_server_code_received(signature=signature, encrypted_server_code=encrypted_server_code)
            return True
        return False

    def on_outgoing_message(self, json_data):
        if _Debug:
            lg.args(_DebugLevel, json_data)
        if self.state != 'READY':
            lg.warn('skip sending api message to client, %r state is %r' % (self, self.state))
            return False
        return self._do_push_encrypted(json_data)

    def on_server_code_received(self, signature, encrypted_server_code):
        try:
            orig_encrypted_server_code = base64.b64decode(strng.to_bin(encrypted_server_code))
            received_server_code_salted = strng.to_text(self.device_key_object.decrypt(orig_encrypted_server_code))
            received_server_code = received_server_code_salted.split('-')[0]
        except:
            lg.exc()
            self.automat('auth-error')
            return
        if _Debug:
            lg.args(_DebugLevel, received_server_code_salted=received_server_code_salted)
        hashed_server_code = hashes.sha1(strng.to_bin(received_server_code_salted))
        if not self.client_key_object.verify(signature, hashed_server_code):
            lg.err('signature verification error, received server code is not valid')
            self.automat('auth-error')
            return
        if received_server_code != self.server_code:
            lg.warn('received server code %r is not matching with generated code %r' % (received_server_code, self.server_code))
            self.automat('auth-error')
            return
        if _Debug:
            lg.args(_DebugLevel, received_server_code=received_server_code)
        self.automat('valid-server-code-received')

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
                self.doLoadAuthInfo(*args, **kwargs)
                self.doNotifyListening(*args, **kwargs)
            elif event == 'routers-failed':
                self.state = 'ROUTERS?'
                self.doLookupRequestRouters(*args, **kwargs)
            elif event == 'stop':
                self.state = 'CLOSED'
                self.doDisconnectRouters(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
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
        return len(kwargs['device_object'].meta.get('connected_routers', {})) >= 3

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        global _IncomingRoutedMessageCallback
        _IncomingRoutedMessageCallback = self.on_incoming_message
        self.device_key_object = kwargs['device_object']
        self.device_name = self.device_key_object.label
        self.connected_routers = self.device_key_object.meta.get('connected_routers', {})
        self.auth_token = None
        self.session_key = None
        self.client_key_object = None
        self.listening_callback = kwargs.get('listening_callback')

    def doLookupRequestRouters(self, *args, **kwargs):
        """
        Action method.
        """
        self.router_lookups = 0
        self.selected_routers = []
        for url, route_id in self.connected_routers.items():
            if route_id:
                self.selected_routers.append(url)
        self._do_lookup_next_router()

    def doConnectRouters(self, *args, **kwargs):
        """
        Action method.
        """
        self.connecting_routers = []
        self.handshaked_routers = []
        self.active_router_url = None
        for url, route_id in self.connected_routers.items():
            if not route_id:
                continue
            route_url = '{}/?i={}'.format(url, route_id)
            self.connecting_routers.append(route_url)
            start_client(url=route_url, callbacks={
                'on_open': self._on_web_socket_router_connection_opened,
                'on_error': self._on_web_socket_router_connection_error,
            })

    def doDisconnectRouters(self, event, *args, **kwargs):
        """
        Action method.
        """
        # TODO: notify about failed result
        for url, route_id in self.connected_routers.items():
            if not route_id:
                continue
            route_url = '{}/?i={}'.format(url, route_id)
            stop_client(url=route_url)
        self.handshaked_routers = []
        self.active_router_url = None
        if event == 'auth-error':
            # TODO: erase stored authorization
            pass
        if event == 'lookup-failed':
            if self.listening_callback:
                reactor.callLater(0, self.listening_callback, False)  # @UndefinedVariable

    def doSaveRouters(self, *args, **kwargs):
        """
        Action method.
        """
        self.device_key_object.meta['connected_routers'] = self.connected_routers
        self.device_key_object.save()

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
        self.device_key_object.meta['auth_token'] = self.auth_token
        self.device_key_object.meta['session_key'] = strng.to_text(base64.b64encode(self.session_key))
        self.device_key_object.meta['client_public_key'] = self.client_key_object.toPublicString()
        self.device_key_object.save()

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
            self.server_code = cipher.generate_digits(6, as_text=True)
        if _Debug:
            lg.args(_DebugLevel, server_code=self.server_code)

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
        client_code = kwargs['client_code']
        session_key_text = strng.to_text(base64.b64encode(self.session_key))
        salted_payload = '{}#{}#{}#{}'.format(client_code, self.auth_token, session_key_text, cipher.generate_secret_text(32))
        # salted_payload = jsn.dumps({
        #     'client_code': client_code,
        #     'auth_token': self.auth_token,
        #     'session_key': session_key_text,
        #     'salt': cipher.generate_secret_text(32),
        # })
        encrypted_payload = base64.b64encode(self.client_key_object.encrypt(strng.to_bin(salted_payload)))
        hashed_payload = hashes.sha1(strng.to_bin(salted_payload))
        if _Debug:
            lg.args(_DebugLevel, client_code=client_code)
        self._do_push({
            'cmd': 'client-code',
            'auth': strng.to_text(encrypted_payload),
            'signature': strng.to_text(self.device_key_object.sign(hashed_payload)),
            'routers': self.handshaked_routers,
        })

    def doWaitClientCodeInput(self, *args, **kwargs):
        """
        Action method.
        """
        BITDUST_WEB_SOCKET_CLIENT_CODE_INPUT = os.environ.get('BITDUST_WEB_SOCKET_CLIENT_CODE_INPUT', None)
        if BITDUST_WEB_SOCKET_CLIENT_CODE_INPUT:
            client_code = BITDUST_WEB_SOCKET_CLIENT_CODE_INPUT.strip()
        else:
            # TODO: call a callback here to request user input
            client_code = input().strip()
        if _Debug:
            lg.args(_DebugLevel, client_code=client_code)
        self.automat('client-code-input-received', client_code=client_code)

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
        ws_send(
            url=ws_inst.url,
            raw_data=jsn.dumps({
                'cmd': 'handshake',
                'internal': True,
            }),
        )

    def _on_web_socket_router_connection_error(self, ws_inst, err):
        url = ws_inst.url
        if not ws_inst.url:
            lg.warn('missed connecting web router: %r' % url)
        else:
            self.connecting_routers.remove(url)
        handshaked_count = len(self.handshaked_routers)
        if _Debug:
            lg.args(_DebugLevel, ws_inst=ws_inst, err=err, connecting=len(self.connecting_routers), handshaked=handshaked_count)
        if not self.connecting_routers:
            if handshaked_count > 0:
                self.automat('routers-connected')
            else:
                self.automat('routers-failed')

    def _on_web_socket_handshake_accepted(self, url, route_url):
        if not url:
            lg.warn('missed connecting web router: %r' % url)
        else:
            self.connecting_routers.remove(url)
        if not self.active_router_url:
            self.active_router_url = route_url
        self.handshaked_routers.append(route_url)
        handshaked_count = len(self.handshaked_routers)
        if _Debug:
            lg.args(_DebugLevel, url=url, connecting=len(self.connecting_routers), handshaked=handshaked_count, active=self.active_router_url)
        if not self.connecting_routers:
            if handshaked_count > 0:
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
        for location in results:
            if location not in self.selected_routers:
                self.selected_routers.append(location)
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
        if _Debug:
            lg.args(_DebugLevel, url=url, resp=resp)
        try:
            stop_client(url)
        except:
            lg.exc()
        if self.connected_routers.get(url):
            lg.warn('web socket router at %s was already connected' % url)
            if len(self.connected_routers) >= 3:
                self.automat('routers-selected')
            return None
        route_id = None
        try:
            route_id = resp['route_id']
        except:
            lg.exc()
        if resp['result'] == 'accepted':
            self.connected_routers[url] = route_id
        else:
            self.connected_routers[url] = None
        if len(self.connected_routers) >= 3:
            self.automat('routers-selected')
        return None

    def _on_web_socket_router_first_connection_opened(self, ws_inst):
        if _Debug:
            lg.args(_DebugLevel, ws_inst=ws_inst)
        ws_send(
            url=ws_inst.url,
            raw_data=jsn.dumps({
                'cmd': 'connect-request',
            }),
        )

    def _on_web_socket_router_first_connection_error(self, ws_inst, err):
        if _Debug:
            lg.args(_DebugLevel, ws_inst=ws_inst, err=err)
        url = ws_inst.url
        try:
            stop_client(url)
        except:
            lg.exc()
        self.connected_routers[url] = None
        if len(self.connected_routers) >= 3:
            self.automat('routers-selected')
        return None

    #------------------------------------------------------------------------------

    def _do_connect_routers(self):
        if _Debug:
            lg.args(_DebugLevel, selected_routers=self.selected_routers)
        for location in self.selected_routers:
            start_client(location, callbacks={
                'on_open': self._on_web_socket_router_first_connection_opened,
                'on_error': self._on_web_socket_router_first_connection_error,
            })

    def _do_lookup_next_router(self):
        if _Debug:
            lg.args(_DebugLevel, lookups=self.router_lookups, connected=len(self.connected_routers), selected=len(self.selected_routers))
        if len(self.selected_routers) >= 3:  # TODO: read from settings.: max web socket routers
            reactor.callLater(0, self._do_connect_routers)  # @UndefinedVariable
            return
        if self.router_lookups >= 10:  # TODO: read from settings.
            if len(self.selected_routers) >= 3:  # TODO: read from settings: min web socket routers
                reactor.callLater(0, self._do_connect_routers)  # @UndefinedVariable
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
        ws_send(self.active_router_url, raw_data)
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
        ws_send(self.active_router_url, encrypted_raw_data)
        if _Debug:
            lg.out(_DebugLevel, '***   API %s PUSH %d encrypted bytes: %r' % (self.device_name, len(encrypted_raw_data), encrypted_json_data))
        return True
