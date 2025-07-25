#!/usr/bin/python
# encrypted_web_socket.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (encrypted_web_socket.py) is part of BitDust Software.
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
.. module:: encrypted_web_socket
.. role:: red

BitDust encrypted_web_socket() Automat

EVENTS:
    * :red:`api-message`
    * :red:`auth-error`
    * :red:`client-code-input-received`
    * :red:`client-pub-key-received`
    * :red:`server-code-failed`
    * :red:`start`
    * :red:`stop`
    * :red:`valid-server-code-received`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 8

#------------------------------------------------------------------------------

import os
import base64

#------------------------------------------------------------------------------

from twisted.application.strports import listen
from twisted.internet.protocol import Protocol, Factory
from twisted.internet import reactor

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.lib import txws
from bitdust.lib import strng
from bitdust.lib import serialization

from bitdust.main import events

from bitdust.crypt import rsa_key
from bitdust.crypt import cipher
from bitdust.crypt import hashes

#------------------------------------------------------------------------------

_Listeners = {}
_Transports = {}
_IncomingAPIMessageCallback = None

#------------------------------------------------------------------------------


def SetIncomingAPIMessageCallback(cb):
    global _IncomingAPIMessageCallback
    _IncomingAPIMessageCallback = cb


def ExecuteIncomingAPIMessageCallback(instance, json_message):
    global _IncomingAPIMessageCallback
    return _IncomingAPIMessageCallback(instance, json_message)


#------------------------------------------------------------------------------


class EncryptedWebSocketProtocol(Protocol):

    _key = None

    def dataReceived(self, data):
        try:
            json_data = serialization.BytesToDict(data, keys_to_text=True, values_to_text=True, encoding='utf-8')
        except:
            lg.exc()
            return
        if _Debug:
            lg.dbg(_DebugLevel, 'received %d bytes from web socket' % len(data))
        self.factory.instance.on_incoming_message(json_data)

    def connectionMade(self):
        global _Transports
        Protocol.connectionMade(self)
        peer = self.transport.getPeer()
        self._key = (peer.type, peer.host, peer.port)
        peer_text = '%s://%s:%s' % (self._key[0], self._key[1], self._key[2])
        if self.factory.instance.device_name not in _Transports:
            _Transports[self.factory.instance.device_name] = {}
        _Transports[self.factory.instance.device_name][self._key] = self.transport
        if _Debug:
            lg.args(_DebugLevel, device_name=self.factory.instance.device_name, peer=peer_text, ws_connections=len(_Transports))

    def connectionLost(self, *args, **kwargs):
        global _Transports
        Protocol.connectionLost(self, *args, **kwargs)
        peer_text = '%s://%s:%s' % (self._key[0], self._key[1], self._key[2])
        if self.factory.instance.device_name in _Transports:
            _Transports[self.factory.instance.device_name].pop(self._key)
            if not _Transports:
                self.factory.instance.client_connected = False
        else:
            lg.err('device %r was already stopped, connection closed: %r' % (self.factory.instance.device_name, peer_text))
        self._key = None
        if _Debug:
            lg.args(_DebugLevel, device_name=self.factory.instance.device_name, peer=peer_text, ws_connections=len(_Transports))


class EncryptedWebSocketFactory(Factory):

    protocol = EncryptedWebSocketProtocol

    def __init__(self, instance):
        self.instance = instance


#------------------------------------------------------------------------------


class WrappedEncryptedWebSocketProtocol(txws.WebSocketProtocol):
    pass


class WrappedEncryptedWebSocketFactory(txws.WebSocketFactory):

    protocol = WrappedEncryptedWebSocketProtocol


#------------------------------------------------------------------------------


