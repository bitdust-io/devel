#!/usr/bin/python
# api_device.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (api_device.py) is part of BitDust Software.
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
from random import _inst
"""
.. module:: api_device.

"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

import os

#------------------------------------------------------------------------------

from twisted.application.strports import listen
from twisted.internet.protocol import Protocol, Factory

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.lib import txws
from bitdust.lib import jsn
from bitdust.lib import serialization

from bitdust.main import settings

from bitdust.system import local_fs

from bitdust.crypt import rsa_key
from bitdust.crypt import cipher

#------------------------------------------------------------------------------

_Devices = {}
_Listeners = {}
_Transports = {}
_Instances = {}

#------------------------------------------------------------------------------


def init():
    if not os.path.exists(settings.DevicesDir()):
        if _Debug:
            lg.out(_DebugLevel, 'api_device.init will create folder: ' + settings.DevicesDir())
        os.makedirs(settings.DevicesDir())
    load_devices()
    start_devices()


def shutdown():
    pass


#------------------------------------------------------------------------------


def devices(device_name=None):
    global _Devices
    if device_name is None:
        return _Devices
    return _Devices.get(device_name)


def instances(device_name=None):
    global _Instances
    if device_name is None:
        return _Instances
    return _Instances.get(device_name)


#------------------------------------------------------------------------------


def save_device(device_name, device_key_object):
    device_file_path = os.path.join(settings.DevicesDir(), device_name)
    device_info_dict = device_key_object.toDict(include_private=True)
    device_info_raw = jsn.dumps(device_info_dict, indent=1, separators=(',', ':'))
    if not local_fs.WriteTextFile(device_file_path, device_info_raw):
        lg.err('failed saving device info %r to %r' % (device_name, device_file_path))
        return False
    if _Debug:
        lg.args(_DebugLevel, device_name=device_name, key=device_key_object)
    return True


def load_device(device_name):
    device_file_path = os.path.join(settings.DevicesDir(), device_name)
    device_info_raw = local_fs.ReadTextFile(device_file_path)
    if not device_info_raw:
        lg.warn('failed reading device file %r' % device_file_path)
        return None
    device_info_dict = jsn.loads_text(device_info_raw.strip())
    try:
        device_key_object = rsa_key.RSAKey()
        device_key_object.fromDict(device_info_dict)
    except:
        lg.exc()
        return None
    if _Debug:
        lg.args(_DebugLevel, device_name=device_name, key=device_key_object)
    return device_key_object


#------------------------------------------------------------------------------


def add_device(device_name, port_number, key_size=4096):
    global _Devices
    if device_name in _Devices:
        raise Exception('device %r already exist' % device_name)
    device_key_object = rsa_key.RSAKey()
    device_key_object.generate(key_size)
    device_key_object.label = device_name
    device_key_object.active = False
    device_key_object.meta['port_number'] = port_number
    device_key_object.meta['state'] = 'client_public_key'
    device_key_object.meta['auth_token'] = None
    device_key_object.meta['session_key'] = None
    device_key_object.meta['client_public_key'] = None
    if not save_device(device_name, device_key_object):
        return False
    _Devices[device_name] = device_key_object
    return True


def remove_device(device_name):
    if not devices(device_name):
        raise Exception('device %r does not exist' % device_name)


#------------------------------------------------------------------------------


def enable_device(device_name):
    device_key_object = devices(device_name)
    if not device_key_object:
        raise Exception('device %r does not exist' % device_name)
    if device_key_object.active:
        lg.warn('device %r is already active' % device_name)
        return False
    device_key_object.active = True
    save_device(device_name, device_key_object)
    lg.info('device %r was activated' % device_name)
    return True


def disable_device(device_name):
    pass

#------------------------------------------------------------------------------

def start_device(device_name):
    global _Instances
    if device_name in _Instances:
        raise Exception('device %r was already started' % device_name)
    device_key_object = devices(device_name)
    if not device_key_object:
        raise Exception('device %r does not exist' % device_name)
    if not device_key_object.active:
        raise Exception('device %r is not active' % device_name)
    port_number = device_key_object.meta['port_number']
    inst = APIDevice()
    if _Debug:
        lg.args(_DebugLevel, device_name, port_number=port_number, instance=inst)
    _Instances[device_name] = inst
    inst.automat('init', device_name=device_name, port_number=port_number)
    return inst


def stop_device(device_name):
    global _Instances
    if device_name not in _Instances:
        raise Exception('device %r was not started' % device_name)
    inst = _Instances[device_name]
    inst.automat('shutdown')
    _Instances.pop(device_name)

#------------------------------------------------------------------------------


def load_devices():
    global _Devices
    for device_name in os.listdir(settings.DevicesDir()):
        device_key_object = load_device(device_name)
        if not device_key_object:
            continue
        _Devices[device_name] = device_key_object
    if _Debug:
        lg.args(_DebugLevel, devices=len(_Devices))


def start_devices():
    for device_name in devices():
        device_key_object = devices(device_name)
        if not device_key_object.active:
            continue
        start_device(device_name)


#------------------------------------------------------------------------------


def on_incoming_message(device_name, json_data):
    if _Debug:
        lg.args(_DebugLevel, inp=json_data)
    inst = instances(device_name)
    if not inst:
        lg.err('received API message for unknown device instance %r' % device_name)
        return False
    cmd = json_data.get('cmd')
    if cmd == 'api':
        device_key_object = devices(device_name)
        if not device_key_object:
            lg.err('received API message for unknown device %r' % device_name)
            return False
        auth_token = device_key_object.meta.get('auth_token')
        if not auth_token:
            lg.err('received API message for unauthorized device %r' % device_name)
            return False
        if auth_token != json_data.get('auth'):
            lg.err('received unauthorized API message for device %r' % device_name)
            return False
        session_key = device_key_object.meta.get('session_key')
        if not session_key:
            lg.err('received API message for device %r, but session key is empty' % device_name)
            return False
        raw_data = cipher.decrypt_json(json_data.inp, session_key)
        try:
            api_message_payload = serialization.BytesToDict(raw_data, keys_to_text=True, values_to_text=True, encoding='utf-8')
        except:
            lg.exc()
            return False
        inst.event('api-message', api_message=api_message_payload)
        return True
    elif cmd == 'client-public-key':
        client_public_key = json_data.get('client-public-key')
        inst.automat('client-pub-key-received', client_public_key=client_public_key)
        return True
    elif cmd == 'server-code':
        server_code = json_data.get('server-code')
        inst.automat('valid-server-code-received', server_code=server_code)
        return True
    return False

#------------------------------------------------------------------------------


class DeviceProtocol(Protocol):

    _key = None

    def dataReceived(self, data):
        try:
            json_data = serialization.BytesToDict(data, keys_to_text=True, values_to_text=True, encoding='utf-8')
        except:
            lg.exc()
            return
        if _Debug:
            lg.dbg(_DebugLevel, 'received %d bytes from web socket: %r' % (len(data), json_data))
        on_incoming_message(self.factory.device_name, json_data)

    def connectionMade(self):
        global _Transports
        Protocol.connectionMade(self)
        peer = self.transport.getPeer()
        self._key = (
            peer.type,
            peer.host,
            peer.port,
        )
        peer = '%s://%s:%s' % (self._key[0], self._key[1], self._key[2])
        if self.factory.device_name not in _Transports:
            _Transports[_Transports] = {}
        _Transports[self.factory.device_name][self._key] = self.transport
        if _Debug:
            lg.args(_DebugLevel, device_name=self.factory.device_name, peer=peer, ws_connections=len(_Transports))
        # events.send('web-socket-connected', data=dict(peer=peer))

    def connectionLost(self, *args, **kwargs):
        global _Transports
        Protocol.connectionLost(self, *args, **kwargs)
        peer = '%s://%s:%s' % (self._key[0], self._key[1], self._key[2])
        if self.factory.device_name in _Transports:
            _Transports.pop(self._key)
        else:
            lg.err('device %r was already stopped, connection closed: %r' % (self.factory.device_name, peer))
        self._key = None
        if _Debug:
            lg.args(_DebugLevel, device_name=self.factory.device_name, peer=peer, ws_connections=len(_Transports))
        # events.send('web-socket-disconnected', data=dict(peer=peer))


class DeviceFactory(Factory):

    protocol = DeviceProtocol

    def __init__(self, device_name):
        self.device_name = device_name

#------------------------------------------------------------------------------


class WrappedDeviceProtocol(txws.WebSocketProtocol):
    pass


class WrappedDeviceFactory(txws.WebSocketFactory):

    protocol = WrappedDeviceProtocol


#------------------------------------------------------------------------------


class APIDevice(automat.Automat):

    """
    This class implements all the functionality of ``api_device()`` state machine.
    """

    def __init__(self, debug_level=_DebugLevel, log_events=_Debug, log_transitions=_Debug, publish_events=False, **kwargs):
        """
        Builds `api_device()` state machine.
        """
        super(APIDevice, self).__init__(name='api_device', state='AT_STARTUP', debug_level=debug_level, log_events=log_events, log_transitions=log_transitions, publish_events=publish_events, **kwargs)

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of `api_device()` machine.
        """

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `api_device()` state were changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in the `api_device()`
        but automat state was not changed.
        """

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <https://github.com/vesellov/visio2python>`_ tool.
        """
        #---READY---
        if self.state == 'READY':
            if event == 'api-message':
                self.doProcess(*args, **kwargs)
            elif event == 'client-pub-key-received':
                self.state = 'CLIENT_PUB?'
                self.doGenerateAuthToken(*args, **kwargs)
                self.doGenerateServerCode(*args, **kwargs)
                self.doSendServerPubKey(*args, **kwargs)
            elif event == 'stop':
                self.state = 'CLOSED'
                self.doStopListener(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'auth-error':
                self.state = 'CLOSED'
                self.doRemoveAuthToken(*args, **kwargs)
                self.doStopListener(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---AT_STARTUP---
        elif self.state == 'AT_STARTUP':
            if event == 'start' and not self.isAuthenticated(*args, **kwargs):
                self.state = 'CLIENT_PUB?'
                self.doInit(*args, **kwargs)
                self.doStartListener()
            elif event == 'start' and self.isAuthenticated(*args, **kwargs):
                self.state = 'READY'
                self.doInit(*args, **kwargs)
                self.doLoadDevice(*args, **kwargs)
                self.doStartListener()
        #---CLIENT_PUB?---
        elif self.state == 'CLIENT_PUB?':
            if event == 'client-pub-key-received':
                self.state = 'SERVER_CODE?'
                self.doGenerateAuthToken(*args, **kwargs)
                self.doGenerateServerCode(*args, **kwargs)
                self.doSendServerPubKey(*args, **kwargs)
            elif event == 'stop':
                self.state = 'CLOSED'
                self.doStopListener(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---SERVER_CODE?---
        elif self.state == 'SERVER_CODE?':
            if event == 'client-pub-key-received':
                self.state = 'CLIENT_PUB?'
                self.doGenerateAuthToken(*args, **kwargs)
                self.doGenerateServerCode(*args, **kwargs)
                self.doSendServerPubKey(*args, **kwargs)
            elif event == 'valid-server-code-received':
                self.state = 'CLIENT_CODE?'
                self.doWaitClientCodeInput(*args, **kwargs)
            elif event == 'stop':
                self.state = 'CLOSED'
                self.doStopListener(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---CLIENT_CODE?---
        elif self.state == 'CLIENT_CODE?':
            if event == 'client-code-input-received':
                self.state = 'READY'
                self.doSendClientCode(*args, **kwargs)
                self.doSaveAuthToken(*args, **kwargs)
            elif event == 'client-pub-key-received':
                self.state = 'CLIENT_PUB?'
                self.doGenerateAuthToken(*args, **kwargs)
                self.doGenerateServerCode(*args, **kwargs)
                self.doSendServerPubKey(*args, **kwargs)
            elif event == 'stop':
                self.state = 'CLOSED'
                self.doStopListener(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass

    def isAuthenticated(self, *args, **kwargs):
        """
        Condition method.
        """
        device_name = kwargs['device_name']
        device_key_object = devices(device_name)
        if not device_key_object:
            return False
        if not device_key_object.meta.get('auth_token'):
            return False
        return True

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.device_name = kwargs['device_name']
        self.port_number = kwargs['port_number']
        self.auth_token = None
        self.client_public_key = None

    def doLoadDevice(self, *args, **kwargs):
        """
        Action method.
        """
        device_key_object = devices(self.device_name)
        self.auth_token = device_key_object.meta['auth_token']
        self.client_public_key = device_key_object.meta['client_public_key']

    def doGenerateServerCode(self, *args, **kwargs):
        """
        Action method.
        """
        self.server_code = cipher.generate_digits(6, as_text=True)

    def doGenerateAuthToken(self, *args, **kwargs):
        """
        Action method.
        """
        self.auth_token = cipher.make_key()

    def doProcess(self, *args, **kwargs):
        """
        Action method.
        """

    def doSendServerPubKey(self, *args, **kwargs):
        """
        Action method.
        """

    def doWaitClientCodeInput(self, *args, **kwargs):
        """
        Action method.
        """

    def doSendClientCode(self, *args, **kwargs):
        """
        Action method.
        """

    def doSaveAuthToken(self, *args, **kwargs):
        """
        Action method.
        """
        device_key_object = devices(self.device_name)
        device_key_object.meta['auth_token'] = self.auth_token
        save_device(self.device_name, device_key_object)

    def doRemoveAuthToken(self, *args, **kwargs):
        """
        Action method.
        """

    def doStartListener(self, *args, **kwargs):
        """
        Action method.
        """
        global _Listeners
        try:
            ws = WrappedDeviceFactory(DeviceFactory(device_name=self.device_name))
            _Listeners[self.device_name] = listen('tcp:%d' % self.port_number, ws)
        except:
            lg.exc()
        return _Listeners[self.device_name], ws

    def doStopListener(self, *args, **kwargs):
        """
        Action method.
        """

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.destroy()
