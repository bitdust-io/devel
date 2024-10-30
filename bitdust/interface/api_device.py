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

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

import os

#------------------------------------------------------------------------------

from twisted.internet.defer import Deferred
from twisted.python.failure import Failure

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.lib import jsn

from bitdust.main import settings

from bitdust.system import local_fs

from bitdust.crypt import rsa_key

from bitdust.services import driver

from bitdust.interface import encrypted_web_socket
from bitdust.interface import routed_web_socket

#------------------------------------------------------------------------------

_Devices = {}
_Listeners = {}
_Transports = {}
_Instances = {}
_AllAPIMethods = []

#------------------------------------------------------------------------------


def init():
    global _AllAPIMethods
    from bitdust.interface import api
    encrypted_web_socket.SetIncomingAPIMessageCallback(do_process_incoming_message)
    _AllAPIMethods = set(dir(api))
    _AllAPIMethods.difference_update(
        [
            # TODO: keep that list up to date when changing the api
            'on_api_result_prepared',
            'Deferred',
            'ERROR',
            'Failure',
            'OK',
            'RESULT',
            '_Debug',
            '_DebugLevel',
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
            'event_listen',
            'message_receive',
        ]
    )
    if _Debug:
        lg.out(_DebugLevel, 'api_device.init  with %d API methods' % len(_AllAPIMethods))
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


class APIDevice(rsa_key.RSAKey):

    def save(self):
        device_file_path = os.path.join(settings.DevicesDir(), self.label)
        device_info_dict = self.toDict(include_private=True)
        device_info_raw = jsn.dumps(device_info_dict, indent=2, separators=(',', ':'))
        if not local_fs.WriteTextFile(device_file_path, device_info_raw):
            lg.err('failed saving device info %r to %r' % (self.label, device_file_path))
            return False
        if _Debug:
            lg.args(_DebugLevel, device_name=self.label, key=self)
        return True

    def load(self, device_file_path):
        device_info_raw = local_fs.ReadTextFile(device_file_path)
        if not device_info_raw:
            lg.warn('failed reading device file %r' % device_file_path)
            return False
        device_info_dict = jsn.loads_text(device_info_raw.strip())
        try:
            self.fromDict(device_info_dict)
        except:
            lg.exc()
            return False
        if _Debug:
            lg.args(_DebugLevel, device_name=self.label, key=self)
        return True


#------------------------------------------------------------------------------


def add_encrypted_device(device_name, port_number, key_size=4096):
    global _Devices
    if device_name in _Devices:
        raise Exception('device %r already exist' % device_name)
    if _Debug:
        lg.args(_DebugLevel, device_name=device_name)
    device_key_object = APIDevice()
    device_key_object.generate(key_size)
    device_key_object.label = device_name
    device_key_object.active = True
    device_key_object.meta['routed'] = False
    device_key_object.meta['port_number'] = port_number
    device_key_object.meta['auth_token'] = None
    device_key_object.meta['session_key'] = None
    device_key_object.meta['client_public_key'] = None
    if not device_key_object.save():
        return False
    _Devices[device_name] = device_key_object
    return True


def add_routed_device(device_name, port_number, key_size=4096):
    global _Devices
    if device_name in _Devices:
        raise Exception('device %r already exist' % device_name)
    if not driver.is_on('service_nodes_lookup'):
        raise Exception('required service_nodes_lookup() is not currently ON')
    if _Debug:
        lg.args(_DebugLevel, device_name=device_name)
    device_key_object = APIDevice()
    device_key_object.generate(key_size)
    device_key_object.label = device_name
    device_key_object.active = True
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
    device_key_object.save()
    lg.info('device %r was activated' % device_name)
    return True