class EncryptedWebSocket(automat.Automat):

    """
    This class implements all the functionality of ``encrypted_web_socket()`` state machine.
    """

    def __init__(self, debug_level=_DebugLevel, log_events=_Debug, log_transitions=_Debug, publish_events=False, **kwargs):
        """
        Builds `encrypted_web_socket()` state machine.
        """
        self.device_key_object = kwargs.pop('device_object')
        self.device_name = self.device_key_object.label
        self.encrypt_auth_info_callback = kwargs.pop('encrypt_auth_info_callback')
        self.host = kwargs.pop('host')
        self.port_number = int(kwargs.pop('port_number'))
        self.url = f'ws://{self.host.strip().strip("/")}:{self.port_number}'
        self.server_code = None
        self.client_connected = False
        super(EncryptedWebSocket, self).__init__(
            name='encrypted_web_socket',
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
        return '%s[%s%s](%s)' % (
            self.id,
            '*' if self.client_connected else '',
            self.url or '?',
            self.state,
        )

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `routed_web_socket()` state were changed.
        """
        if event == 'auth-error':
            if oldstate in ('CLIENT_PUB?', 'SERVER_CODE?', 'CLIENT_CODE?'):
                events.send('web-socket-handshake-failed', data=self.to_json())

    def to_json(self, short=True):
        ret = super().to_json(short=short)
        ret.update({
            'url': self.url,
            'port_number': self.port_number,
            'server_code': self.server_code,
            'device_name': self.device_name,
            'client_connected': self.client_connected,
        })
        return ret

    def on_incoming_message(self, json_data):
        if _Debug:
            lg.args(_DebugLevel, inp=json_data)
        cmd = json_data.get('cmd')
        if cmd == 'api':
            if self.state != 'READY':
                lg.warn('received api request, but web socket is not ready yet')
                self.automat('auth-error')
                return False
            self.client_connected = True
            self.event('api-message', json_data=json_data)
            return True
        elif cmd == 'client-public-key':
            try:
                client_key_object = rsa_key.RSAKey()
                client_key_object.fromString(json_data.get('client_public_key'))
            except:
                lg.exc()
                self.automat('auth-error')
                return False
            self.automat('client-pub-key-received', client_key_object=client_key_object)
            return True
        elif cmd == 'server-code':
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
            self.on_server_code_received(signature=signature, encrypted_server_code=encrypted_server_code)
            return True
        return False

    def on_outgoing_message(self, json_data):
        if json_data.get('cmd') == 'push':
            if not self.client_connected:
                return False
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
            elif event == 'auth-error' or event == 'stop':
                self.state = 'CLOSED'
                self.doRemoveAuthToken(event, *args, **kwargs)
                self.doStopListener(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'client-pub-key-received':
                self.state = 'SERVER_CODE?'
                self.doSaveClientPublicKey(*args, **kwargs)
                self.doGenerateAuthToken(*args, **kwargs)
                self.doGenerateServerCode(*args, **kwargs)
                self.doSendServerPubKey(*args, **kwargs)
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'start' and not self.isAuthenticated(*args, **kwargs):
                self.state = 'CLIENT_PUB?'
                self.doInit(*args, **kwargs)
                self.doStartListener(*args, **kwargs)
            elif event == 'start' and self.isAuthenticated(*args, **kwargs):
                self.state = 'READY'
                self.doInit(*args, **kwargs)
                self.doLoadAuthInfo(*args, **kwargs)
                self.doStartListener(*args, **kwargs)
        #---CLIENT_PUB?---
        elif self.state == 'CLIENT_PUB?':
            if event == 'auth-error' or event == 'stop':
                self.state = 'CLOSED'
                self.doRemoveAuthToken(event, *args, **kwargs)
                self.doStopListener(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'client-pub-key-received':
                self.state = 'SERVER_CODE?'
                self.doSaveClientPublicKey(*args, **kwargs)
                self.doGenerateAuthToken(*args, **kwargs)
                self.doGenerateServerCode(*args, **kwargs)
                self.doSendServerPubKey(*args, **kwargs)
        #---SERVER_CODE?---
        elif self.state == 'SERVER_CODE?':
            if event == 'auth-error' or event == 'stop':
                self.state = 'CLOSED'
                self.doRemoveAuthToken(event, *args, **kwargs)
                self.doStopListener(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'client-pub-key-received':
                self.doSaveClientPublicKey(*args, **kwargs)
                self.doGenerateAuthToken(*args, **kwargs)
                self.doGenerateServerCode(*args, **kwargs)
                self.doSendServerPubKey(*args, **kwargs)
            elif event == 'valid-server-code-received':
                self.state = 'CLIENT_CODE?'
                self.doWaitClientCodeInput(*args, **kwargs)
            elif event == 'server-code-failed':
                self.state = 'CLIENT_PUB?'
                self.doEraseServerCode(*args, **kwargs)
        #---CLIENT_CODE?---
        elif self.state == 'CLIENT_CODE?':
            if event == 'client-code-input-received':
                self.state = 'READY'
                self.doSaveAuthInfo(*args, **kwargs)
                self.doSendClientCode(*args, **kwargs)
            elif event == 'auth-error' or event == 'stop':
                self.state = 'CLOSED'
                self.doRemoveAuthToken(event, *args, **kwargs)
                self.doStopListener(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'client-pub-key-received':
                self.state = 'SERVER_CODE?'
                self.doSaveClientPublicKey(*args, **kwargs)
                self.doGenerateAuthToken(*args, **kwargs)
                self.doGenerateServerCode(*args, **kwargs)
                self.doSendServerPubKey(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        return None

    def isAuthenticated(self, *args, **kwargs):
        """
        Condition method.
        """
        if self.device_key_object.meta.get('auth_token'):
            return True
        return False

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.auth_token = None
        self.session_key = None
        self.client_key_object = None
        self.listening_callback = kwargs.get('listening_callback')
        self.client_code_input_callback = kwargs.get('client_code_input_callback')

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
            'listeners': [self.url],
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

    def doStartListener(self, *args, **kwargs):
        """
        Action method.
        """
        global _Listeners
        try:
            ws = WrappedEncryptedWebSocketFactory(EncryptedWebSocketFactory(instance=self))
            _Listeners[self.device_name] = listen(f'tcp:{self.port_number}:interface={self.host}', ws)
        except:
            lg.exc()
            cb = self.listening_callback
            self.automat('stop')
            if cb:
                reactor.callLater(0, cb, False)  # @UndefinedVariable
            return None, None
        self.device_key_object.meta['url'] = self.url
        self.device_key_object.save()
        if _Debug:
            lg.args(_DebugLevel, listener=_Listeners[self.device_name], device=ws)
        if self.listening_callback:
            reactor.callLater(0, self.listening_callback, True)  # @UndefinedVariable
        return _Listeners[self.device_name], ws

    def doStopListener(self, *args, **kwargs):
        """
        Action method.
        """
        global _Listeners
        if self.device_name in _Listeners:
            if _Debug:
                lg.out(_DebugLevel, 'encrypted_web_socket.doStopListener calling stopListening() for %r' % self.device_name)
            _Listeners[self.device_name].stopListening()
            _Listeners.pop(self.device_name)
        else:
            lg.warn('listener was not started')

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.destroy()

    #------------------------------------------------------------------------------

    def _do_push(self, json_data):
        global _Transports
        if not _Transports or self.device_name not in _Transports:
            lg.warn('there are currently no web socket transports open')
            return False
        raw_bytes = serialization.DictToBytes(json_data, encoding='utf-8')
        for _key, transp in _Transports[self.device_name].items():
            try:
                transp.write(raw_bytes)
            except:
                lg.exc()
                continue
            if _Debug:
                lg.dbg(_DebugLevel, 'sent %d bytes to web socket %s' % (len(raw_bytes), '%s://%s:%s' % (_key[0], _key[1], _key[2])))
        if _Debug:
            lg.out(_DebugLevel, '***   API %s PUSH  %d bytes: %r' % (self.device_name, len(raw_bytes), json_data))
        return True

    def _do_push_encrypted(self, json_data):
        global _Transports
        if not _Transports or self.device_name not in _Transports:
            lg.warn('there are currently no web socket transports open')
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
        for _key, transp in _Transports[self.device_name].items():
            try:
                transp.write(encrypted_raw_data)
            except:
                lg.exc()
                continue
            if _Debug:
                lg.dbg(_DebugLevel, 'sent %d encrypted bytes to web socket %s' % (len(encrypted_raw_data), '%s://%s:%s' % (_key[0], _key[1], _key[2])))
        if _Debug:
            lg.out(_DebugLevel, '***   API %s PUSH %d encrypted bytes: %r' % (self.device_name, len(encrypted_raw_data), json_data))
        return True
