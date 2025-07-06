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
"""
.. module:: api_device

"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

_APILogFileEnabled = False

#------------------------------------------------------------------------------

import os
import base64

#------------------------------------------------------------------------------

from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.python.failure import Failure

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.lib import jsn
from bitdust.lib import strng

from bitdust.main import settings

from bitdust.system import local_fs

from bitdust.crypt import rsa_key
from bitdust.crypt import cipher
from bitdust.crypt import hashes

from bitdust.services import driver

from bitdust.interface import encrypted_web_socket
from bitdust.interface import routed_web_socket

#------------------------------------------------------------------------------

_Devices = {}
_Listeners = {}
_Transports = {}
_Instances = {}
_AllAPIMethods = []
_LegalDeviceNameCharacters = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-')
_LegalDeviceNameFirstCharacter = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ')

#------------------------------------------------------------------------------


def init():
    global _AllAPIMethods
    global _APILogFileEnabled
    _APILogFileEnabled = settings.config.conf().getBool('logs/api-enabled')
    from bitdust.interface import api
    encrypted_web_socket.SetIncomingAPIMessageCallback(do_process_incoming_message)
    routed_web_socket.SetIncomingAPIMessageCallback(do_process_incoming_message)
    _AllAPIMethods = api._ALL.copy()
    if _Debug:
        lg.out(_DebugLevel, 'api_device.init  with %d API methods' % len(_AllAPIMethods))
    if not os.path.exists(settings.DevicesDir()):
        if _Debug:
            lg.out(_DebugLevel, 'api_device.init will create folder: ' + settings.DevicesDir())
        os.makedirs(settings.DevicesDir())
    load_devices()
    start_direct_devices()
    reactor.addSystemEventTrigger('before', 'shutdown', routed_web_socket.shutdown_clients)  # @UndefinedVariable


def shutdown():
    if _Debug:
        lg.out(_DebugLevel, 'api_device.shutdown')
    stop_devices()


#------------------------------------------------------------------------------


def devices(device_name=None):
    global _Devices
    if device_name is None:
        return _Devices
    validate_device_name(device_name)
    return _Devices.get(device_name)


def instances(device_name=None):
    global _Instances
    if device_name is None:
        return _Instances
    validate_device_name(device_name)
    return _Instances.get(device_name)


#------------------------------------------------------------------------------


class APIDevice(rsa_key.RSAKey):

    def save(self):
        device_file_path = os.path.join(settings.DevicesDir(), self.label)
        device_info_dict = self.toDict(include_private=True)
        device_info_raw = jsn.dumps(device_info_dict, indent=2, separators=(',', ':'))
        if not local_fs.WriteTextFile(device_file_path, device_info_raw):
            lg.err('failed saving device info %r to %r' % (self.label, device_file_path))
            return False
        if _Debug:
            lg.args(_DebugLevel, n=self.label, k=self, m=self.meta, d=device_info_dict)
        return True

    def load(self, device_file_path):
        device_info_raw = local_fs.ReadTextFile(device_file_path)
        if not device_info_raw:
            lg.warn('failed reading device file %r' % device_file_path)
            return False
        device_info_dict = jsn.loads_text(device_info_raw.strip())
        try:
            self.fromDict(device_info_dict, exists_ok=True)
        except:
            lg.exc()
            return False
        # TODO: remove later
        if self.meta.get('connected_routers'):
            if not self.meta.get('authorized_routers'):
                self.meta['authorized_routers'] = self.meta.pop('connected_routers')
        if _Debug:
            lg.args(_DebugLevel, n=self.label, key=self, m=self.meta)
        return True


#------------------------------------------------------------------------------


def validate_device_name(device_name):
    """
    A method to validate device name entered by user.
    """
    global _LegalDeviceNameCharacters
    global _LegalDeviceNameFirstCharacter
    if len(device_name) < 3:
        raise Exception('device name is too short')
    if len(device_name) > 20:
        raise Exception('device name is too long')
    pos = 0
    for c in device_name:
        if c not in _LegalDeviceNameCharacters:
            raise Exception('device name has illegal character at position: %d' % pos)
        pos += 1
    if device_name[0] not in _LegalDeviceNameFirstCharacter:
        raise Exception('device name must begin with a letter')
    return True


#------------------------------------------------------------------------------


def add_encrypted_device(device_name, host='localhost', port_number=None, key_size=4096):
    global _Devices
    validate_device_name(device_name)
    if device_name in _Devices:
        raise Exception('device %r already exist' % device_name)
    if not port_number:
        port_number = settings.DefaultWebSocketEncryptedPort()
    if _Debug:
        lg.args(_DebugLevel, device_name=device_name, host=host, port_number=port_number)
    if len(_Devices) >= 1:
        raise Exception('currently it is not possible to connect more than one remote device')
    device_key_object = APIDevice(label=device_name)
    device_key_object.generate(key_size)
    device_key_object.active = False
    device_key_object.meta['routed'] = False
    device_key_object.meta['host'] = host
    device_key_object.meta['port_number'] = port_number
    device_key_object.meta['auth_token'] = None
    device_key_object.meta['session_key'] = None
    device_key_object.meta['client_public_key'] = None
    device_key_object.meta['url'] = f'ws://{host.strip().strip("/")}:{port_number}'
    if not device_key_object.save():
        return False
    _Devices[device_name] = device_key_object
    return True


def add_routed_device(device_name, key_size=4096):
    global _Devices
    validate_device_name(device_name)
    if device_name in _Devices:
        raise Exception('device %r already exist' % device_name)
    if not driver.is_on('service_nodes_lookup'):
        raise Exception('required service_nodes_lookup() is not currently ON')
    if _Debug:
        lg.args(_DebugLevel, device_name=device_name)
    if len(_Devices) >= 1:
        raise Exception('currently it is not possible to connect more than one remote device')
    device_key_object = APIDevice(label=device_name)
    device_key_object.generate(key_size)
    device_key_object.active = False
    device_key_object.meta['routed'] = True
    device_key_object.meta['port_number'] = None
    device_key_object.meta['auth_token'] = None
    device_key_object.meta['session_key'] = None
    device_key_object.meta['client_public_key'] = None
    if not device_key_object.save():
        return False
    _Devices[device_name] = device_key_object
    return True


def remove_device(device_name):
    validate_device_name(device_name)
    device_key_object = devices(device_name)
    if instances(device_name):
        stop_device(device_name)
    device_file_path = os.path.join(settings.DevicesDir(), device_name)
    if os.path.isfile(device_file_path):
        os.remove(device_file_path)
    else:
        lg.warn('device info file %s does not exist' % device_file_path)
    if device_key_object:
        devices().pop(device_name, None)
    if _Debug:
        lg.args(_DebugLevel, device_name=device_name, device_file_path=device_file_path)
    return True


#------------------------------------------------------------------------------


def enable_device(device_name):
    validate_device_name(device_name)
    device_key_object = devices(device_name)
    if not device_key_object:
        raise Exception('device %r does not exist' % device_name)
    if device_key_object.active:
        lg.warn('device %r is already active' % device_name)
        return True
    device_key_object.active = True
    device_key_object.save()
    lg.info('device %r was activated' % device_name)
    return True


def disable_device(device_name):
    validate_device_name(device_name)
    device_key_object = devices(device_name)
    if not device_key_object:
        raise Exception('device %r does not exist' % device_name)
    if instances(device_name):
        stop_device(device_name)
    if not device_key_object.active:
        lg.warn('device %r was not active' % device_name)
        return True
    device_key_object.active = False
    device_key_object.save()
    lg.info('device %r was deactivated' % device_name)
    return True


#------------------------------------------------------------------------------


def start_device(device_name, listening_callback=None, client_code_input_callback=None):
    global _Instances
    validate_device_name(device_name)
    device_key_object = devices(device_name)
    if not device_key_object:
        raise Exception('device %r does not exist' % device_name)
    if not device_key_object.active:
        raise Exception('device %r is not active' % device_name)
    inst = instances(device_name)
    if inst:
        if inst.state == 'CLOSED':
            _Instances.pop(device_name)
            del inst
        else:
            lg.warn('device %r was already started' % device_name)
            if listening_callback:
                reactor.callLater(0, listening_callback, True)  # @UndefinedVariable
            return inst
    if device_key_object.meta['routed']:
        if not driver.is_on('service_web_socket_communicator'):
            raise Exception('required service_web_socket_communicator() is not currently ON')
        inst = routed_web_socket.RoutedWebSocket(
            device_object=device_key_object,
            encrypt_auth_info_callback=encrypt_auth_info,
        )
    else:
        inst = encrypted_web_socket.EncryptedWebSocket(
            device_object=device_key_object,
            encrypt_auth_info_callback=encrypt_auth_info,
            host=device_key_object.meta.get('host') or 'localhost',
            port_number=device_key_object.meta['port_number'],
        )
    if _Debug:
        lg.args(_DebugLevel, device_name=device_name, instance=inst)
    _Instances[device_name] = inst
    inst.automat(
        'start',
        listening_callback=listening_callback,
        client_code_input_callback=client_code_input_callback,
    )
    return inst


def stop_device(device_name):
    global _Instances
    validate_device_name(device_name)
    if device_name not in _Instances:
        raise Exception('device %r was not started' % device_name)
    inst = _Instances[device_name]
    if _Debug:
        lg.args(_DebugLevel, device_name=device_name, instance=inst)
    inst.automat('stop')
    _Instances.pop(device_name)
    del inst
    return True


#------------------------------------------------------------------------------


def is_device_started(device_name):
    global _Instances
    validate_device_name(device_name)
    return device_name in _Instances


def is_device_enabled(device_name):
    validate_device_name(device_name)
    device_key_object = devices(device_name)
    if not device_key_object:
        raise Exception('device %r does not exist' % device_name)
    return device_key_object.active


#------------------------------------------------------------------------------


def reload_device(device_name):
    global _Devices
    if device_name not in _Devices:
        return False
    device_file_path = os.path.join(settings.DevicesDir(), device_name)
    _Devices[device_name].load(device_file_path)
    if _Debug:
        lg.args(_DebugLevel, device_name=device_name)
    return True


def load_devices():
    global _Devices
    for device_name in os.listdir(settings.DevicesDir()):
        device_file_path = os.path.join(settings.DevicesDir(), device_name)
        device_key_object = APIDevice()
        if not device_key_object.load(device_file_path):
            del device_key_object
            continue
        _Devices[device_name] = device_key_object
    if _Debug:
        lg.args(_DebugLevel, devices=len(_Devices))


def start_direct_devices():
    for device_name in devices():
        device_key_object = devices(device_name)
        if not device_key_object.active:
            continue
        if not device_key_object.meta['routed']:
            start_device(device_name)


def start_routed_devices():
    for device_name in devices():
        device_key_object = devices(device_name)
        if not device_key_object.active:
            continue
        if device_key_object.meta['routed']:
            start_device(device_name)


def stop_routed_devices():
    for device_name in devices():
        device_key_object = devices(device_name)
        if not device_key_object:
            continue
        if device_key_object.meta['routed']:
            if instances(device_name):
                stop_device(device_name)


def stop_devices():
    for device_name in devices():
        if instances(device_name):
            stop_device(device_name)


#------------------------------------------------------------------------------


def reset_authorization(device_name):
    if _Debug:
        lg.args(_DebugLevel, device_name=device_name)
    validate_device_name(device_name)
    device_key_object = devices(device_name)
    if not device_key_object:
        raise Exception('device %r does not exist' % device_name)
    if instances(device_name):
        raise Exception('not possible to reset authorization with started device, device must be stopped first')
    device_key_object.meta['auth_token'] = None
    device_key_object.meta['session_key'] = None
    if not device_key_object.save():
        return False
    return True


def request_authorization(device_name, client_public_key_text, client_code):
    if _Debug:
        lg.args(_DebugLevel, device_name=device_name)
    validate_device_name(device_name)
    device_key_object = devices(device_name)
    if not device_key_object:
        raise Exception('device %r does not exist' % device_name)
    if instances(device_name):
        raise Exception('not possible to request authorization with started device, device must be stopped first')
    if not client_public_key_text.startswith('ssh-rsa '):
        client_public_key_text = 'ssh-rsa ' + client_public_key_text
    try:
        client_key_object = rsa_key.RSAKey()
        client_key_object.fromString(client_public_key_text)
    except Exception as exc:
        raise Exception('failed reading public key: %s' % str(exc))
    if _Debug:
        lg.args(_DebugLevel, meta=device_key_object.meta)
    device_key_object.meta['auth_token'] = cipher.generate_secret_text(10)
    device_key_object.meta['session_key'] = strng.to_text(base64.b64encode(cipher.make_key()))
    device_key_object.meta['client_public_key'] = client_key_object.toPublicString()
    if not device_key_object.save():
        return None
    auth_info, signature = encrypt_auth_info(
        device_key_object=device_key_object,
        auth_token=device_key_object.meta['auth_token'],
        session_key=base64.b64decode(strng.to_bin(device_key_object.meta['session_key'])),
        client_public_key_object=client_key_object,
        client_code=client_code,
    )
    return {
        'auth_info': auth_info,
        'signature': signature,
        'server_public_key': device_key_object.toPublicString(),
    }


#------------------------------------------------------------------------------


def encrypt_auth_info(device_key_object, auth_token, session_key, client_public_key_object, client_code):
    session_key_text = strng.to_text(base64.b64encode(session_key))
    salted_payload = '{}#{}#{}#{}'.format(client_code, auth_token, session_key_text, cipher.generate_secret_text(32))
    encrypted_payload = base64.b64encode(client_public_key_object.encrypt(strng.to_bin(salted_payload)))
    hashed_payload = hashes.sha1(strng.to_bin(salted_payload))
    auth_info = strng.to_text(encrypted_payload)
    signature = strng.to_text(device_key_object.sign(hashed_payload))
    return auth_info, signature


#------------------------------------------------------------------------------


def do_process_incoming_message(device_object, json_data):
    global _AllAPIMethods
    global _APILogFileEnabled
    from bitdust.interface import api
    command = json_data.get('command')
    if command == 'api_call':
        method = json_data.get('method', None)
        kwargs = json_data.get('kwargs', {})
        call_id = json_data.get('call_id', None)

        if not method:
            lg.warn('api method name was not provided')
            return device_object.on_outgoing_message({
                'cmd': 'response',
                'type': 'api_call',
                'payload': {
                    'call_id': call_id,
                    'errors': ['api method name was not provided'],
                },
            })

        if method not in _AllAPIMethods:
            lg.warn('invalid api method name: %r' % method)
            return device_object.on_outgoing_message({
                'cmd': 'response',
                'type': 'api_call',
                'payload': {
                    'call_id': call_id,
                    'errors': ['invalid api method name'],
                },
            })

        if _Debug:
            lg.out(_DebugLevel, '*** %s  API WS IN  %s(%r)' % (call_id, method, kwargs))

        if _APILogFileEnabled:
            lg.out(0, '*** %s  WS IN %s %s(%r)' % (device_object.device_name, call_id, method, kwargs), log_name='api', showtime=True)

        func = getattr(api, method)
        try:
            response = func(**kwargs)
        except Exception as err:
            lg.err(f'{method}({kwargs}) : {err}')
            return device_object.on_outgoing_message({
                'cmd': 'response',
                'type': 'api_call',
                'payload': {
                    'call_id': call_id,
                    'errors': [str(err)],
                },
            })

        if isinstance(response, Deferred):

            def _cb(r):
                return device_object.on_outgoing_message({
                    'cmd': 'response',
                    'type': 'api_call',
                    'payload': {
                        'call_id': call_id,
                        'response': r,
                    },
                })

            def _eb(err):
                err_msg = err.getErrorMessage() if isinstance(err, Failure) else str(err)
                return device_object.on_outgoing_message({
                    'cmd': 'response',
                    'type': 'api_call',
                    'payload': {
                        'call_id': call_id,
                        'errors': [err_msg],
                    },
                })

            response.addCallback(_cb)
            response.addErrback(_eb)
            return True

        return device_object.on_outgoing_message({
            'cmd': 'response',
            'type': 'api_call',
            'payload': {
                'call_id': call_id,
                'response': response,
            },
        })

    return False


#------------------------------------------------------------------------------


def on_event(evt):
    push({
        'cmd': 'push',
        'type': 'event',
        'payload': {
            'event_id': evt.event_id,
            'data': evt.data,
        },
    })


def on_stream_message(message_json):
    push({
        'cmd': 'push',
        'type': 'stream_message',
        'payload': message_json,
    })


def on_online_status_changed(status_info):
    push({
        'cmd': 'push',
        'type': 'online_status',
        'payload': status_info,
    })


def on_model_changed(snapshot_object):
    push({
        'cmd': 'push',
        'type': 'model',
        'payload': snapshot_object.to_json(),
    })


def on_device_client_code_input_received(device_name, client_code):
    validate_device_name(device_name)
    inst = instances(device_name)
    if not inst:
        raise Exception('device %r was not started' % device_name)
    inst.on_client_code_input_received(client_code)


#------------------------------------------------------------------------------


def push(json_data):
    global _APILogFileEnabled
    pushed = False
    for inst in instances().values():
        if inst.on_outgoing_message(json_data):
            pushed = True
            if _APILogFileEnabled:
                lg.out(0, '*** WS PUSH  %s : %r' % (inst.device_name, json_data), log_name='api', showtime=True)
    if not pushed:
        if _APILogFileEnabled:
            lg.warn('*** WS PUSH FAILED : %r' % json_data, log_name='api')


#------------------------------------------------------------------------------

if __name__ == '__main__':
    settings.init()
    lg.set_debug_level(24)
    automat.init()
    automat.LifeBegins(lg.when_life_begins())
    automat.SetGlobalLogEvents(True)
    automat.SetGlobalLogTransitions(True)
    automat.SetExceptionsHandler(lg.exc)
    automat.SetLogOutputHandler(lambda debug_level, message: lg.out(debug_level, message))
    init()
    # add_device('test123', 12345)
    reactor.run()  # @UndefinedVariable