def disable_device(device_name):
    device_key_object = devices(device_name)
    if not device_key_object:
        raise Exception('device %r does not exist' % device_name)
    if instances(device_name):
        stop_device(device_name)
    if not device_key_object.active:
        lg.warn('device %r is not active' % device_name)
        return False
    device_key_object.active = False
    device_key_object.save()
    lg.info('device %r was deactivated' % device_name)
    return True


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
    if device_key_object.meta['routed']:
        if not driver.is_on('service_nodes_lookup'):
            raise Exception('required service_nodes_lookup() is not currently ON')
        inst = routed_web_socket.RoutedWebSocket()
    else:
        inst = encrypted_web_socket.EncryptedWebSocket(port_number=device_key_object.meta['port_number'])
    if _Debug:
        lg.args(_DebugLevel, device_name=device_name, instance=inst)
    _Instances[device_name] = inst
    inst.automat('start', device_object=device_key_object)
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
        device_file_path = os.path.join(settings.DevicesDir(), device_name)
        device_key_object = APIDevice()
        if not device_key_object.load(device_file_path):
            del device_key_object
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


def stop_devices():
    for device_name in devices():
        device_key_object = devices(device_name)
        if not device_key_object.active:
            continue
        stop_device(device_name)


#------------------------------------------------------------------------------


def do_process_incoming_message(device_object, json_data):
    global _AllAPIMethods
    from bitdust.interface import api
    command = json_data.get('command')
    if command == 'api_call':
        method = json_data.get('method', None)
        kwargs = json_data.get('kwargs', {})
        call_id = json_data.get('call_id', None)

        if not method:
            lg.warn('api method name was not provided')
            return device_object.on_outgoing_message({
                'type': 'api_call',
                'payload': {
                    'call_id': call_id,
                    'errors': ['api method name was not provided'],
                },
            })

        if method not in _AllAPIMethods:
            lg.warn('invalid api method name: %r' % method)
            return device_object.on_outgoing_message({
                'type': 'api_call',
                'payload': {
                    'call_id': call_id,
                    'errors': ['invalid api method name'],
                },
            })

        if _Debug:
            lg.out(_DebugLevel, '*** %s  API WS IN  %s(%r)' % (call_id, method, kwargs))

        # if _APILogFileEnabled:
        #     lg.out(0, '*** %s  WS IN  %s(%r)' % (call_id, method, kwargs), log_name='api', showtime=True)

        func = getattr(api, method)
        try:
            response = func(**kwargs)
        except Exception as err:
            lg.err(f'{method}({kwargs}) : {err}')
            return device_object.on_outgoing_message({
                'type': 'api_call',
                'payload': {
                    'call_id': call_id,
                    'errors': [str(err)],
                },
            })

        if isinstance(response, Deferred):

            def _cb(r):
                return device_object.on_outgoing_message({
                    'type': 'api_call',
                    'payload': {
                        'call_id': call_id,
                        'response': r,
                    },
                })

            def _eb(err):
                err_msg = err.getErrorMessage() if isinstance(err, Failure) else str(err)
                return device_object.on_outgoing_message({
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
            'type': 'api_call',
            'payload': {
                'call_id': call_id,
                'response': response,
            },
        })

    return False


#------------------------------------------------------------------------------


def on_event(evt):
    for inst in instances().values():
        inst.on_outgoing_message({
            'type': 'event',
            'payload': {
                'event_id': evt.event_id,
                'data': evt.data,
            },
        })


def on_stream_message(message_json):
    for inst in instances().values():
        inst.on_outgoing_message({
            'type': 'stream_message',
            'payload': message_json,
        })


def on_online_status_changed(status_info):
    for inst in instances().values():
        inst.on_outgoing_message({
            'type': 'online_status',
            'payload': status_info,
        })


def on_model_changed(snapshot_object):
    for inst in instances().values():
        inst.on_outgoing_message({
            'type': 'model',
            'payload': snapshot_object.to_json(),
        })


#------------------------------------------------------------------------------

if __name__ == '__main__':
    from twisted.internet import reactor
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
