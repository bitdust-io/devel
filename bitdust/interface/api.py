#!/usr/bin/python
# api.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (api.py) is part of BitDust Software.
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
.. module:: api.

Here is a bunch of methods to interact with BitDust software.
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

_APILogFileEnabled = None

#------------------------------------------------------------------------------

import os
import sys
import time
import gc

from twisted.internet import reactor  # @UnresolvedImport
from twisted.internet.defer import Deferred  # @UnresolvedImport
from twisted.python.failure import Failure  # @UnresolvedImport

#------------------------------------------------------------------------------

from bitdust.lib import strng
from bitdust.lib import jsn

from bitdust.logs import lg

from bitdust.services import driver

from bitdust.main import config

#------------------------------------------------------------------------------


def on_api_result_prepared(result):
    # TODO
    return result


#------------------------------------------------------------------------------


def OK(result='', message=None, status='OK', **kwargs):
    global _APILogFileEnabled
    o = {
        'status': status,
    }
    if result:
        if isinstance(result, dict):
            o['result'] = result
        else:
            o['result'] = result if isinstance(result, list) else [
                result,
            ]
    if message is not None:
        o['message'] = message
    o = on_api_result_prepared(o)
    sample = ''
    if _Debug or _APILogFileEnabled:
        try:
            sample = jsn.dumps(o, ensure_ascii=True, sort_keys=True)
        except:
            lg.exc()
            sample = strng.to_text(o, errors='ignore')
    api_method = kwargs.get('api_method', None)
    if not api_method:
        api_method = sys._getframe().f_back.f_code.co_name
        if api_method.count('lambda') or api_method.startswith('_'):
            api_method = sys._getframe(1).f_back.f_code.co_name
    if _Debug:
        if api_method not in [
            'process_health',
            'network_connected',
        ] or _DebugLevel > 10:
            lg.out(_DebugLevel, 'api.%s return OK(%s)' % (api_method, sample[:80]))
    if _APILogFileEnabled is None:
        _APILogFileEnabled = config.conf().getBool('logs/api-enabled')
    if _APILogFileEnabled:
        lg.out(
            0,
            'api.%s return OK(%s)\n' % (
                api_method,
                sample,
            ),
            log_name='api',
            showtime=True,
        )
    return o


def RESULT(result=[], message=None, status='OK', errors=None, source=None, extra_fields=None, **kwargs):
    global _APILogFileEnabled
    o = {}
    if source is not None:
        o.update(source)
    o.update({'status': status, 'result': result})
    if message is not None:
        o['message'] = message
    if errors is not None:
        o['errors'] = errors
    if extra_fields is not None:
        o.update(extra_fields)
    o = on_api_result_prepared(o)
    sample = ''
    if _Debug or _APILogFileEnabled:
        try:
            sample = jsn.dumps(o, ensure_ascii=True, sort_keys=True)
        except:
            lg.exc()
            sample = strng.to_text(o, errors='ignore')
    api_method = kwargs.get('api_method', None)
    if not api_method:
        api_method = sys._getframe().f_back.f_code.co_name
        if api_method.count('lambda') or api_method.startswith('_'):
            api_method = sys._getframe(1).f_back.f_code.co_name
    if _Debug:
        lg.out(_DebugLevel, 'api.%s return RESULT(%s)' % (api_method, sample[:150]))
    if _APILogFileEnabled is None:
        _APILogFileEnabled = config.conf().getBool('logs/api-enabled')
    if _APILogFileEnabled:
        lg.out(
            0,
            'api.%s return RESULT(%s)\n' % (
                api_method,
                sample,
            ),
            log_name='api',
            showtime=True,
        )
    return o


def ERROR(errors=[], message=None, status='ERROR', reason=None, details=None, **kwargs):
    global _APILogFileEnabled
    if not isinstance(errors, list):
        errors = [
            errors,
        ]
    for i in range(len(errors)):
        if isinstance(errors[i], Failure):
            try:
                errors[i] = errors[i].getErrorMessage()
            except:
                errors[i] = 'unknown failure'
        else:
            try:
                errors[i] = strng.to_text(errors[i])
            except:
                errors[i] = 'unknown exception'
    o = {
        'status': status,
        'errors': errors,
    }
    if message is not None:
        o['message'] = message
    if reason is not None:
        o['reason'] = reason
    if details is not None:
        o.update(details)
    o = on_api_result_prepared(o)
    sample = ''
    if _Debug or _APILogFileEnabled:
        try:
            sample = jsn.dumps(o, ensure_ascii=True, sort_keys=True)
        except:
            lg.exc()
            sample = strng.to_text(o, errors='ignore')
    api_method = kwargs.get('api_method', None)
    if not api_method:
        api_method = sys._getframe().f_back.f_code.co_name
        if api_method.count('lambda') or api_method.startswith('_'):
            api_method = sys._getframe(1).f_back.f_code.co_name
    if _Debug:
        lg.out(_DebugLevel, 'api.%s return ERROR(%s)' % (api_method, sample[:150]))
    if _APILogFileEnabled is None:
        _APILogFileEnabled = config.conf().getBool('logs/api-enabled')
    if _APILogFileEnabled:
        lg.out(
            0,
            'api.%s return ERROR(%s)\n' % (
                api_method,
                sample,
            ),
            log_name='api',
            showtime=True,
        )
    return o


#------------------------------------------------------------------------------


def enable_model_listener(model_name: str, request_all: bool = False):
    """
    When using WebSocket API interface you can get advantage of real-time data streaming and receive additional information when certain things
    are changing in the engine. Any updates to those instances will be automatically populated to the WebSocket connection.

    For each model this method suppose to be called only once to switch on the live streaming for that data type.

    When `request_all=True` the engine will immediately populate one time all of the data objects of given type to the WebSocket.
    This way client will be able to catch and store everything on the front-side and after that use only live streaming to receive the updates for given data model.

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "enable_model_listener", "kwargs": {"model_name": "key"} }');
    """
    if _Debug:
        lg.args(_DebugLevel, m=model_name, request_all=request_all)
    from bitdust.main import listeners
    from bitdust.interface import api_web_socket
    from bitdust.interface import api_device
    listeners.add_listener(api_web_socket.on_model_changed, model_name)
    listeners.add_listener(api_device.on_model_changed, model_name)
    if request_all:
        return request_model_data(model_name)
    return OK()


def disable_model_listener(model_name: str):
    """
    Stop live streaming of all updates regarding given data type to the WebSocket connection.

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "disable_model_listener", "kwargs": {"model_name": "key"} }');
    """
    if _Debug:
        lg.args(_DebugLevel, m=model_name)
    from bitdust.main import listeners
    from bitdust.interface import api_web_socket
    from bitdust.interface import api_device
    if model_name == 'key':
        listeners.populate_later('key', stop=True)
    elif model_name == 'conversation':
        listeners.populate_later('conversation', stop=True)
    elif model_name == 'message':
        listeners.populate_later('message', stop=True)
    elif model_name == 'correspondent':
        listeners.populate_later('correspondent', stop=True)
    elif model_name == 'online_status':
        listeners.populate_later('online_status', stop=True)
    elif model_name == 'private_file':
        listeners.populate_later('private_file', stop=True)
    elif model_name == 'shared_file':
        listeners.populate_later('shared_file', stop=True)
    elif model_name == 'remote_version':
        listeners.populate_later('remote_version', stop=True)
    elif model_name == 'shared_location':
        listeners.populate_later('shared_location', stop=True)
    listeners.remove_listener(api_web_socket.on_model_changed, model_name)
    listeners.remove_listener(api_device.on_model_changed, model_name)
    return OK()


def request_model_data(model_name: str, query_details: dict = None):
    """
    The engine will try to immediately populate all data related to the given model type to the WebSocket, one time only.

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "request_model_data", "kwargs": {"model_name": "key"} }');
    """
    if _Debug:
        lg.args(_DebugLevel, m=model_name, query_details=query_details)
    from bitdust.main import listeners
    if model_name == 'service':
        driver.populate_services()
    elif model_name == 'key':
        if driver.is_on('service_keys_registry'):
            from bitdust.crypt import my_keys
            my_keys.populate_keys()
        else:
            listeners.populate_later('key')
    elif model_name == 'conversation':
        if driver.is_on('service_message_history'):
            from bitdust.chat import message_database
            message_database.populate_conversations()
        else:
            listeners.populate_later('conversation')
    elif model_name == 'message':
        if driver.is_on('service_message_history'):
            from bitdust.chat import message_database  # @Reimport
            message_database.populate_messages()
        else:
            listeners.populate_later('message')
    elif model_name == 'correspondent':
        if driver.is_on('service_identity_propagate'):
            from bitdust.contacts import contactsdb
            contactsdb.populate_correspondents()
        else:
            listeners.populate_later('correspondent')
    elif model_name == 'online_status':
        if driver.is_on('service_p2p_hookups'):
            from bitdust.p2p import online_status
            online_status.populate_online_statuses()
        else:
            listeners.populate_later('online_status')
    elif model_name == 'private_file':
        if driver.is_on('service_my_data'):
            from bitdust.storage import backup_fs
            backup_fs.populate_private_files()
        else:
            listeners.populate_later('private_file')
    elif model_name == 'shared_file':
        if driver.is_on('service_shared_data'):
            from bitdust.storage import backup_fs  # @Reimport
            backup_fs.populate_shared_files(key_id=(query_details or {}).get('key_id'))
        else:
            listeners.populate_later('shared_file')
    elif model_name == 'remote_version':
        if driver.is_on('service_backups'):
            from bitdust.storage import backup_matrix
            backup_matrix.populate_remote_versions(
                key_id=(query_details or {}).get('key_id'),
                remote_path=(query_details or {}).get('remote_path'),
                backup_id=(query_details or {}).get('backup_id'),
            )
        else:
            listeners.populate_later('remote_version')
    elif model_name == 'shared_location':
        if driver.is_on('service_shared_data'):
            from bitdust.access import shared_access_coordinator
            shared_access_coordinator.populate_shares()
        else:
            listeners.populate_later('shared_location')
    return OK()


#------------------------------------------------------------------------------


def chunk_read(path: str, offset: int, max_size: int = 1024*32):
    """
    Requests chunk of data from a local file. Used to download a file via WebSocket stream.

    Binary data is encoded to a text string using "latin1" encoding.

    The "path" must be pointing to a location inside of the "~/.bitdust/temp/" folder.

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "chunk_read", "kwargs": {"path": "/tmp/cat.png", "offset": 1000, "max_size": 8192} }');
    """
    from bitdust.stream import chunk
    from bitdust.system import tmpfile
    if not path.startswith(tmpfile.base_dir()):
        return ERROR('wrong path location provided')
    try:
        raw_data = chunk.data_read(file_path=path, offset=offset, max_size=max_size, to_text=True)
    except Exception as exc:
        return ERROR(exc)
    if not raw_data:
        return OK({'chunk': '', 'completed': True})
    return OK({'chunk': raw_data})


def chunk_write(data: str, path: str = None):
    """
    Writes chunk of data to a local file. Used to upload a file via WebSocket stream.

    Text data is decoded to a binary string using "latin1" encoding.

    When "path" argument is empty a new file will be opened in a temporarily location,
    response will include full local path to the file.

    When the "path" is present it must be pointing to a location inside of the "~/.bitdust/temp/" folder.

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "chunk_write", "kwargs": {"path": "/tmp/cat.png", "data": "ABCD1234"} }');
    """
    from bitdust.stream import chunk
    from bitdust.system import tmpfile
    file_path = path
    if path:
        if not path.startswith(tmpfile.base_dir()):
            return ERROR('wrong path location provided')
    else:
        _, file_path = tmpfile.make('upload', close_fd=True)
    try:
        chunk.data_write(file_path=file_path, data=data, from_text=True)
    except Exception as exc:
        return ERROR(exc)
    if not path:
        return OK({'path': file_path})
    return OK()


#------------------------------------------------------------------------------


def process_stop(instant: bool = True):
    """
    Stop the main process immediately.

    ###### HTTP
        curl -X GET 'localhost:8180/process/stop/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "process_stop", "kwargs": {} }');
    """
    if _Debug:
        lg.out(_DebugLevel, 'api.process_stop sending event "stop" to the shutdowner() machine')
    from bitdust.main import shutdowner
    if not shutdowner.A():
        return ERROR('application shutdown failed')
    if instant:
        reactor.callLater(0, shutdowner.A, 'stop', 'exit')  # @UndefinedVariable
        return OK()
    ret = Deferred()
    reactor.callLater(0, ret.callback, OK(api_method='process_stop'))  # @UndefinedVariable
    reactor.callLater(0.5, shutdowner.A, 'stop', 'exit')  # @UndefinedVariable
    return ret


def process_restart():
    """
    Restart the main process.

    ###### HTTP
        curl -X GET 'localhost:8180/process/restart/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "process_restart", "kwargs": {} }');
    """
    from bitdust.main import shutdowner
    if _Debug:
        lg.out(_DebugLevel, 'api.process_restart sending event "stop" to the shutdowner() machine')
    reactor.callLater(0.1, shutdowner.A, 'stop', 'restart')  # @UndefinedVariable
    return OK({
        'restarted': True,
    })


def process_health():
    """
    Returns positive response if engine process is running. This method suppose to be used for health checks.

    ###### HTTP
        curl -X GET 'localhost:8180/process/health/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "process_health", "kwargs": {} }');
    """
    return OK()


def process_info():
    """
    Returns overall information about current process. This method can be used for live monitoring and statistics.

    ###### HTTP
        curl -X GET 'localhost:8180/process/info/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "process_info", "kwargs": {} }');
    """
    from bitdust.contacts import identitydb
    from bitdust.contacts import contactsdb
    from bitdust.automats import automat
    from bitdust.userid import my_id
    result = {
        'config': {
            'options': len(config.conf().cache()),
        },
        'identity': {
            'ready': my_id.isLocalIdentityReady(),
            'cache': len(identitydb.cache()),
            'cache_ids': len(identitydb.cache_ids()),
            'cache_contacts': len(identitydb.cache_contacts()),
        },
        'contact': {
            'active': 0,
            'correspondents': contactsdb.num_correspondents(),
            'customers': contactsdb.num_customers(),
            'suppliers_hired': contactsdb.num_suppliers(),
            'suppliers_total': contactsdb.total_suppliers(),
            'suppliers_active': 0,
            'customer_assistants': 0,
        },
        'service': {
            'active': len(driver.services()),
        },
        'key': {
            'registered': 0,
        },
        'file': {
            'items': 0,
            'files': 0,
            'files_size': 0,
            'folders': 0,
            'folders_size': 0,
            'backups_size': 0,
            'customers': 0,
        },
        'dht': {
            'layers': {},
            'bytes_out': 0,
            'bytes_in': 0,
        },
        'share': {
            'active': 0,
        },
        'group': {
            'active': 0,
        },
        'network': {
            'protocols': 0,
            'packets_out': 0,
            'packets_out_total': 0,
            'packets_in': 0,
            'packets_in_total': 0,
        },
        'stream': {
            'queues': 0,
            'consumers': 0,
            'producers': 0,
            'keepers': 0,
            'peddlers': 0,
            'supplier_queues': 0,
        },
        'automats': {
            'active': len(automat.objects()),
        },
    }
    if driver.is_on('service_customer'):
        from bitdust.customer import supplier_connector
        result['contact']['suppliers_active'] = supplier_connector.total_connectors()
    if driver.is_on('service_customer_support'):
        from bitdust.supplier import customer_assistant
        result['contact']['customer_assistants'] = len(customer_assistant.assistants())
    if driver.is_on('service_identity_propagate'):
        from bitdust.p2p import online_status
        result['contact']['active'] = len(online_status.online_statuses())
    if driver.is_on('service_keys_registry'):
        from bitdust.crypt import my_keys
        result['key'] = {
            'registered': len(my_keys.known_keys()),
        }
    if driver.is_on('service_entangled_dht'):
        from bitdust.dht import dht_service
        result['dht']['bytes_out'] = dht_service.node().bytes_out
        result['dht']['bytes_in'] = dht_service.node().bytes_in
        for layer_id in dht_service.node().active_layers:
            result['dht']['layers'][layer_id] = {
                'cache': len(dht_service.cache().get(layer_id, [])),
                'packets_in': dht_service.node().packets_in.get(layer_id, 0),
                'packets_out': dht_service.node().packets_out.get(layer_id, 0),
            }
    if driver.is_on('service_backup_db'):
        from bitdust.storage import backup_fs
        v = backup_fs.total_stats()
        result['file'] = {
            'items': v['items'],
            'files': v['files'],
            'folders': v['folders'],
            'files_size': v['size_files'],
            'folders_size': v['size_folders'],
            'backups_size': v['size_backups'],
            'customers': len(backup_fs.known_customers()),
        }
    if driver.is_on('service_shared_data'):
        from bitdust.access import shared_access_coordinator
        result['share'] = {
            'active': len(shared_access_coordinator.list_active_shares()),
        }
    if driver.is_on('service_private_groups'):
        from bitdust.access import group_participant
        result['group'] = {
            'active': len(group_participant.list_active_group_participants()),
        }
    if driver.is_on('service_gateway'):
        from bitdust.transport import gateway
        from bitdust.transport import packet_in
        from bitdust.transport import packet_out
        result['network']['packets_out'] = len(packet_out.queue())
        result['network']['packets_out_total'] = packet_out.get_packets_counter()
        result['network']['packets_in'] = len(packet_in.inbox_items())
        result['network']['packets_in_total'] = packet_in.get_packets_counter()
        result['network']['protocols'] = len(gateway.transports())
    if driver.is_on('service_p2p_notifications'):
        from bitdust.stream import p2p_queue
        result['stream']['queues'] = len(p2p_queue.queue())
        result['stream']['consumers'] = len(p2p_queue.consumer())
        result['stream']['producers'] = len(p2p_queue.producer())
    if driver.is_on('service_joint_postman'):
        from bitdust.stream import postman
        result['stream']['streams'] = len(postman.streams())
    if driver.is_on('service_data_motion'):
        from bitdust.stream import io_throttle
        result['stream']['supplier_queues'] = len(io_throttle.throttle().ListSupplierQueues())
    return OK(result)


def process_debug():
    """
    Execute a breakpoint inside the main thread and start Python shell using standard `pdb.set_trace()` debugger method.

    This is only useful if you already have executed the BitDust engine manually via shell console and would like
    to interrupt it and investigate things.

    This call will block the main process and it will stop responding to any API calls until pdb shell is released.

    ###### HTTP
        curl -X GET 'localhost:8180/process/debug/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "process_debug", "kwargs": {} }');
    """
    import pdb
    pdb.set_trace()
    return OK()


#------------------------------------------------------------------------------


def devices_list(sort: bool = False):
    """
    List all registered configurations of your configured API devices.

    API Device provide remote access to BitDust node running on that machine.

    Remote device (often mobile phone, tablet, etc.) acts as a thin-client and allows you to access and manage
    this BitDust node via secure web socket connection. To be able to access this BitDust node from your mobile phone,
    you first need to configure and authorize API device.

    ###### HTTP
        curl -X GET 'localhost:8180/device/list/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "devices_list", "kwargs": {} }');
    """
    from bitdust.interface import api_device
    results = []
    for device_name, device_object in api_device.devices().items():
        result = device_object.toDict()
        result['name'] = result.pop('label')
        result['instance'] = None
        result['url'] = None
        result.pop('body', None)
        result.pop('local_key_id', None)
        device_instance = api_device.instances(device_name)
        if device_instance:
            result['instance'] = device_instance.to_json()
            result['instance'].pop('device_name', None)
            result['url'] = result['instance'].pop('url', None)
        results.append(result)
    if sort:
        results = sorted(results, key=lambda i: i['label'])
    return RESULT(results)


def device_info(name: str):
    """
    Returns detailed info about given API device.

    ###### HTTP
        curl -X GET 'localhost:8180/device/info/v1?name=my_iPhone_12'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "device_info", "kwargs": {"name": "my_iPhone_12"} }');
    """
    from bitdust.interface import api_device
    device_object = api_device.devices(name)
    if not device_object:
        return ERROR('device %r does not exist' % name)
    device_instance = api_device.instances(name)
    result = device_object.toDict()
    result['name'] = result.pop('label')
    result['url'] = None
    result['instance'] = None
    result.pop('body', None)
    result.pop('local_key_id', None)
    if not device_instance:
        return OK(result)
    result['instance'] = device_instance.to_json()
    result['instance'].pop('device_name', None)
    result['url'] = result['instance'].pop('url', None)
    return OK(result)


def device_add(name: str, routed: bool = False, activate: bool = True, wait_listening: bool = False, web_socket_host: str = 'localhost', web_socket_port: int = None, key_size: int = None):
    """
    Register a new API device configuration to be able to access this BitDust node remotely.

    The `name` parameter is a user-specified local name to be used to identify new API device.
    You can use ASCII characters, numbers and underscore.

    When parameter `routed` is set to `true` new API device configuration will be using
    intermediate BitDust nodes to route encrypted web socket traffic from your client-device to the BitDust node.

    Such setup is especially useful to connect your pair your mobile phone to a PC running BitDust node at home.
    Routed traffic is end-to-end encrypted and intermediate BitDust nodes have no way to read your private data.

    The `web_socket_port` parameter from other side is only used in non-routed setup. In that case you are connecting
    from your mobile phone directly to the opened web socket of the running BitDust node. You have to have a static
    publicly-accessible IP address and opened port on your machine in order to make this working.

    Such setup is more suitable when you are hosting your BitDust node on the cloud-server and want to access it from
    your mobile device, laptop or home PC.

    If you pass `activate=true`, new device will be activated and started accepting incoming connections right away.

    ###### HTTP
        curl -X POST 'localhost:8180/device/add/v1' -d '{"name": "my_iPhone_12", "routed": true}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "device_add", "kwargs": {"name": "my_iPhone_12", "routed": true} }');
    """
    from bitdust.main import settings
    from bitdust.interface import api_device
    if not key_size:
        key_size = settings.getPrivateKeySize()
    if _Debug:
        lg.args(_DebugLevel, name=name, routed=routed, activate=activate, web_socket_port=web_socket_port, key_size=key_size)
    try:
        if routed in ('true', 'True', True, 1, '1', 'yes', 'YES'):
            if not driver.is_on('service_web_socket_communicator'):
                return ERROR('required service_web_socket_communicator() is not currently ON')
            ret = api_device.add_routed_device(device_name=name, key_size=key_size)
        else:
            ret = api_device.add_encrypted_device(device_name=name, host=web_socket_host, port_number=web_socket_port, key_size=key_size)
    except Exception as exc:
        return ERROR(exc)
    if not ret:
        return ERROR('failed to created device')
    if activate not in ('true', 'True', True, 1, '1', 'yes', 'YES'):
        return device_info(name)
    return device_start(name, wait_listening=(wait_listening in ('true', 'True', True, 1, '1', 'yes', 'YES')))


def device_start(name: str, wait_listening: bool = False):
    """
    Activates given API device and start accepting incoming connections.

    ###### HTTP
        curl -X POST 'localhost:8180/device/start/v1' -d '{"name": "my_iPhone_12"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "device_start", "kwargs": {"name": "my_iPhone_12"} }');
    """
    from bitdust.interface import api_device
    if _Debug:
        lg.args(_DebugLevel, name=name)
    try:
        api_device.enable_device(device_name=name)
    except Exception as exc:
        return ERROR(exc)
    if not wait_listening:
        try:
            api_device.start_device(device_name=name)
        except Exception as exc:
            return ERROR(exc)
        return device_info(name)
    ret = Deferred()

    def _on_listening_started(success):
        if not success:
            ret.callback(ERROR('device configuration failed', api_method='device_start'))
            return
        ret.callback(device_info(name))

    try:
        api_device.start_device(device_name=name, listening_callback=_on_listening_started)
    except Exception as exc:
        return ERROR(exc)
    return ret


def device_authorization_request(name: str, client_public_key: str, client_code: str):
    """
    This is another way to authorize a remote device configuration.

    The `client_public_key` and `client_code` are generated on the remote device.
    Result data from that call needs to be decrypted and processed on the remote device to complete authorisation procedure.

    This makes possible to authorize a remote device without entering the client and server 4 digits codes.

    ###### HTTP
        curl -X POST 'localhost:8180/device/authorization/request/v1' -d '{"name": "my_iPhone_12", "client_public_key": "AAAAB3Nza...", "client_code": "1234"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "device_authorization_request", "kwargs": {"name": "my_iPhone_12", "client_public_key": "AAAAB3Nza...", "client_code": "1234"} }');
    """
    from bitdust.interface import api_device
    if _Debug:
        lg.args(_DebugLevel, name=name)
    try:
        result = api_device.request_authorization(
            device_name=name,
            client_public_key_text=client_public_key,
            client_code=client_code,
        )
    except Exception as exc:
        return ERROR(exc)
    return OK(result)


def device_authorization_generate(name: str, key_size: int = 2048):
    """
    Generates private key and all required info to authorize a device configuration.

    This information must be securely copied to the target remote device and added to the web socket client.

    ###### HTTP
        curl -X POST 'localhost:8180/device/authorization/generate/v1' -d '{"name": "my_iPhone_12", "key_size": 4096}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "device_authorization_generate", "kwargs": {"name": "my_iPhone_12", "key_size": 4096} }');
    """
    from bitdust.interface import api_device
    from bitdust.crypt import rsa_key
    from bitdust.crypt import cipher
    if _Debug:
        lg.args(_DebugLevel, name=name)
    client_key_object = rsa_key.RSAKey(label=f'device_client_key_{name}')
    client_key_object.generate(key_size)
    client_code = cipher.generate_digits(4, as_text=True)
    try:
        result = api_device.request_authorization(
            device_name=name,
            client_public_key_text=client_key_object.toPublicString(),
            client_code=client_code,
        )
    except Exception as exc:
        return ERROR(exc)
    result['client_private_key'] = client_key_object.toDict(include_private=True)
    result['client_code'] = client_code
    return OK(result)


def device_authorization_reset(name: str, start: bool = True, wait_listening: bool = False):
    """
    To be called when given device needs to be authorized again.

    ###### HTTP
        curl -X POST 'localhost:8180/device/authorization/reset/v1' -d '{"name": "my_iPhone_12"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "device_authorization_reset", "kwargs": {"name": "my_iPhone_12"} }');
    """
    from bitdust.interface import api_device
    if _Debug:
        lg.args(_DebugLevel, name=name)
    try:
        api_device.reset_authorization(device_name=name)
    except Exception as exc:
        return ERROR(exc)
    if not start:
        return OK()
    return device_start(name, wait_listening=wait_listening)


def device_authorization_client_code(name: str, client_code: str):
    """
    Must be called during authorization procedure to provide client code entered by the user manually.

    ###### HTTP
        curl -X POST 'localhost:8180/device/authorization/client_code/v1' -d '{"name": "my_iPhone_12", "client_code": "1234"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "device_authorization_client_code", "kwargs": {"name": "my_iPhone_12", "client_code": "1234"} }');
    """
    from bitdust.interface import api_device
    if _Debug:
        lg.args(_DebugLevel, name=name, client_code=client_code)
    try:
        api_device.on_device_client_code_input_received(device_name=name, client_code=client_code)
    except Exception as exc:
        return ERROR(exc)
    return OK()


def device_stop(name: str):
    """
    This will stop accepting incoming connections from given API device and deactivate it.

    Stored configuration will not be removed and the device can be started again later.

    ###### HTTP
        curl -X POST 'localhost:8180/device/stop/v1 -d '{"name": "my_iPhone_12"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "device_stop", "kwargs": {"name": "my_iPhone_12"} }');
    """
    from bitdust.interface import api_device
    if _Debug:
        lg.args(_DebugLevel, name=name)
    try:
        api_device.disable_device(name)
    except Exception as exc:
        return ERROR(exc)
    try:
        api_device.stop_device(name)
    except Exception as exc:
        return ERROR(exc)
    return device_info(name)


def device_remove(name: str):
    """
    Removes stored configuration of the given API device.

    ###### HTTP
        curl -X DELETE 'localhost:8180/device/remove/v1' -d '{"name": "my_iPhone_12"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "device_remove", "kwargs": {"name": "my_iPhone_12"} }');
    """
    from bitdust.interface import api_device
    try:
        api_device.remove_device(name)
    except Exception as exc:
        return ERROR(exc)
    return OK()


def device_router_info():
    """
    Returns information about the web socket router service , running on that device.

    The `web_socket_router` service help other BitDust users to connect thier mobile devices to BitDust full-node devices
    via routed web socket connections.

    This way you can enter into the BitDust network from a "lightweight" client device.

    Your own BitDust node application must be already running on your home PC, laptop or another server.
    Then your mobile device will be automatically connected to your home computer via this secure web socket connecton.

    To support this way to enter to the BitDust network and make it available for the people,
    sufficient number of web socket routers must be already running in the network.

    Those active users will be transmitting encrypted web socket traffic over the Internet for you.
    You can enable and disable the `web_socket_router` service in the config at any moment.

    ###### HTTP
        curl -X GET 'localhost:8180/device/router/info/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "device_router_info", "kwargs": {} }');
    """
    if not driver.is_on('service_web_socket_router'):
        return ERROR('service_web_socket_router() is not started')
    try:
        from bitdust.interface import web_socket_transmitter
        routes = []
        total_internal_bytes = 0
        total_external_bytes = 0
        for route_id, route_info in web_socket_transmitter.routes().items():
            r = {
                'created': route_info.get('created') or None,
                'route_id': route_id,
                'node_url': route_info.get('internal_url') or None,
                'node_connected': bool(route_info.get('internal_transport')),
                'node_bytes': route_info.get('internal_bytes') or 0,
                'node_updated': route_info.get('internal_updated') or None,
                'route_url': route_info.get('route_url') or None,
                'client_connected': bool(route_info.get('external_transport')),
                'client_bytes': route_info.get('external_bytes') or 0,
                'client_updated': route_info.get('external_updated') or None,
            }
            routes.append(r)
            total_internal_bytes += r['node_bytes']
            total_external_bytes += r['client_bytes']
        return OK({
            'routes': routes,
            'nodes_bytes': total_internal_bytes,
            'clients_bytes': total_external_bytes,
        })
    except Exception as exc:
        lg.exc()
        return ERROR(exc)


#------------------------------------------------------------------------------


def network_create(url: str):
    """
    This method is a way to load a new custom network configuration for this BitDust node.

    You can always use the default network configuration - this is a public network available for everyone.
    The seed nodes are maintained by the founders of the project.

    But you can also run your own hardware and maintain a number of your own BitDust seed nodes.
    This is a way to run a completely isolated and private BitDust network.

    All BitDust users on your network will need to run this method once on their devices to load the custom network configuration and
    make software know where to connect for the first time.

    The `url` parameter is a web location of the JSON-formatted network configuration file.
    It can also be a full path to the local file where the network configuration is stored on your drive.

    ###### HTTP
        curl -X POST 'localhost:8180/network/create/v1' -d '{"url": "https://my-people.secure-url-location.org/network.json"}

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "network_create", "kwargs": {"url": "https://my-people.secure-url-location.org/network.json"} }');
    """
    from bitdust.system import deploy
    from bitdust.system import local_fs
    from bitdust.main import initializer
    from bitdust.main import shutdowner
    from bitdust.main import settings
    from bitdust.lib import net_misc
    from bitdust.lib import serialization
    ret = Deferred()

    def _on_network_disconnected(x, network_info):
        cur_base_dir = deploy.current_base_dir()
        cur_network = deploy.current_network()
        shutdowner.shutdown_services()
        shutdowner.shutdown_local()
        shutdowner.shutdown_automats()
        shutdowner.shutdown_engine()
        shutdowner.shutdown_settings()
        deploy.init_current_network(name=network_info['name'], base_dir=cur_base_dir)
        initializer.init_settings(base_dir=cur_base_dir)
        networks_json_path = os.path.join(settings.MetaDataDir(), 'networkconfig')
        local_fs.WriteBinaryFile(networks_json_path, serialization.DictToBytes(network_info, indent=2))
        shutdowner.shutdown_settings()
        deploy.init_current_network(name=cur_network, base_dir=cur_base_dir)
        initializer.init_settings(base_dir=cur_base_dir)
        initializer.init_engine()
        initializer.init_automats()
        initializer.init_local()
        d = initializer.init_services()
        d.addCallback(lambda resp: ret.callback(OK(resp, api_method='network_create')))
        d.addErrback(lambda err: ret.callback(ERROR(err, api_method='network_create')))
        return None

    def _on_network_info_received(raw_data):
        try:
            network_info = serialization.BytesToDict(
                strng.to_bin(raw_data),
                keys_to_text=True,
                values_to_text=True,
            )
        except Exception as exc:
            ret.callback(ERROR(exc, api_method='network_create'))
            return ret
        try:
            network_name = network_info['name']
            network_info['label']
            network_info['maintainer']
        except:
            ret.callback(ERROR('incorrect network configuration', api_method='network_create'))
            return ret
        if os.path.isdir(os.path.join(deploy.current_base_dir(), network_name)):
            ret.callback(ERROR('network %r already exist' % network_name, api_method='network_create'))
            return ret
        d = network_disconnect()
        d.addCallback(_on_network_disconnected, network_info)
        d.addErrback(lambda err: ret.callback(ERROR(err, api_method='network_create')))
        return ret

    network_info_raw = None
    try:
        if os.path.isfile(url):
            network_info_raw = local_fs.ReadBinaryFile(url)
    except:
        pass
    if network_info_raw:
        return _on_network_info_received(network_info_raw)
    d = net_misc.getPageTwisted(url)
    d.addCallback(_on_network_info_received)
    d.addErrback(lambda err: ret.callback(ERROR(err, api_method='network_create')))
    return ret


def network_select(name: str):
    """
    Use this method to switch between different, previously loaded, network configurations.
    Only one network configuration can be active at a moment.

    ###### HTTP
        curl -X POST 'localhost:8180/network/select/v1' -d '{"name": "my-people"}

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "network_select", "kwargs": {"name": "my-people"} }');
    """
    from bitdust.system import deploy
    from bitdust.main import initializer
    from bitdust.main import shutdowner
    if not os.path.isdir(os.path.join(deploy.current_base_dir(), name)):
        return ERROR('network %r does not exist' % name)
    ret = Deferred()

    def _on_network_disconnected(x):
        cur_base_dir = deploy.current_base_dir()
        # TODO: must wait shutdown and init to complete with defered
        shutdowner.shutdown_services()
        shutdowner.shutdown_local()
        shutdowner.shutdown_automats()
        shutdowner.shutdown_engine()
        shutdowner.shutdown_settings()
        deploy.init_current_network(name=name, base_dir=cur_base_dir)
        initializer.init_settings(base_dir=cur_base_dir)
        initializer.init_engine()
        initializer.init_automats()
        initializer.init_local()
        d = initializer.init_services()
        d.addCallback(lambda resp: ret.callback(OK(resp, api_method='network_select')))
        d.addErrback(lambda err: ret.callback(ERROR(err, api_method='network_select')))
        return None

    d = network_disconnect()
    d.addCallback(_on_network_disconnected)
    d.addErrback(lambda err: ret.callback(ERROR(err, api_method='network_select')))
    return ret


def network_connected(wait_timeout: int = 5):
    """
    Method can be used by clients to ensure BitDust application is connected to other nodes in the network.

    If all is good this method will block for `wait_timeout` seconds. In case of some network issues method will return result immediately.

    ###### HTTP
        curl -X GET 'localhost:8180/network/connected/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "network_connected", "kwargs": {} }');
    """
    if _Debug:
        lg.out(_DebugLevel + 10, 'api.network_connected  wait_timeout=%r' % wait_timeout)
    if not driver.is_on('service_network'):
        return ERROR('service_network() is not started')
    ret = Deferred()

    def _on_network_service_connected(resp):
        if 'error' in resp:
            ret.callback(ERROR(resp['error'], reason=resp.get('reason'), api_method='network_connected'))
            return None
        ret.callback(OK(resp, api_method='network_connected'))
        return None

    from bitdust.p2p import network_service
    d = network_service.connected(wait_timeout=wait_timeout)
    d.addCallback(_on_network_service_connected)
    d.addErrback(lambda err: ret.callback(ERROR(err, api_method='network_connected')))
    return ret


def network_disconnect():
    """
    This method will stop `service_network()` service.
    Your BitDust node will be completely disconnected from the currently selected peer-to-peer network.

    ###### HTTP
        curl -X GET 'localhost:8180/network/disconnect/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "network_disconnect", "kwargs": {} }');
    """
    ret = Deferred()
    d = driver.stop_single('service_network')
    d.addCallback(lambda resp: ret.callback(OK(resp, api_method='network_disconnect')))
    d.addErrback(lambda err: ret.callback(ERROR(err, api_method='network_disconnect')))
    return ret


def network_reconnect():
    """
    Method can be used to refresh network status and restart all internal connections.

    ###### HTTP
        curl -X GET 'localhost:8180/network/reconnect/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "network_reconnect", "kwargs": {} }');
    """
    if not driver.is_on('service_network'):
        return ERROR('service_network() is not started')
    from bitdust.p2p import network_connector
    if _Debug:
        lg.out(_DebugLevel, 'api.network_reconnect')
    network_connector.A('reconnect')
    return OK(message='reconnected')


def network_status(suppliers: bool = False, customers: bool = False, cache: bool = False, tcp: bool = False, udp: bool = False, proxy: bool = False, dht: bool = False):
    """
    Returns detailed info about current network status, protocols and active connections.

    ###### HTTP
        curl -X GET 'localhost:8180/network/status/v1?cache=1&suppliers=1&dht=1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "network_status", "kwargs": {"cache": 1, "suppliers": 1, "dht": 1} }');
    """
    if not driver.is_on('service_network'):
        return ERROR('service_network() is not started')
    from bitdust.automats import automat
    from bitdust.lib import net_misc
    from bitdust.main import settings
    from bitdust.userid import my_id
    from bitdust.userid import global_id

    r = {
        'p2p_connector_state': None,
        'network_connector_state': None,
        'idurl': None,
        'global_id': None,
    }
    p2p_connector_lookup = automat.find('p2p_connector')
    if p2p_connector_lookup:
        p2p_connector_machine = automat.by_index(p2p_connector_lookup[0])
        if p2p_connector_machine:
            r['p2p_connector_state'] = p2p_connector_machine.state
    network_connector_lookup = automat.find('network_connector')
    if network_connector_lookup:
        network_connector_machine = automat.by_index(network_connector_lookup[0])
        if network_connector_machine:
            r['network_connector_state'] = network_connector_machine.state
    if my_id.isLocalIdentityReady():
        r['idurl'] = my_id.getIDURL()
        r['global_id'] = my_id.getID()
        r['identity_sources'] = my_id.getLocalIdentity().getSources(as_originals=True)
        r['identity_contacts'] = my_id.getLocalIdentity().getContacts()
        r['identity_revision'] = my_id.getLocalIdentity().getRevisionValue()
    if True in [suppliers, customers, cache] and driver.is_on('service_p2p_hookups'):
        from bitdust.contacts import contactsdb
        from bitdust.p2p import online_status
        if suppliers:
            connected = 0
            items = []
            for idurl in contactsdb.all_suppliers():
                i = {'idurl': idurl, 'global_id': global_id.UrlToGlobalID(idurl), 'state': None}
                inst = online_status.getInstance(idurl)
                if inst:
                    i['state'] = inst.state
                    if inst.state == 'CONNECTED':
                        connected += 1
                items.append(i)
            r['suppliers'] = {
                'desired': settings.getSuppliersNumberDesired(),
                'requested': contactsdb.num_suppliers(),
                'connected': connected,
                'total': contactsdb.total_suppliers(),
                'peers': items,
            }
        if customers:
            connected = 0
            items = []
            for idurl in contactsdb.customers():
                i = {'idurl': idurl, 'global_id': global_id.UrlToGlobalID(idurl), 'state': None}
                inst = online_status.getInstance(idurl)
                if inst:
                    i['state'] = inst.state
                    if inst.state == 'CONNECTED':
                        connected += 1
                items.append(i)
            r['customers'] = {
                'connected': connected,
                'total': contactsdb.num_customers(),
                'peers': items,
            }
        if cache:
            from bitdust.contacts import identitycache
            connected = 0
            items = []
            for idurl in identitycache.Items().keys():
                i = {'idurl': idurl, 'global_id': global_id.UrlToGlobalID(idurl), 'state': None}
                inst = online_status.getInstance(idurl)
                if inst:
                    i['state'] = inst.state
                    if inst.state == 'CONNECTED':
                        connected += 1
                items.append(i)
            r['cache'] = {
                'total': identitycache.CacheLen(),
                'connected': connected,
                'peers': items,
            }
    if True in [tcp, udp, proxy]:
        from bitdust.transport import gateway
        if tcp:
            r['tcp'] = {
                'sessions': [],
                'streams': [],
            }
            if driver.is_on('service_tcp_transport'):
                sessions = []
                for s in gateway.list_active_sessions('tcp'):
                    i = s.to_json()
                    i.update(
                        {
                            'peer': getattr(s, 'peer', None),
                            'state': getattr(s, 'state', None),
                            'id': getattr(s, 'id', None),
                            'idurl': getattr(s, 'peer_idurl', None),
                            'address': net_misc.pack_address_text(getattr(s, 'peer_address', None)),
                            'external_address': net_misc.pack_address_text(getattr(s, 'peer_external_address', None)),
                            'connection_address': net_misc.pack_address_text(getattr(s, 'connection_address', None)),
                            'bytes_received': getattr(s, 'total_bytes_received', 0),
                            'bytes_sent': getattr(s, 'total_bytes_sent', 0),
                        }
                    )
                    sessions.append(i)
                streams = []
                for s in gateway.list_active_streams('tcp'):
                    i = {
                        'started': s.started,
                        'stream_id': s.file_id,
                        'transfer_id': s.transfer_id,
                        'size': s.size,
                        'type': s.typ,
                    }
                    streams.append(i)
                r['tcp']['sessions'] = sessions
                r['tcp']['streams'] = streams
        if udp:
            from bitdust.lib import udp
            r['udp'] = {
                'sessions': [],
                'streams': [],
                'ports': [],
            }
            for one_listener in udp.listeners().values():
                r['udp']['ports'].append(one_listener.port)
            if driver.is_on('service_udp_transport'):
                sessions = []
                for s in gateway.list_active_sessions('udp'):
                    i = s.to_json()
                    i.update(
                        {
                            'peer': s.peer_id,
                            'state': s.state,
                            'id': s.id,
                            'idurl': s.peer_idurl,
                            'address': net_misc.pack_address_text(s.peer_address),
                            'bytes_received': s.bytes_sent,
                            'bytes_sent': s.bytes_received,
                            'outgoing': len(s.file_queue.outboxFiles),
                            'incoming': len(s.file_queue.inboxFiles),
                            'queue': len(s.file_queue.outboxQueue),
                            'dead_streams': len(s.file_queue.dead_streams),
                        }
                    )
                    sessions.append(i)
                streams = []
                for s in gateway.list_active_streams('udp'):
                    streams.append({
                        'started': s.started,
                        'stream_id': s.stream_id,
                        'transfer_id': s.transfer_id,
                        'size': s.size,
                        'type': s.typ,
                    })
                r['udp']['sessions'] = sessions
                r['udp']['streams'] = streams
        if proxy:
            r['proxy'] = {
                'sessions': [],
            }
            if driver.is_on('service_proxy_transport'):
                sessions = []
                for s in gateway.list_active_sessions('proxy'):
                    i = s.to_json()
                    if getattr(s, 'router_idurl', None):
                        i['idurl'] = s.router_idurl
                        i['router'] = global_id.UrlToGlobalID(s.router_idurl)
                    if getattr(s, 'pending_packets', None):
                        i['queue'] = len(s.pending_packets)
                    sessions.append(i)
                r['proxy']['sessions'] = sessions
            if driver.is_on('service_proxy_server'):
                from bitdust.transport.proxy import proxy_router
                if proxy_router.A():
                    r['proxy']['routes'] = []
                    for v in proxy_router.A().routes.values():
                        _r = v['connection_info'].copy()
                        _r['contacts'] = ', '.join(['{}:{}'.format(c[0], c[1]) for c in v['contacts']])
                        _r['address'] = ', '.join(['{}:{}'.format(a[0], a[1]) for a in v['address']])
                        _r.pop('id', None)
                        _r.pop('index', None)
                        r['proxy']['routes'].append(_r)
                    r['proxy']['closed_routes'] = [(strng.to_text(k), strng.to_text(v)) for k, v in proxy_router.A().closed_routes.items()]
                    r['proxy']['acks'] = len(proxy_router.A().acks)
                    r['proxy']['hosts'] = ', '.join([('{}://{}:{}'.format(strng.to_text(k), strng.to_text(v[0]), strng.to_text(v[1]))) for k, v in proxy_router.A().my_hosts.items()])
    if dht:
        from bitdust.dht import dht_service
        r['dht'] = {}
        if driver.is_on('service_entangled_dht'):
            layers = []
            for layer_id in sorted(dht_service.node().layers):
                layers.append(
                    {
                        'layer_id': layer_id,
                        'data_store_items': len(dht_service.node()._dataStores[layer_id].keys()),
                        'node_items': len(dht_service.node().data.get(layer_id, {})),
                        'node_id': dht_service.node().layers[layer_id],
                        'buckets': len(dht_service.node()._routingTables[layer_id]._buckets),
                        'contacts': dht_service.node()._routingTables[layer_id].totalContacts(),
                        'attached': (layer_id in dht_service.node().attached_layers),
                        'active': (layer_id in dht_service.node().active_layers),
                        'packets_received': dht_service.node().packets_in.get(layer_id, 0),
                        'packets_sent': dht_service.node().packets_out.get(layer_id, 0),
                        'rpc_calls': dht_service.node().rpc_calls.get(layer_id, {}),
                        'rpc_responses': dht_service.node().rpc_responses.get(layer_id, {}),
                    }
                )
            r['dht'].update({
                'udp_port': dht_service.node().port,
                'bytes_received': dht_service.node().bytes_in,
                'bytes_sent': dht_service.node().bytes_out,
                'layers': layers,
            })
    return OK(r)


def network_configuration():
    """
    Returns details about network services.

    ###### HTTP
        curl -X GET 'localhost:8180/network/configuration/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "network_configuration", "kwargs": {} }');
    """
    return OK(driver.get_network_configuration())


def network_stun(udp_port: int = None, dht_port: int = None):
    """
    Begins network STUN process to detect your network configuration and current external IP address of that host.

    ###### HTTP
        curl -X GET 'localhost:8180/network/stun/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "network_stun", "kwargs": {} }');
    """
    from bitdust.stun import stun_client
    ret = Deferred()
    d = stun_client.safe_stun(udp_port=udp_port, dht_port=dht_port)
    d.addBoth(lambda r: ret.callback(OK(r, api_method='network_stun')))
    return ret


#------------------------------------------------------------------------------


def config_get(key: str, include_info: bool = False):
    """
    Returns current key/value from the program settings.

    ###### HTTP
        curl -X GET 'localhost:8180/config/get/v1?key=logs/debug-level'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "config_get", "kwargs": {"key": "logs/debug-level"} }');
    """
    try:
        key = strng.to_text(key).strip('/')
    except:
        return ERROR('wrong key')
    if not key:
        return ERROR('empty key')
    if _Debug:
        lg.out(_DebugLevel, 'api.config_get [%s]' % key)
    if not config.conf().registered(key):
        return ERROR('option %s does not exist' % key)
    if not config.conf().hasChilds(key):
        return RESULT([config.conf().toJson(key, include_info=include_info)])
    known_childs = sorted(config.conf().listEntries(key))
    if key.startswith('services/') and key.count('/') == 1:
        svc_enabled_key = key + '/enabled'
        if svc_enabled_key in known_childs:
            known_childs.remove(svc_enabled_key)
            known_childs.insert(0, svc_enabled_key)
    childs = []
    for child in known_childs:
        if config.conf().hasChilds(child):
            childs.append({
                'key': child,
                'childs': len(config.conf().listEntries(child)),
            })
        else:
            childs.append(config.conf().toJson(child, include_info=include_info))
    return RESULT(childs)


def config_set(key: str, value: str):
    """
    Set a value for given key option.

    ###### HTTP
        curl -X POST 'localhost:8180/config/set/v1' -d '{"key": "logs/debug-level", "value": 12}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "config_set", "kwargs": {"key": "logs/debug-level", "value": 12} }');
    """
    key = strng.to_text(key)
    v = {}
    if not config.conf().registered(key):
        return ERROR('option %s does not exist' % key)
    if config.conf().exist(key):
        v['old_value'] = config.conf().getValueOfType(key)
    typ_label = config.conf().getTypeLabel(key)
    if _Debug:
        lg.out(_DebugLevel, 'api.config_set [%s]=%s type is %s' % (key, value, typ_label))
    # TODO: verify value against type of the field
    config.conf().setValueOfType(key, value)
    v.update(config.conf().toJson(key, include_info=False))
    return RESULT([
        v,
    ])


def configs_list(sort: bool = False, include_info: bool = False):
    """
    Provide detailed info about all program settings.

    ###### HTTP
        curl -X GET 'localhost:8180/config/list/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "configs_list", "kwargs": {} }');
    """
    if _Debug:
        lg.out(_DebugLevel, 'api.configs_list')
    r = config.conf().cache()
    r = [config.conf().toJson(key, include_info=include_info) for key in list(r.keys()) if config.conf().getType(key)]
    if sort:
        r = sorted(r, key=lambda i: i['key'])
    return RESULT(r)


def configs_tree(include_info: bool = False):
    """
    Returns all options as a tree structure, can be more suitable for UI operations.

    ###### HTTP
        curl -X GET 'localhost:8180/config/tree/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "configs_tree", "kwargs": {} }');
    """
    if _Debug:
        lg.out(_DebugLevel, 'api.configs_tree')
    r = {}
    for key in config.conf().cache():
        cursor = r
        for part in key.split('/'):
            if part not in cursor:
                cursor[part] = {}
            cursor = cursor[part]
        cursor.update(config.conf().toJson(key, include_info=include_info))
    return RESULT([
        r,
    ])


#------------------------------------------------------------------------------


def identity_get(include_xml_source: bool = False):
    """
    Returns your identity info.

    ###### HTTP
        curl -X GET 'localhost:8180/identity/get/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "identity_get", "kwargs": {} }');
    """
    from bitdust.userid import my_id
    if not my_id.isLocalIdentityReady():
        return ERROR('local identity is not valid or not exist')
    r = my_id.getLocalIdentity().serialize_json()
    if include_xml_source:
        r['xml'] = my_id.getLocalIdentity().serialize(as_text=True)
    return OK(r)


def identity_create(username: str, preferred_servers: str = '', join_network: bool = False):
    """
    Generates new private key and creates new identity for you to be able to communicate with other nodes in the network.

    Parameter `username` defines filename of the new identity, can not be changed anymore.

    By default that method only connects to ID servers to be able to register a new identity file for you.
    If you also pass `join_network=True` it will start all network services right after that and will make
    you connected to the BitDust network automatically.

    ###### HTTP
        curl -X POST 'localhost:8180/identity/create/v1' -d '{"username": "alice", "join_network": 1}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "identity_create", "kwargs": {"username": "alice", "join_network": 1} }');
    """
    from bitdust.lib import misc
    from bitdust.crypt import key
    from bitdust.userid import id_registrator
    from bitdust.userid import my_id
    if my_id.isLocalIdentityReady() or (my_id.isLocalIdentityExists() and key.isMyKeyExists()):
        return ERROR('local identity already exist')
    try:
        username = strng.to_text(username)
    except:
        return ERROR('invalid user name')
    if not misc.ValidUserName(username):
        return ERROR('invalid user name')

    ret = Deferred()
    my_id_registrator = id_registrator.A()

    def _id_registrator_state_changed(oldstate, newstate, event_string, *args, **kwargs):
        if _Debug:
            lg.args(_DebugLevel, oldstate=oldstate, newstate=newstate, event_string=event_string)
        if ret.called:
            return
        if oldstate != newstate and newstate == 'FAILED':
            ret.callback(ERROR(my_id_registrator.last_message, api_method='identity_create'))
            return
        if oldstate != newstate and newstate == 'DONE':
            my_id.loadLocalIdentity()
            if not my_id.isLocalIdentityReady():
                return ERROR('identity create failed', api_method='identity_create')
            r = my_id.getLocalIdentity().serialize_json()
            r['xml'] = my_id.getLocalIdentity().serialize(as_text=True)
            if join_network:
                from bitdust.p2p import network_service
                network_service.connected(wait_timeout=0.1)
            ret.callback(OK(r, api_method='identity_create'))
            return

    my_id_registrator.addStateChangedCallback(_id_registrator_state_changed)
    my_id_registrator.A('start', username=username, preferred_servers=(preferred_servers.strip().split(',') if preferred_servers.strip() else []))
    return ret


def identity_backup(destination_filepath: str):
    """
    Creates local file at `destination_filepath` on your disk drive with a backup copy of your private key and recent IDURL.

    You can use that file to restore identity in case of lost data using `identity_recover()` API method.

    WARNING! Make sure to always have a backup copy of your identity secret key in a safe place - there is no other way
    to restore your data in case of lost.

    ###### HTTP
        curl -X POST 'localhost:8180/identity/backup/v1' -d '{"destination_filepath": "/tmp/alice_backup.key"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "identity_backup", "kwargs": {"destination_filepath": "/tmp/alice_backup.key"} }');
    """
    from bitdust.userid import my_id
    from bitdust.crypt import key
    from bitdust.system import bpio
    if not my_id.isLocalIdentityReady():
        return ERROR('local identity is not ready')
    TextToSave = ''
    for id_source in my_id.getLocalIdentity().getSources(as_originals=True):
        TextToSave += strng.to_text(id_source) + u'\n'
    TextToSave += key.MyPrivateKey()
    if not bpio.WriteTextFile(destination_filepath, TextToSave):
        del TextToSave
        gc.collect()
        return ERROR('error writing to %s\n' % destination_filepath)
    del TextToSave
    gc.collect()
    return OK(message='WARNING! keep the master key in a safe place and never publish it anywhere!')


def identity_recover(private_key_source: str, known_idurl: str = None, join_network: bool = False):
    """
    Restores your identity from backup copy.

    Input parameter `private_key_source` must contain your latest IDURL and the private key as openssh formated string.

    ###### HTTP
        curl -X POST 'localhost:8180/identity/recover/v1' -d '{"private_key_source": "http://some-host.com/alice.xml\n-----BEGIN RSA PRIVATE KEY-----\nMIIEogIBAAKC..."}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "identity_recover", "kwargs": {"private_key_source": "http://some-host.com/alice.xml\n-----BEGIN RSA PRIVATE KEY-----\nMIIEogIBAAKC..."} }');
    """
    from bitdust.crypt import key
    from bitdust.userid import id_url
    from bitdust.userid import id_restorer
    from bitdust.userid import my_id
    if my_id.isLocalIdentityReady() or (my_id.isLocalIdentityExists() and key.isMyKeyExists()):
        return ERROR('local identity already exist')
    if not private_key_source:
        return ERROR('must provide private key in order to recover your identity')
    if len(private_key_source) > 1024*10:
        return ERROR('private key is too large')
    idurl_list = []
    pk_source = ''
    try:
        lines = private_key_source.split('\n')
        for i in range(len(lines)):
            line = lines[i]
            if not line.startswith('-----BEGIN RSA PRIVATE KEY-----'):
                idurl_list.append(id_url.field(line))
                continue
            pk_source = '\n'.join(lines[i:])
            break
    except:
        idurl_list = []
        pk_source = private_key_source
    if not idurl_list and known_idurl:
        idurl_list.append(known_idurl)
    if not idurl_list:
        return ERROR('you must provide at least one IDURL address of your identity')

    ret = Deferred()
    my_id_restorer = id_restorer.A()

    def _id_restorer_state_changed(oldstate, newstate, event_string, *args, **kwargs):
        if _Debug:
            lg.args(_DebugLevel, oldstate=oldstate, newstate=newstate, event_string=event_string)
        if ret.called:
            return
        if newstate == 'FAILED':
            ret.callback(ERROR(my_id_restorer.last_message, api_method='identity_recover'))
            return
        if newstate == 'RESTORED!':
            my_id.loadLocalIdentity()
            if not my_id.isLocalIdentityReady():
                return ERROR('identity recovery', api_method='identity_recover')
            r = my_id.getLocalIdentity().serialize_json()
            r['xml'] = my_id.getLocalIdentity().serialize(as_text=True)
            if join_network:
                from bitdust.p2p import network_service
                network_service.connected(wait_timeout=0.1)
            ret.callback(OK(r, api_method='identity_recover'))
            return

    try:
        my_id_restorer.addStateChangedCallback(_id_restorer_state_changed)
        my_id_restorer.A('start', {
            'idurl': idurl_list[0],
            'keysrc': pk_source,
        })
        # TODO: iterate over idurl_list to find at least one reliable source
    except Exception as exc:
        lg.exc()
        ret.callback(ERROR(exc, api_method='identity_recover'))
    return ret


def identity_erase(erase_private_key: bool = False):
    """
    Method will erase current identity file and the private key (optionally).
    All network services will be stopped first.

    ###### HTTP
        curl -X DELETE 'localhost:8180/identity/erase/v1' -d '{"erase_private_key": true}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "identity_erase", "kwargs": {"erase_private_key": true} }');
    """
    return ERROR('not implemented yet. please manually stop the application process and erase files inside ".bitdust/[network name]/metadata/" folder')


def identity_rotate():
    """
    Rotate your identity sources and republish identity file on another ID server even if current ID servers are healthy.

    Normally that procedure is executed automatically when current process detects unhealthy ID server among your identity sources.

    This method is provided for testing and development purposes.

    ###### HTTP
        curl -X PUT 'localhost:8180/identity/rotate/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "identity_rotate", "kwargs": {} }');
    """
    from bitdust.userid import my_id
    if not my_id.isLocalIdentityReady():
        return ERROR('local identity is not ready')
    from bitdust.p2p import id_rotator
    old_sources = my_id.getLocalIdentity().getSources(as_originals=True)
    ret = Deferred()
    d = id_rotator.run(force=True)

    def _cb(result, rotated):
        if not result:
            ret.callback(ERROR(result, api_method='identity_rotate'))
            return None
        r = my_id.getLocalIdentity().serialize_json()
        r['old_sources'] = old_sources
        r['rotated'] = rotated
        ret.callback(OK(r, api_method='identity_rotate'))
        return None

    def _eb(e):
        ret.callback(ERROR(e, api_method='identity_rotate'))
        return None

    d.addCallback(_cb)
    d.addErrback(_eb)
    return ret


def identity_cache_list():
    """
    Returns list of all cached locally identity files received from other users.

    ###### HTTP
        curl -X GET 'localhost:8180/identity/cache/list/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "identity_cache_list", "kwargs": {} }');
    """
    from bitdust.contacts import identitycache
    results = []
    for id_obj in identitycache.Items().values():
        r = id_obj.serialize_json()
        results.append(r)
    results.sort(key=lambda r: r['name'])
    return RESULT(results)


#------------------------------------------------------------------------------


def key_get(key_id: str, include_private: bool = False, include_signature: bool = False, generate_signature: bool = False):
    """
    Returns details of the registered public or private key.

    Use `include_private=True` if you also need a private key (as openssh formated string) to be present in the response.

    ###### HTTP
        curl -X GET 'localhost:8180/key/get/v1?key_id=abcd1234$alice@server-a.com'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "key_get", "kwargs": {"key_id": "abcd1234$alice@server-a.com"} }');
    """
    if not driver.is_on('service_keys_registry'):
        return ERROR('service_keys_registry() is not started')
    if _Debug:
        lg.out(_DebugLevel, 'api.key_get')
    from bitdust.crypt import my_keys
    try:
        key_info = my_keys.get_key_info(
            key_id=key_id,
            include_private=include_private,
            include_signature=include_signature,
            generate_signature=generate_signature,
        )
        key_info.pop('include_private', None)
    except Exception as exc:
        return ERROR(exc)
    return OK(key_info)


def keys_list(sort: bool = False, include_private: bool = False):
    """
    List details for all registered public and private keys.

    Use `include_private=True` if you also need a private key (as openssh formated string) to be present in the response.

    ###### HTTP
        curl -X GET 'localhost:8180/key/list/v1?include_private=1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "keys_list", "kwargs": {"include_private": 1} }');
    """
    if not driver.is_on('service_keys_registry'):
        return ERROR('service_keys_registry() is not started')
    if _Debug:
        lg.out(_DebugLevel, 'api.keys_list')
    from bitdust.crypt import my_keys
    r = []
    for key_id, key_object in my_keys.known_keys().items():
        key_alias, creator_idurl = my_keys.split_key_id(key_id)
        if not key_alias or not creator_idurl:
            lg.warn('incorrect key_id: %s' % key_id)
            continue
        try:
            key_info = my_keys.make_key_info(key_object, key_id=key_id, include_private=include_private, include_local_id=True, include_state=True)
        except:
            key_info = my_keys.make_key_info(key_object, key_id=key_id, include_private=False, include_local_id=True, include_state=True)
        key_info.pop('include_private', None)
        r.append(key_info)
    if sort:
        r = sorted(r, key=lambda i: i['alias'])
    r.insert(0, my_keys.make_master_key_info(include_private=include_private))
    return RESULT(r)


def key_create(key_alias: str, key_size: int = None, label: str = '', active: bool = True, include_private: bool = False):
    """
    Generate new RSA private key and add it to the list of registered keys with a new `key_id`.

    Optional input parameter `key_size` can be 1024, 2048, 4096. If `key_size` was not passed, default value will be
    populated from the `personal/private-key-size` program setting.

    Parameter `label` can be used to attach some meaningful information for the user to display in the UI.

    Use `include_private=True` if you also need a private key (as openssh formated string) to be present in the response.

    ###### HTTP
        curl -X POST 'localhost:8180/key/create/v1' -d '{"key_alias": "abcd1234", "key_size": 1024, "label": "Cats and Dogs"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "key_create", "kwargs": {"key_alias": "abcd1234", "key_size": 1024, "label": "Cats and Dogs"} }');
    """
    if not driver.is_on('service_keys_registry'):
        return ERROR('service_keys_registry() is not started')
    from bitdust.lib import utime
    from bitdust.crypt import my_keys
    from bitdust.main import settings
    from bitdust.userid import my_id
    key_alias = strng.to_text(key_alias)
    key_alias = key_alias.strip().lower()
    key_id = my_keys.make_key_id(key_alias, creator_idurl=my_id.getIDURL())
    if not my_keys.is_valid_key_id(key_id):
        return ERROR('key %s is not valid' % key_id)
    if my_keys.is_key_registered(key_id):
        return ERROR('key %s already exist' % key_id)
    if not key_size:
        key_size = settings.getPrivateKeySize()
    if _Debug:
        lg.out(_DebugLevel, 'api.key_create id=%s, size=%s' % (key_id, key_size))
    if not label:
        label = 'key%s' % utime.make_timestamp()
    key_object = my_keys.generate_key(key_id, label=label, active=active, key_size=key_size)
    if key_object is None:
        return ERROR('failed to generate private key %s' % key_id)
    key_info = my_keys.make_key_info(
        key_object,
        key_id=key_id,
        include_private=include_private,
        include_state=True,
    )
    key_info.pop('include_private', None)
    return OK(
        key_info,
        message='new private key %s was generated successfully' % key_alias,
    )


def key_label(key_id: str, label: str):
    """
    Set new label for the given key.

    ###### HTTP
        curl -X POST 'localhost:8180/key/label/v1' -d '{"key_id": "abcd1234$alice@server-a.com", "label": "Man and Woman"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "key_label", "kwargs": {"key_id": "abcd1234$alice@server-a.com", "label": "Man and Woman"} }');
    """
    if not driver.is_on('service_keys_registry'):
        return ERROR('service_keys_registry() is not started')
    from bitdust.crypt import my_keys
    from bitdust.userid import my_id
    key_label = strng.to_text(label)
    if not my_keys.is_valid_key_id(key_id):
        return ERROR('key %s is not valid' % key_id)
    if not my_keys.is_key_registered(key_id):
        return ERROR('key %s does not exist' % key_id)
    if key_id == 'master' or key_id == my_id.getGlobalID(key_alias='master') or key_id == my_id.getID():
        return ERROR('master key label can not be changed')
    if _Debug:
        lg.out(_DebugLevel, 'api.key_label id=%s, label=%r' % (key_id, key_label))
    key_id = my_keys.latest_key_id(key_id)
    my_keys.key_obj(key_id).label = label
    if not my_keys.save_key(key_id):
        return ERROR('key %s store failed' % key_id)
    return OK(message='label for the key %s updated successfully' % key_id)


def key_state(key_id: str, active: bool):
    """
    Set active/inactive state for the given key.
    If key was set to "inactive" state, certain parts of the software will not use it.

    ###### HTTP
        curl -X POST 'localhost:8180/key/state/v1' -d '{"key_id": "abcd1234$alice@server-a.com", "active": false}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "key_state", "kwargs": {"key_id": "abcd1234$alice@server-a.com", "active": false} }');
    """
    if not driver.is_on('service_keys_registry'):
        return ERROR('service_keys_registry() is not started')
    from bitdust.crypt import my_keys
    from bitdust.userid import my_id
    if not my_keys.is_valid_key_id(key_id):
        return ERROR('key %s is not valid' % key_id)
    if not my_keys.is_key_registered(key_id):
        return ERROR('key %s does not exist' % key_id)
    if key_id == 'master' or key_id == my_id.getGlobalID(key_alias='master') or key_id == my_id.getID():
        return ERROR('master key can not be changed to inactive state')
    if _Debug:
        lg.out(_DebugLevel, 'api.key_state id=%s, active=%r' % (key_id, active))
    key_id = my_keys.latest_key_id(key_id)
    my_keys.set_active(key_id, active)
    if not my_keys.save_key(key_id):
        return ERROR('key %s store failed' % key_id)
    return OK(message='active state for the key %s updated successfully' % key_id)


def key_erase(key_id: str):
    """
    Unregister and remove given key from the list of known keys and erase local file.

    ###### HTTP
        curl -X DELETE 'localhost:8180/key/erase/v1' -d '{"key_id": "abcd1234$alice@server-a.com"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "key_erase", "kwargs": {"key_id": "abcd1234$alice@server-a.com"} }');
    """
    if not driver.is_on('service_keys_registry'):
        return ERROR('service_keys_registry() is not started')
    from bitdust.crypt import my_keys
    key_id = strng.to_text(key_id)
    if _Debug:
        lg.out(_DebugLevel, 'api.keys_list')
    if key_id == 'master':
        return ERROR('"master" key can not be erased')
    key_alias, creator_idurl = my_keys.split_key_id(key_id)
    if not key_alias or not creator_idurl:
        return ERROR('incorrect key_id format')
    if not my_keys.erase_key(key_id):
        return ERROR('failed to erase private key %s' % key_id)
    return OK(message='key %s was erased' % key_id)


def key_share(key_id: str, trusted_user_id: str, include_private: bool = False, include_signature: bool = False, timeout: int = 30):
    """
    Connects to remote user and transfer given public or private key to that node.
    This way you can share access to files/groups/resources with other users in the network.

    If you pass `include_private=True` also private part of the key will be shared, otherwise only public part.

    ###### HTTP
        curl -X PUT 'localhost:8180/key/share/v1' -d '{"key_id": "abcd1234$alice@server-a.com", "trusted_user_id": "bob@machine-b.net"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "key_share", "kwargs": {"key_id": "abcd1234$alice@server-a.com", "trusted_user_id": "bob@machine-b.net"} }');
    """
    from bitdust.userid import global_id
    try:
        trusted_user_id = strng.to_text(trusted_user_id)
        full_key_id = strng.to_text(key_id)
    except:
        return ERROR('error reading input parameters')
    if not driver.is_on('service_keys_registry'):
        return ERROR('service_keys_registry() is not started')
    glob_id = global_id.ParseGlobalID(full_key_id)
    if glob_id['key_alias'] == 'master':
        return ERROR('"master" key can not be shared')
    if not glob_id['key_alias'] or not glob_id['idurl']:
        return ERROR('incorrect key_id format')
    idurl = strng.to_bin(trusted_user_id)
    if global_id.IsValidGlobalUser(idurl):
        idurl = global_id.GlobalUserToIDURL(idurl, as_field=False)
    from bitdust.access import key_ring
    ret = Deferred()
    d = key_ring.share_key(key_id=full_key_id, trusted_idurl=idurl, include_private=include_private, include_signature=include_signature, timeout=timeout)
    d.addCallback(lambda resp: ret.callback(OK(strng.to_text(resp), api_method='key_share')))
    d.addErrback(lambda err: ret.callback(ERROR(err, api_method='key_share')))
    return ret


def key_audit(key_id: str, untrusted_user_id: str, is_private: bool = False, timeout: int = None):
    """
    Connects to remote node identified by `untrusted_user_id` parameter and request audit of given public or private key `key_id` on that node.

    Returns positive result if audit process succeed - that means remote user really possess the key.

    ###### HTTP
        curl -X POST 'localhost:8180/key/audit/v1' -d '{"key_id": "abcd1234$alice@server-a.com", "untrusted_user_id": "carol@computer-c.net", "is_private": 1}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "key_audit", "kwargs": {"key_id": "abcd1234$alice@server-a.com", "untrusted_user_id": "carol@computer-c.net", "is_private": 1} }');
    """
    from bitdust.userid import global_id
    try:
        untrusted_user_id = strng.to_text(untrusted_user_id)
        full_key_id = strng.to_text(key_id)
    except:
        return ERROR('error reading input parameters')
    if not driver.is_on('service_keys_registry'):
        return ERROR('service_keys_registry() is not started')
    glob_id = global_id.ParseGlobalID(full_key_id)
    if not glob_id['key_alias'] or not glob_id['idurl']:
        return ERROR('incorrect key_id format')
    if global_id.IsValidGlobalUser(untrusted_user_id):
        idurl = global_id.GlobalUserToIDURL(untrusted_user_id, as_field=False)
    else:
        idurl = strng.to_bin(untrusted_user_id)
    from bitdust.access import key_ring
    ret = Deferred()
    if is_private:
        d = key_ring.audit_private_key(key_id=key_id, untrusted_idurl=idurl, timeout=timeout)
    else:
        d = key_ring.audit_public_key(key_id=key_id, untrusted_idurl=idurl, timeout=timeout)
    d.addCallback(lambda resp: ret.callback(OK(strng.to_text(resp), api_method='key_audit')))
    d.addErrback(lambda err: ret.callback(ERROR(err, api_method='key_audit')))
    return ret


#------------------------------------------------------------------------------


def files_sync(force: bool = False):
    """
    This should restart "data synchronization" process with your remote suppliers.

    Normally all communications and synchronizations are handled automatically, so you do not need to
    call that method.

    This method is provided for testing and development purposes only.

    ###### HTTP
        curl -X GET 'localhost:8180/file/sync/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "files_sync", "kwargs": {} }');
    """
    if not driver.is_on('service_backups'):
        return ERROR('service_backups() is not started')
    if _Debug:
        lg.out(_DebugLevel, 'api.files_sync')
    from bitdust.storage import backup_monitor
    if force:
        from bitdust.customer import fire_hire
        fire_hire.ForceRestart()
    backup_monitor.A('restart')
    if _Debug:
        lg.out(_DebugLevel, 'api.files_sync')
    return OK('the main files sync loop has been restarted')


def files_list(remote_path: str = None, key_id: str = None, recursive: bool = True, all_customers: bool = False, include_uploads: bool = False, include_downloads: bool = False):
    """
    Returns list of all known files registered in the catalog under given `remote_path` folder.
    By default returns items from root of the catalog.

    If `key_id` is passed will only return items encrypted using that key.

    Use `all_customers=True` to get list of all registered files - including received/shared to you by another user.

    You can also use `include_uploads` and `include_downloads` parameters to get more info about currently running
    uploads and downloads.

    ###### HTTP
        curl -X GET 'localhost:8180/file/list/v1?remote_path=abcd1234$alice@server-a.com:pictures/cats/'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "files_list", "kwargs": {"remote_path": "abcd1234$alice@server-a.com:pictures/cats/"} }');
    """
    if not driver.is_on('service_backup_db'):
        return ERROR('service_backup_db() is not started')
    from bitdust.main import settings
    from bitdust.storage import backup_fs
    from bitdust.storage import backup_control
    from bitdust.system import bpio
    from bitdust.lib import misc
    from bitdust.userid import global_id
    from bitdust.crypt import my_keys
    result = []
    if remote_path:
        norm_path = global_id.NormalizeGlobalID(remote_path)
    else:
        if key_id:
            norm_path = global_id.NormalizeGlobalID(key_id)
        else:
            norm_path = global_id.NormalizeGlobalID(None)
    remotePath = bpio.remotePath(norm_path['path'])
    customer_idurl = norm_path['idurl']
    key_alias = norm_path['key_alias'] if not key_id else key_id.split('$')[0]
    if not all_customers and customer_idurl not in backup_fs.known_customers():
        return ERROR('customer %s was not found' % customer_idurl)
    backup_info_callback = None
    if driver.is_on('service_restores'):
        from bitdust.storage import restore_monitor
        backup_info_callback = restore_monitor.GetBackupStatusInfo
    lookup_results = []
    if all_customers:
        for customer_idurl in backup_fs.known_customers():
            if key_alias in backup_fs.known_keys_aliases(customer_idurl):
                look = backup_fs.ListChildsByPath(
                    path=remotePath,
                    recursive=recursive,
                    iter=backup_fs.fs(customer_idurl, key_alias),
                    iterID=backup_fs.fsID(customer_idurl, key_alias),
                    backup_info_callback=backup_info_callback,
                )
                if isinstance(look, list):
                    lookup_results.extend(look)
                else:
                    lg.warn(look)
    else:
        if key_alias in backup_fs.known_keys_aliases(customer_idurl):
            lookup_results = backup_fs.ListChildsByPath(
                path=remotePath,
                recursive=recursive,
                iter=backup_fs.fs(customer_idurl, key_alias),
                iterID=backup_fs.fsID(customer_idurl, key_alias),
                backup_info_callback=backup_info_callback,
            )
    if not isinstance(lookup_results, list):
        return ERROR(lookup_results)
    if _Debug:
        lg.out(_DebugLevel, '    lookup with %d items' % len(lookup_results))
    local_dir = settings.getRestoreDir()
    for i in lookup_results:
        if i['path_id'] == 'index':
            continue
        if key_id is not None and key_id != i['item']['k']:
            continue
        if key_id is None and norm_path['key_alias'] and i['item']['k']:
            if i['item']['k'] != my_keys.make_key_id(alias=norm_path['key_alias'], creator_glob_id=norm_path['customer']):
                continue
        k_alias = 'master'
        if i['item']['k']:
            real_key_id = i['item']['k']
            k_alias, real_idurl = my_keys.split_key_id(real_key_id)
            real_customer_id = global_id.UrlToGlobalID(real_idurl)
        else:
            real_key_id = my_keys.make_key_id(alias=k_alias, creator_idurl=customer_idurl)
            real_idurl = customer_idurl
            real_customer_id = global_id.UrlToGlobalID(customer_idurl)
        full_glob_id = global_id.MakeGlobalID(
            path=i['path_id'],
            customer=real_customer_id,
            key_alias=k_alias,
        )
        full_remote_path = global_id.MakeGlobalID(
            path=i['path'],
            customer=real_customer_id,
            key_alias=k_alias,
        )
        r = {
            'remote_path': full_remote_path,
            'global_id': full_glob_id,
            'customer': real_customer_id,
            'idurl': real_idurl,
            'path_id': i['path_id'],
            'name': i['name'],
            'path': i['path'],
            'type': backup_fs.TYPES.get(i['type'], '').lower(),
            'size': i['total_size'],
            'local_size': i['item']['s'],
            'latest': i['latest'],
            'key_id': real_key_id,
            'key_alias': k_alias,
            'childs': i['childs'],
            'versions': i['versions'],
            'uploads': {
                'running': [],
                'pending': [],
            },
            'downloads': [],
            'local_path': os.path.join(local_dir, bpio.remotePath(i['path'])),
        }
        if include_uploads:
            backup_control.tasks()
            running = []
            for backupID in backup_control.FindRunningBackup(pathID=full_glob_id):
                j = backup_control.jobs().get(backupID)
                if j:
                    running.append(
                        {
                            'backup_id': j.backupID,
                            'key_id': j.keyID,
                            'source_path': j.sourcePath,
                            'eccmap': j.eccmap.name,
                            'pipe': 'closed' if not j.pipe else j.pipe.state(),
                            'block_size': j.blockSize,
                            'aborting': j.ask4abort,
                            'terminating': j.terminating,
                            'eof_state': j.stateEOF,
                            'reading': j.stateReading,
                            'closed': j.closed,
                            'work_blocks': len(j.workBlocks),
                            'block_number': j.blockNumber,
                            'bytes_processed': j.dataSent,
                            'progress': misc.percent2string(j.progress()),
                            'total_size': j.totalSize,
                        }
                    )
            pending = []
            t = backup_control.GetPendingTask(full_glob_id)
            if t:
                pending.append({
                    'task_id': t.number,
                    'path_id': t.pathID,
                    'source_path': t.localPath,
                    'created': time.asctime(time.localtime(t.created)),
                })
            r['uploads']['running'] = running
            r['uploads']['pending'] = pending
        if include_downloads:
            downloads = []
            if driver.is_on('service_restores'):
                for backupID in restore_monitor.FindWorking(pathID=full_glob_id):
                    d = restore_monitor.GetWorkingRestoreObject(backupID)
                    if d:
                        downloads.append(
                            {
                                'backup_id': d.backup_id,
                                'creator_id': d.creator_id,
                                'path_id': d.path_id,
                                'version': d.version,
                                'block_number': d.block_number,
                                'bytes_processed': d.bytes_written,
                                'created': time.asctime(time.localtime(d.Started)),
                                'aborted': d.abort_flag,
                                'done': d.done_flag,
                                'eccmap': '' if not d.EccMap else d.EccMap.name,
                            }
                        )
            r['downloads'] = downloads
        result.append(r)
    if _Debug:
        lg.out(_DebugLevel, '    %d items returned' % len(result))
    return RESULT(
        result,
        extra_fields={
            'revision': backup_fs.revision(),
        },
    )


def file_exists(remote_path: str):
    """
    Returns positive result if file or folder with such `remote_path` already exists in the catalog.

    ###### HTTP
        curl -X GET 'localhost:8180/file/exists/v1?remote_path=abcd1234$alice@server-a.com:pictures/cats/pussy.png'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "file_exists", "kwargs": {"remote_path": "abcd1234$alice@server-a.com:pictures/cats/pussy.png"} }');
    """
    if not driver.is_on('service_backup_db'):
        return ERROR('service_backup_db() is not started')
    if _Debug:
        lg.out(_DebugLevel, 'api.file_exists remote_path=%s' % remote_path)
    from bitdust.storage import backup_fs
    from bitdust.system import bpio
    from bitdust.userid import global_id
    norm_path = global_id.NormalizeGlobalID(remote_path)
    remotePath = bpio.remotePath(norm_path['path'])
    customer_idurl = norm_path['idurl']
    if customer_idurl not in backup_fs.known_customers():
        return OK(
            {
                'exist': False,
                'path_id': None,
            },
            message='customer %s was not found' % customer_idurl,
        )
    pathID = backup_fs.ToID(remotePath, iter=backup_fs.fs(customer_idurl, norm_path['key_alias']))
    if not pathID:
        return OK(
            {
                'exist': False,
                'path_id': None,
            },
            message='path %s was not found in the catalog' % remotePath,
        )
    item = backup_fs.GetByID(pathID, iterID=backup_fs.fsID(customer_idurl, norm_path['key_alias']))
    if not item:
        return OK(
            {
                'exist': False,
                'path_id': None,
            },
            message='item %s was not found in the catalog' % pathID,
        )
    return OK({
        'exist': True,
        'path_id': pathID,
    }, )


def file_info(remote_path: str, include_uploads: bool = True, include_downloads: bool = True):
    """
    Returns detailed info about given file or folder in the catalog.

    You can also use `include_uploads` and `include_downloads` parameters to get more info about currently running
    uploads and downloads.

    ###### HTTP
        curl -X GET 'localhost:8180/file/info/v1?remote_path=abcd1234$alice@server-a.com:pictures/dogs/bobby.jpeg'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "file_info", "kwargs": {"remote_path": "abcd1234$alice@server-a.com:pictures/dogs/bobby.jpeg"} }');
    """
    if not driver.is_on('service_backup_db'):
        return ERROR('service_backup_db() is not started')
    if _Debug:
        lg.out(_DebugLevel, 'api.file_info remote_path=%s include_uploads=%s include_downloads=%s' % (remote_path, include_uploads, include_downloads))
    from bitdust.main import settings
    from bitdust.storage import backup_fs
    from bitdust.storage import backup_control
    from bitdust.lib import misc
    from bitdust.system import bpio
    from bitdust.userid import global_id
    norm_path = global_id.NormalizeGlobalID(remote_path)
    remotePath = bpio.remotePath(norm_path['path'])
    customer_idurl = norm_path['idurl']
    if customer_idurl not in backup_fs.known_customers():
        return ERROR('customer %s was not found' % customer_idurl)
    pathID = backup_fs.ToID(remotePath, iter=backup_fs.fs(customer_idurl, norm_path['key_alias']))
    if not pathID:
        return ERROR('path %s was not found in the catalog' % remotePath)
    item = backup_fs.GetByID(pathID, iterID=backup_fs.fsID(customer_idurl, norm_path['key_alias']))
    if not item:
        return ERROR('item %s was not found in the catalog' % pathID)
    backup_info_callback = None
    if driver.is_on('service_restores'):
        from bitdust.storage import restore_monitor
        backup_info_callback = restore_monitor.GetBackupStatusInfo
    (item_size, item_time, versions) = backup_fs.ExtractVersions(pathID, item, backup_info_callback=backup_info_callback)
    glob_path_item = norm_path.copy()
    glob_path_item['path'] = pathID
    key_alias = norm_path['key_alias']
    if item.key_id:
        key_alias = item.key_id.split('$')[0]
    r = {
        'remote_path': global_id.MakeGlobalID(
            path=norm_path['path'],
            customer=norm_path['customer'],
            key_alias=key_alias,
        ),
        'global_id': global_id.MakeGlobalID(
            path=pathID,
            customer=norm_path['customer'],
            key_alias=key_alias,
        ),
        'customer': norm_path['customer'],
        'path_id': pathID,
        'path': remotePath,
        'name': item.name(),
        'type': backup_fs.TYPES.get(item.type, '').lower(),
        'size': item_size,
        'latest': item_time,
        'key_id': item.key_id,
        'versions': versions,
        'uploads': {
            'running': [],
            'pending': [],
        },
        'downloads': [],
        'local_path': os.path.join(settings.getRestoreDir(), remotePath),
    }
    if include_uploads:
        backup_control.tasks()
        running = []
        for backupID in backup_control.FindRunningBackup(pathID=pathID):
            j = backup_control.jobs().get(backupID)
            if j:
                running.append(
                    {
                        'backup_id': j.backupID,
                        'key_id': j.keyID,
                        'source_path': j.sourcePath,
                        'eccmap': j.eccmap.name,
                        'pipe': 'closed' if not j.pipe else j.pipe.state(),
                        'block_size': j.blockSize,
                        'aborting': j.ask4abort,
                        'terminating': j.terminating,
                        'eof_state': j.stateEOF,
                        'reading': j.stateReading,
                        'closed': j.closed,
                        'work_blocks': len(j.workBlocks),
                        'block_number': j.blockNumber,
                        'bytes_processed': j.dataSent,
                        'progress': misc.percent2string(j.progress()),
                        'total_size': j.totalSize,
                    }
                )
        pending = []
        t = backup_control.GetPendingTask(pathID)
        if t:
            pending.append({
                'task_id': t.number,
                'path_id': t.pathID,
                'source_path': t.localPath,
                'created': time.asctime(time.localtime(t.created)),
            })
        r['uploads']['running'] = running
        r['uploads']['pending'] = pending
    if include_downloads:
        downloads = []
        if driver.is_on('service_restores'):
            for backupID in restore_monitor.FindWorking(pathID=pathID):
                d = restore_monitor.GetWorkingRestoreObject(backupID)
                if d:
                    downloads.append(
                        {
                            'backup_id': d.backup_id,
                            'creator_id': d.creator_id,
                            'path_id': d.path_id,
                            'version': d.version,
                            'block_number': d.block_number,
                            'bytes_processed': d.bytes_written,
                            'created': time.asctime(time.localtime(d.Started)),
                            'aborted': d.abort_flag,
                            'done': d.done_flag,
                            'eccmap': '' if not d.EccMap else d.EccMap.name,
                        }
                    )
        r['downloads'] = downloads
    if _Debug:
        lg.out(_DebugLevel, 'api.file_info : %r' % pathID)
    r['revision'] = backup_fs.revision()
    return OK(r)


def file_create(remote_path: str, as_folder: bool = False, exist_ok: bool = False, force_path_id: str = None):
    """
    Creates new file in the catalog, but do not upload any data to the network yet.

    This method only creates a "virtual ID" for the new data.

    Pass `as_folder=True` to create a virtual folder instead of a file.

    ###### HTTP
        curl -X POST 'localhost:8180/file/create/v1' -d '{"remote_path": "abcd1234$alice@server-a.com:movies/travels/safari.mp4"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "file_create", "kwargs": {"remote_path": "abcd1234$alice@server-a.com:movies/travels/safari.mp4"} }');
    """
    if not driver.is_on('service_backup_db'):
        return ERROR('service_backup_db() is not started')
    from bitdust.storage import backup_fs
    from bitdust.storage import backup_control
    from bitdust.system import bpio
    from bitdust.main import listeners
    from bitdust.crypt import my_keys
    from bitdust.userid import id_url
    from bitdust.userid import global_id
    from bitdust.userid import my_id
    parts = global_id.NormalizeGlobalID(remote_path)
    if not parts['path']:
        if _Debug:
            lg.args(_DebugLevel, remote_path=remote_path, inp=parts)
        return ERROR('invalid "remote_path" format')
    path = bpio.remotePath(parts['path'])
    customer_idurl = parts['idurl']
    keyID = my_keys.make_key_id(alias=parts['key_alias'], creator_glob_id=parts['customer'])
    key_alias = parts['key_alias']
    pathID = backup_fs.ToID(path, iter=backup_fs.fs(customer_idurl, key_alias))
    itemInfo = None
    if _Debug:
        lg.args(_DebugLevel, remote_path=remote_path, as_folder=as_folder, path_id=pathID, customer_idurl=customer_idurl, force_path_id=force_path_id)
    if pathID is not None:
        if exist_ok:
            fullRemotePath = global_id.MakeGlobalID(customer=parts['customer'], path=parts['path'], key_alias=key_alias)
            fullGlobID = global_id.MakeGlobalID(customer=parts['customer'], path=pathID, key_alias=key_alias)
            return OK(
                {
                    'path_id': pathID,
                    'key_id': keyID,
                    'path': path,
                    'remote_path': fullRemotePath,
                    'global_id': fullGlobID,
                    'customer': customer_idurl,
                    'created': False,
                    'type': ('dir' if as_folder else 'file'),
                },
                message='remote path %s already exists in the catalog: %s' % (('folder' if as_folder else 'file'), fullGlobID),
            )
        return ERROR('remote path %s already exists in the catalog: %s' % (path, pathID))
    if as_folder:
        newPathID, itemInfo, _, _ = backup_fs.AddDir(
            path,
            read_stats=False,
            iter=backup_fs.fs(customer_idurl, key_alias),
            iterID=backup_fs.fsID(customer_idurl, key_alias),
            key_id=keyID,
            force_path_id=force_path_id,
        )
    else:
        parent_path = os.path.dirname(path)
        if not backup_fs.IsDir(parent_path, iter=backup_fs.fs(customer_idurl, key_alias)):
            if backup_fs.IsFile(parent_path, iter=backup_fs.fs(customer_idurl, key_alias)):
                return ERROR('remote path can not be assigned, file %s already exists' % parent_path)
            parentPathID, _, _, _ = backup_fs.AddDir(
                parent_path,
                read_stats=False,
                iter=backup_fs.fs(customer_idurl, key_alias),
                iterID=backup_fs.fsID(customer_idurl, key_alias),
                key_id=keyID,
            )
            if _Debug:
                lg.out(_DebugLevel, 'api.file_create parent folder %r was created at %r' % (parent_path, parentPathID))
        id_iter_iterID = backup_fs.GetIteratorsByPath(
            parent_path,
            iter=backup_fs.fs(customer_idurl, key_alias),
            iterID=backup_fs.fsID(customer_idurl, key_alias),
        )
        if not id_iter_iterID:
            return ERROR('remote path can not be assigned, parent folder %s was not found' % parent_path)
        parentPathID = id_iter_iterID[0]
        newPathID, itemInfo, _, _ = backup_fs.PutItem(
            name=os.path.basename(path),
            parent_path_id=parentPathID,
            as_folder=as_folder,
            iter=id_iter_iterID[1],
            iterID=id_iter_iterID[2],
            key_id=keyID,
        )
        if not newPathID:
            return ERROR('remote path can not be assigned, failed to create new item %s' % path)
    backup_control.SaveFSIndex(customer_idurl, key_alias)
    full_glob_id = global_id.MakeGlobalID(customer=parts['customer'], path=newPathID, key_alias=key_alias)
    full_remote_path = global_id.MakeGlobalID(customer=parts['customer'], path=parts['path'], key_alias=key_alias)
    if id_url.is_the_same(customer_idurl, my_id.getIDURL()) and key_alias == 'master':
        snapshot = dict(
            global_id=full_glob_id,
            remote_path=full_remote_path,
            size=max(0, itemInfo.size),
            type=backup_fs.TYPES.get(itemInfo.type, 'unknown').lower(),
            customer=parts['customer'],
            versions=[],
        )
        listeners.push_snapshot('private_file', snap_id=full_glob_id, data=snapshot)
    else:
        snapshot = dict(
            global_id=full_glob_id,
            remote_path=full_remote_path,
            size=max(0, itemInfo.size),
            type=backup_fs.TYPES.get(itemInfo.type, 'unknown').lower(),
            customer=parts['customer'],
            versions=[],
        )
        listeners.push_snapshot('shared_file', snap_id=full_glob_id, data=snapshot)
    if _Debug:
        lg.out(_DebugLevel, 'api.file_create : %r' % full_glob_id)
    return OK(
        {
            'path_id': newPathID,
            'key_id': keyID,
            'path': path,
            'remote_path': full_remote_path,
            'global_id': full_glob_id,
            'customer': parts['idurl'],
            'created': True,
            'type': ('dir' if as_folder else 'file'),
        },
        message='new %s created in %s successfully' % (('folder' if as_folder else 'file'), full_glob_id),
    )


def file_delete(remote_path: str):
    """
    Removes virtual file or folder from the catalog and also notifies your remote suppliers to clean up corresponding uploaded data.

    ###### HTTP
        curl -X DELETE 'localhost:8180/file/delete/v1' -d '{"remote_path": "abcd1234$alice@server-a.com:cars/ferrari.gif"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "file_delete", "kwargs": {"remote_path": "abcd1234$alice@server-a.com:cars/ferrari.gif"} }');
    """
    if not driver.is_on('service_backup_db'):
        return ERROR('service_backup_db() is not started')
    if _Debug:
        lg.out(_DebugLevel, 'api.file_delete remote_path=%s' % remote_path)
    from bitdust.storage import backup_fs
    from bitdust.storage import backup_control
    from bitdust.storage import backup_monitor
    from bitdust.main import settings
    from bitdust.main import listeners
    from bitdust.lib import packetid
    from bitdust.system import bpio
    from bitdust.userid import global_id
    from bitdust.userid import id_url
    from bitdust.userid import my_id
    parts = global_id.NormalizeGlobalID(remote_path)
    if not parts['idurl'] or not parts['path']:
        return ERROR('invalid "remote_path" format')
    path = bpio.remotePath(parts['path'])
    customer_idurl = parts['idurl']
    key_alias = parts['key_alias']
    pathID = backup_fs.ToID(path, iter=backup_fs.fs(customer_idurl, key_alias))
    if not pathID:
        return ERROR('remote path %s was not found' % parts['path'])
    if not packetid.Valid(pathID):
        return ERROR('invalid item found: %s' % pathID)
    itemInfo = backup_fs.GetByID(pathID, iterID=backup_fs.fsID(customer_idurl, key_alias))
    pathIDfull = packetid.MakeBackupID(customer=parts['customer'], path_id=pathID, key_alias=key_alias)
    full_glob_id = global_id.MakeGlobalID(customer=parts['customer'], path=pathID, key_alias=key_alias)
    full_remote_path = global_id.MakeGlobalID(customer=parts['customer'], path=parts['path'], key_alias=key_alias)
    result = backup_control.DeletePathBackups(pathID=pathIDfull, saveDB=False, calculate=False)
    if not result:
        return ERROR('remote item %s was not found' % pathIDfull)
    backup_fs.DeleteLocalDir(settings.getLocalBackupsDir(), pathIDfull)
    backup_fs.DeleteByID(pathID, iter=backup_fs.fs(customer_idurl, key_alias), iterID=backup_fs.fsID(customer_idurl, key_alias))
    backup_fs.Scan(customer_idurl=customer_idurl, key_alias=key_alias)
    backup_fs.Calculate(customer_idurl=customer_idurl, key_alias=key_alias)
    if key_alias != 'master':
        if driver.is_on('service_shared_data'):
            from bitdust.access import shared_access_coordinator
            shared_access_coordinator.on_file_deleted(customer_idurl, key_alias, pathID)
    backup_control.SaveFSIndex(customer_idurl, key_alias)
    backup_monitor.A('restart')
    if id_url.is_the_same(parts['idurl'], my_id.getIDURL()) and key_alias == 'master':
        snapshot = dict(
            global_id=full_glob_id,
            remote_path=full_remote_path,
            size=0 if not itemInfo else itemInfo.size,
            type='file' if not itemInfo else backup_fs.TYPES.get(itemInfo.type, 'unknown').lower(),
            customer=parts['customer'],
            versions=[],
        )
        listeners.push_snapshot('private_file', snap_id=full_glob_id, deleted=True, data=snapshot)
    else:
        snapshot = dict(
            global_id=full_glob_id,
            remote_path=full_remote_path,
            size=0 if not itemInfo else itemInfo.size,
            type='file' if not itemInfo else backup_fs.TYPES.get(itemInfo.type, 'unknown').lower(),
            customer=parts['customer'],
            versions=[],
        )
        listeners.push_snapshot('shared_file', snap_id=full_glob_id, deleted=True, data=snapshot)
    if _Debug:
        lg.out(_DebugLevel, 'api.file_delete %s' % parts)
    return OK(
        {
            'path_id': pathIDfull,
            'path': path,
            'remote_path': full_remote_path,
            'global_id': full_glob_id,
            'customer': parts['idurl'],
        },
        message='item %s was deleted from remote suppliers' % pathIDfull,
    )


def files_uploads(include_running: bool = True, include_pending: bool = True):
    """
    Returns a list of currently running uploads and list of pending items to be uploaded.

    ###### HTTP
        curl -X GET 'localhost:8180/file/upload/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "files_uploads", "kwargs": {} }');
    """
    if not driver.is_on('service_backups'):
        return ERROR('service_backups() is not started')
    from bitdust.lib import misc
    from bitdust.storage import backup_control
    if _Debug:
        lg.out(_DebugLevel, 'api.file_uploads include_running=%s include_pending=%s' % (include_running, include_pending))
        lg.out(_DebugLevel, '     %d jobs running, %d tasks pending' % (len(backup_control.jobs()), len(backup_control.tasks())))
    r = {
        'running': [],
        'pending': [],
    }
    if include_running:
        r['running'].extend(
            [
                {
                    'version': j.backupID,
                    'key_id': j.keyID,
                    'source_path': j.sourcePath,
                    'eccmap': j.eccmap.name,
                    'pipe': 'closed' if not j.pipe else j.pipe.state(),
                    'block_size': j.blockSize,
                    'aborting': j.ask4abort,
                    'terminating': j.terminating,
                    'eof_state': j.stateEOF,
                    'reading': j.stateReading,
                    'closed': j.closed,
                    'work_blocks': len(j.workBlocks),
                    'block_number': j.blockNumber,
                    'bytes_processed': j.dataSent,
                    'progress': misc.percent2string(j.progress()),
                    'total_size': j.totalSize,
                } for j in backup_control.jobs().values()
            ]
        )
    if include_pending:
        r['pending'].extend([{
            'task_id': t.number,
            'path_id': t.pathID,
            'source_path': t.localPath,
            'created': time.asctime(time.localtime(t.created)),
        } for t in backup_control.tasks()])
    return RESULT(r)


def file_upload_start(local_path: str, remote_path: str, wait_result: bool = False, publish_events: bool = False):
    """
    Starts a new file or folder (including all sub-folders and files) upload from `local_path` on your disk drive
    to the virtual location `remote_path` in the catalog. New "version" of the data will be created for given catalog item
    and uploading task started.

    You can use `wait_result=True` to block the response from that method until uploading finishes or fails (makes no sense for large uploads).

    ###### HTTP
        curl -X POST 'localhost:8180/file/upload/start/v1' -d '{"remote_path": "abcd1234$alice@server-a.com:cars/fiat.jpeg", "local_path": "/tmp/fiat.jpeg"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "file_upload_start", "kwargs": {"remote_path": "abcd1234$alice@server-a.com:cars/fiat.jpeg", "local_path": "/tmp/fiat.jpeg"} }');
    """
    if not driver.is_on('service_backups'):
        return ERROR('service_backups() is not started')
    if _Debug:
        lg.out(_DebugLevel, 'api.file_upload_start local_path=%s remote_path=%s wait_result=%s' % (local_path, remote_path, wait_result))
    from bitdust.system import bpio
    from bitdust.storage import backup_fs
    from bitdust.storage import backup_control
    from bitdust.lib import packetid
    from bitdust.userid import global_id
    from bitdust.crypt import my_keys
    if not bpio.pathExist(local_path):
        return ERROR('local file or folder %s not exist' % local_path)
    parts = global_id.NormalizeGlobalID(remote_path)
    if not parts['idurl'] or not parts['path']:
        return ERROR('invalid "remote_path" format')
    customer_idurl = parts['idurl']
    key_alias = parts['key_alias']
    if key_alias == 'master':
        is_hidden_item = parts['path'].startswith('.')
        if not is_hidden_item:
            if not driver.is_on('service_my_data'):
                return ERROR('service_my_data() is not started')
    path = bpio.remotePath(parts['path'])
    pathID = backup_fs.ToID(path, iter=backup_fs.fs(customer_idurl, key_alias))
    if not pathID:
        return ERROR('path %s was not registered yet' % remote_path)
    keyID = my_keys.make_key_id(alias=key_alias, creator_glob_id=parts['customer'])
    pathIDfull = packetid.MakeBackupID(keyID, pathID)
    if key_alias != 'master':
        if not driver.is_on('service_shared_data'):
            return ERROR('service_shared_data() is not started')
    if wait_result:
        task_created_defer = Deferred()
        tsk = backup_control.StartSingle(
            pathID=pathIDfull,
            localPath=local_path,
            keyID=keyID,
        )
        tsk.result_defer.addCallback(
            lambda result: task_created_defer.callback(
                OK(
                    {
                        'remote_path': remote_path,
                        'version': result[0],
                        'key_id': tsk.keyID,
                        'source_path': local_path,
                        'path_id': pathID,
                    },
                    message='item %s was uploaded, local path is: %s' % (remote_path, local_path),
                    api_method='file_upload_start',
                )
            )
        )
        tsk.result_defer.addErrback(lambda result: task_created_defer.callback(ERROR(result, api_method='file_upload_start')))
        # tsk.result_defer.addErrback(lambda result: task_created_defer.callback(ERROR(
        #     'uploading task %d for %s failed: %s' % (
        #         tsk.number,
        #         tsk.pathID,
        #         result,
        #     ),
        #     api_method='file_upload_start',
        # ), ), )
        backup_fs.Calculate(customer_idurl=customer_idurl, key_alias=key_alias)
        backup_control.SaveFSIndex(customer_idurl, key_alias)
        if _Debug:
            lg.out(_DebugLevel, 'api.file_upload_start %s with %s, wait_result=True' % (remote_path, pathIDfull))
        return task_created_defer

    tsk = backup_control.StartSingle(
        pathID=pathIDfull,
        localPath=local_path,
        keyID=keyID,
    )
    tsk.result_defer.addErrback(lambda result: lg.err('errback from api.file_upload_start.task() failed with %r' % result))
    backup_fs.Calculate(customer_idurl=customer_idurl, key_alias=key_alias)
    backup_control.SaveFSIndex(customer_idurl, key_alias)
    if _Debug:
        lg.out(_DebugLevel, 'api.file_upload_start %s with %s' % (remote_path, pathIDfull))
    return OK(
        {
            'remote_path': remote_path,
            'key_id': tsk.keyID,
            'source_path': local_path,
            'path_id': pathID,
        },
        message='uploading task for %s started, local path is %s' % (remote_path, local_path),
    )


def file_upload_stop(remote_path: str):
    """
    Useful method if you need to interrupt and cancel already running uploading task.

    ###### HTTP
        curl -X POST 'localhost:8180/file/upload/stop/v1' -d '{"remote_path": "abcd1234$alice@server-a.com:cars/fiat.jpeg"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "file_upload_stop", "kwargs": {"remote_path": "abcd1234$alice@server-a.com:cars/fiat.jpeg"} }');
    """
    if not driver.is_on('service_backups'):
        return ERROR('service_backups() is not started')
    if _Debug:
        lg.out(_DebugLevel, 'api.file_upload_stop remote_path=%s' % remote_path)
    from bitdust.storage import backup_control
    from bitdust.storage import backup_fs
    from bitdust.system import bpio
    from bitdust.userid import global_id
    from bitdust.lib import packetid
    parts = global_id.NormalizeGlobalID(remote_path)
    if not parts['idurl'] or not parts['path']:
        return ERROR('invalid "remote_path" format')
    remotePath = bpio.remotePath(parts['path'])
    customer_idurl = parts['idurl']
    key_alias = parts['key_alias']
    pathID = backup_fs.ToID(remotePath, iter=backup_fs.fs(customer_idurl, key_alias))
    if not pathID:
        return ERROR('remote path %s was not found' % parts['path'])
    if not packetid.Valid(pathID):
        return ERROR('invalid item was found: %s' % pathID)
    pathIDfull = packetid.MakeBackupID(customer=parts['customer'], path_id=pathID, key_alias=key_alias)
    r = []
    msg = []
    if backup_control.AbortPendingTask(pathIDfull):
        r.append(pathIDfull)
        msg.append('pending item %s was removed' % pathIDfull)
    for backupID in backup_control.FindRunningBackup(pathIDfull):
        if backup_control.AbortRunningBackup(backupID):
            r.append(backupID)
            msg.append('uploading task %s was aborted' % backupID)
    if not r:
        return ERROR('no running or pending tasks for path %s were found' % pathIDfull)
    if _Debug:
        lg.out(_DebugLevel, 'api.file_upload_stop %s' % r)
    return RESULT(r, message=(', '.join(msg)))


def files_downloads():
    """
    Returns a list of currently running downloading tasks.

    ###### HTTP
        curl -X GET 'localhost:8180/file/download/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "files_downloads", "kwargs": {} }');
    """
    if not driver.is_on('service_backups'):
        return ERROR('service_backups() is not started')
    from bitdust.storage import restore_monitor
    return RESULT(
        [
            {
                'backup_id': r.backup_id,
                'creator_id': r.creator_id,
                'path_id': r.path_id,
                'version': r.version,
                'block_number': r.block_number,
                'bytes_processed': r.bytes_written,
                'created': time.asctime(time.localtime(r.Started)),
                'aborted': r.abort_flag,
                'done': r.done_flag,
                'key_id': r.key_id,
                'eccmap': '' if not r.EccMap else r.EccMap.name,
            } for r in restore_monitor.GetWorkingObjects()
        ]
    )


def file_download_start(remote_path: str, destination_path: str = None, wait_result: bool = False, publish_events: bool = False):
    """
    Download data from remote suppliers to your local machine.

    You can use different methods to select the target data with `remote_path` input:

      + "virtual" path of the file
      + internal path ID in the catalog
      + full data version identifier with path ID and version name

    It is possible to select the destination folder to extract requested files to.
    By default this method uses specified value from `paths/restore` program setting or user home folder.

    You can use `wait_result=True` to block the response from that method until downloading finishes or fails (makes no sense for large files).

    WARNING! Your existing local data in `destination_path` will be overwritten!

    ###### HTTP
        curl -X POST 'localhost:8180/file/download/start/v1' -d '{"remote_path": "abcd1234$alice@server-a.com:movies/back_to_the_future.mp4", "destination_path": "/tmp/films/"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "file_download_start", "kwargs": {"remote_path": "abcd1234$alice@server-a.com:movies/back_to_the_future.mp4", "destination_path": "/tmp/films/"} }');
    """
    if not driver.is_on('service_restores'):
        return ERROR('service_restores() is not started')
    from bitdust.storage import backup_fs
    from bitdust.storage import backup_control
    from bitdust.storage import restore_monitor
    from bitdust.system import bpio
    from bitdust.system import tmpfile
    from bitdust.lib import packetid
    # from bitdust.main import settings
    from bitdust.userid import my_id
    from bitdust.userid import global_id
    from bitdust.crypt import my_keys
    glob_path = global_id.NormalizeGlobalID(remote_path)
    customer_idurl = glob_path['idurl']
    key_alias = glob_path['key_alias']
    if glob_path['key_alias'] == 'master':
        is_hidden_item = glob_path['path'].startswith('.')
        if not is_hidden_item:
            if not driver.is_on('service_my_data'):
                return ERROR('service_my_data() is not started')
    else:
        if not driver.is_on('service_shared_data'):
            return ERROR('service_shared_data() is not started')
    if packetid.Valid(glob_path['path']):
        _, pathID, version = packetid.SplitBackupID(remote_path)
        if not pathID and version:
            pathID, version = version, ''
        item = backup_fs.GetByID(pathID, iterID=backup_fs.fsID(customer_idurl, key_alias))
        if not item:
            return ERROR('path %s was not found in the catalog' % remote_path)
        if not version:
            version = item.get_latest_version()
        if not version:
            return ERROR('no remotely stored versions found')
        if item.key_id:
            key_alias = packetid.KeyAlias(item.key_id)
        customerGlobalID = global_id.MakeGlobalID(customer=glob_path['customer'], key_alias=key_alias)
        backupID = packetid.MakeBackupID(customerGlobalID, pathID, version)
    else:
        remotePath = bpio.remotePath(glob_path['path'])
        knownPathID = backup_fs.ToID(remotePath, iter=backup_fs.fs(customer_idurl, key_alias))
        if not knownPathID:
            return ERROR('path %s was not found in the catalog' % remotePath)
        item = backup_fs.GetByID(knownPathID, iterID=backup_fs.fsID(customer_idurl, key_alias))
        if not item:
            return ERROR('item %s was not found in the catalog' % knownPathID)
        version = glob_path['version']
        if not version:
            version = item.get_latest_version()
        if not version:
            return ERROR('no remotely stored versions found')
        if item.key_id:
            key_alias = packetid.KeyAlias(item.key_id)
        customerGlobalID = global_id.MakeGlobalID(customer=glob_path['customer'], key_alias=key_alias)
        backupID = packetid.MakeBackupID(customerGlobalID, knownPathID, version)
    if backup_control.IsBackupInProcess(backupID):
        return ERROR('downloading is not possible, uploading task %s is currently in progress' % backupID)
    if restore_monitor.IsWorking(backupID):
        return ERROR('downloading task %s was already scheduled' % backupID)
    keyAlias, customerGlobalID, pathID_target, version = packetid.SplitBackupIDFull(backupID)
    if not customerGlobalID:
        customerGlobalID = global_id.UrlToGlobalID(my_id.getIDURL())
    knownPath = backup_fs.ToPath(pathID_target, iterID=backup_fs.fsID(
        customer_idurl=global_id.GlobalUserToIDURL(customerGlobalID),
        key_alias=keyAlias,
    ))
    if not knownPath:
        return ERROR('location %s was not found in the catalog' % knownPath)
    # if not destination_path:
    #     destination_path = settings.getRestoreDir()
    # if not destination_path:
    #     destination_path = settings.DefaultRestoreDir()
    if not destination_path:
        destination_path = tmpfile.make_dir('download')
    key_id = my_keys.make_key_id(alias=keyAlias, creator_glob_id=customerGlobalID)
    ret = Deferred()

    def _on_result(backupID, result):
        if result == 'restore done':
            ret.callback(
                OK(
                    {
                        'downloaded': True,
                        'key_id': key_id,
                        'backup_id': backupID,
                        'local_path': os.path.join(destination_path, glob_path['path']),
                        'path_id': pathID_target,
                        'remote_path': knownPath,
                    },
                    message='version %s downloaded to %s successfully' % (backupID, destination_path),
                    api_method='file_download_start',
                )
            )
        else:
            ret.callback(
                ERROR(
                    'downloading task %s failed, result is %s' % (backupID, result),
                    details={
                        'downloaded': False,
                        'key_id': key_id,
                        'backup_id': backupID,
                        'local_path': os.path.join(destination_path, glob_path['path']),
                        'path_id': pathID_target,
                        'remote_path': knownPath,
                    },
                    api_method='file_download_start',
                )
            )
        return True

    def _start_restore():
        if _Debug:
            lg.out(_DebugLevel, 'api.file_download_start._start_restore %s to %s, wait_result=%s' % (backupID, destination_path, wait_result))
        if wait_result:
            restore_monitor.Start(backupID, destination_path, keyID=key_id, callback=_on_result)
            return ret
        restore_monitor.Start(backupID, destination_path, keyID=key_id)
        ret.callback(
            OK(
                {
                    'downloaded': False,
                    'key_id': key_id,
                    'backup_id': backupID,
                    'local_path': os.path.join(destination_path, glob_path['path']),
                    'path_id': pathID_target,
                    'remote_path': knownPath,
                },
                message='downloading task %s started, destination is %s' % (backupID, destination_path),
                api_method='file_download_start',
            )
        )
        return True

    def _on_share_connected(active_share, callback_id, result):
        if _Debug:
            lg.out(_DebugLevel, 'api.download_start._on_share_connected callback_id=%s result=%s' % (callback_id, result))
        if not result:
            if _Debug:
                lg.out(_DebugLevel, '    share %s is now DISCONNECTED, removing callback %s' % (active_share.key_id, callback_id))
            active_share.remove_connected_callback(callback_id)
            ret.callback(
                ERROR(
                    'downloading task %s failed, result is: %s' % (backupID, 'share is disconnected'),
                    details={
                        'key_id': active_share.key_id,
                        'backup_id': backupID,
                        'local_path': os.path.join(destination_path, glob_path['path']),
                        'path_id': pathID_target,
                        'remote_path': knownPath,
                    },
                )
            )
            return True
        if _Debug:
            lg.out(_DebugLevel, '        share %s is now CONNECTED, removing callback %s and starting restore process' % (active_share.key_id, callback_id))
        reactor.callLater(0, active_share.remove_connected_callback, callback_id)  # @UndefinedVariable
        _start_restore()
        return True

    def _open_share():
        if not driver.is_on('service_shared_data'):
            ret.callback(ERROR('service_shared_data() is not started'))
            return False
        from bitdust.access import shared_access_coordinator
        active_share = shared_access_coordinator.get_active_share(key_id)
        if not active_share:
            active_share = shared_access_coordinator.SharedAccessCoordinator(
                key_id=key_id,
                log_events=True,
                publish_events=publish_events,
            )
            if _Debug:
                lg.out(_DebugLevel, 'api.download_start._open_share opened new share : %s' % active_share.key_id)
        else:
            if _Debug:
                lg.out(_DebugLevel, 'api.download_start._open_share found existing share : %s' % active_share.key_id)
        if active_share.state != 'CONNECTED':
            cb_id = 'file_download_start_' + strng.to_text(time.time())
            active_share.add_connected_callback(cb_id, lambda _id, _result: _on_share_connected(active_share, _id, _result))
            active_share.automat('restart')
            if _Debug:
                lg.out(_DebugLevel, 'api.download_start._open_share added callback %s to the active share : %s' % (cb_id, active_share.key_id))
        else:
            if _Debug:
                lg.out(_DebugLevel, 'api.download_start._open_share existing share %s is currently CONNECTED' % active_share.key_id)
            _start_restore()
        return True

    if key_alias != 'master':
        _open_share()
    else:
        _start_restore()

    return ret


def file_download_stop(remote_path: str):
    """
    Abort currently running restore process.

    ###### HTTP
        curl -X POST 'localhost:8180/file/download/stop/v1' -d '{"remote_path": "abcd1234$alice@server-a.com:cars/fiat.jpeg"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "file_download_stop", "kwargs": {"remote_path": "abcd1234$alice@server-a.com:cars/fiat.jpeg"} }');
    """
    if not driver.is_on('service_restores'):
        return ERROR('service_restores() is not started')
    if _Debug:
        lg.out(_DebugLevel, 'api.file_download_stop remote_path=%s' % remote_path)
    from bitdust.storage import backup_fs
    from bitdust.storage import restore_monitor
    from bitdust.system import bpio
    from bitdust.lib import packetid
    from bitdust.userid import my_id
    from bitdust.userid import global_id
    glob_path = global_id.NormalizeGlobalID(remote_path)
    customer_idurl = glob_path['idurl']
    key_alias = glob_path['key_alias']
    backupIDs = []
    if packetid.Valid(glob_path['path']):
        customerGlobalID, pathID, version = packetid.SplitBackupID(remote_path)
        if not customerGlobalID:
            customerGlobalID = global_id.UrlToGlobalID(my_id.getIDURL())
        item = backup_fs.GetByID(pathID, iterID=backup_fs.fsID(customer_idurl, key_alias))
        if not item:
            return ERROR('path %s was not found in the catalog' % remote_path)
        versions = []
        if version:
            versions.append(version)
        if not versions:
            versions.extend(item.get_versions())
        for version in versions:
            backupIDs.append(packetid.MakeBackupID(customerGlobalID, pathID, version, key_alias=key_alias))
    else:
        remotePath = bpio.remotePath(glob_path['path'])
        knownPathID = backup_fs.ToID(remotePath, iter=backup_fs.fs(customer_idurl, key_alias))
        if not knownPathID:
            return ERROR('path %s was not found in the catalog' % remotePath)
        item = backup_fs.GetByID(knownPathID, iterID=backup_fs.fsID(customer_idurl, key_alias))
        if not item:
            return ERROR('item %s was not found in the catalog' % knownPathID)
        versions = []
        if glob_path['version']:
            versions.append(glob_path['version'])
        if not versions:
            versions.extend(item.get_versions())
        for version in versions:
            backupIDs.append(packetid.MakeBackupID(glob_path['customer'], knownPathID, version, key_alias=key_alias))
    if not backupIDs:
        return ERROR('no remotely stored versions found')
    r = []
    for backupID in backupIDs:
        r.append({
            'backup_id': backupID,
            'aborted': restore_monitor.Abort(backupID),
        })
    if _Debug:
        lg.out(_DebugLevel, '    stopping %s' % r)
    return RESULT(r)


def file_explore(local_path: str):
    """
    Useful method to be executed from inside of the UI application right after downloading is finished.

    It will open default OS file manager and display
    given `local_path` to the user so he can do something with the file.

    ###### HTTP
        curl -X GET 'localhost:8180/file/explore/v1?local_path=/tmp/movies/back_to_the_future.mp4'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "file_explore", "kwargs": {"local_path": "/tmp/movies/back_to_the_future.mp4"} }');
    """
    from bitdust.lib import misc
    from bitdust.system import bpio
    locpath = bpio.portablePath(local_path)
    if not bpio.pathExist(locpath):
        return ERROR('local path not exist')
    misc.ExplorePathInOS(locpath)
    return OK(message='system file explorer opened')


#------------------------------------------------------------------------------


def shares_list(only_active: bool = False, include_mine: bool = True, include_granted: bool = True):
    """
    Returns a list of registered "shares" - encrypted locations where you can upload/download files.

    Use `only_active=True` to select only connected shares.

    Parameters `include_mine` and `include_granted` can be used to filter shares created by you,
    or by other users that shared a key with you before.

    ###### HTTP
        curl -X GET 'localhost:8180/share/list/v1?only_active=1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "shares_list", "kwargs": {"only_active": 1} }');
    """
    if not driver.is_on('service_shared_data'):
        return ERROR('service_shared_data() is not started')
    from bitdust.access import shared_access_coordinator
    from bitdust.storage import backup_fs
    from bitdust.crypt import my_keys
    from bitdust.userid import global_id
    from bitdust.userid import id_url
    from bitdust.userid import my_id
    results = []
    if only_active:
        for key_id in shared_access_coordinator.list_active_shares():
            _glob_id = global_id.ParseGlobalID(key_id)
            if not id_url.is_cached(_glob_id['idurl']):
                continue
            to_be_listed = False
            if include_mine and _glob_id['idurl'] == my_id.getIDURL():
                to_be_listed = True
            if include_granted and _glob_id['idurl'] != my_id.getIDURL():
                to_be_listed = True
            if not to_be_listed:
                continue
            cur_share = shared_access_coordinator.get_active_share(key_id)
            if not cur_share:
                lg.warn('share %s was not found' % key_id)
                continue
            results.append(cur_share.to_json())
        return RESULT(results)
    for key_id in my_keys.known_keys():
        if not key_id.startswith('share_'):
            continue
        key_alias, creator_idurl = my_keys.split_key_id(key_id)
        if not id_url.is_cached(creator_idurl):
            continue
        to_be_listed = False
        if include_mine and creator_idurl == my_id.getIDURL():
            to_be_listed = True
        if include_granted and creator_idurl != my_id.getIDURL():
            to_be_listed = True
        if not to_be_listed:
            continue
        one_share = shared_access_coordinator.get_active_share(key_id)
        if one_share:
            r = one_share.to_json()
        else:
            r = {
                'active': my_keys.is_active(key_id),
                'key_id': key_id,
                'alias': key_alias,
                'label': my_keys.get_label(key_id) or '',
                'creator': creator_idurl.to_id(),
                'suppliers': [],
                'ecc_map': None,
                'revision': backup_fs.revision(creator_idurl, key_alias),
                'index': None,
                'id': None,
                'name': None,
                'state': None,
            }
        results.append(r)
    return RESULT(results)


def share_info(key_id: str):
    """
    Returns detailed info about given shared location.

    ###### HTTP
        curl -X GET 'localhost:8180/share/info/v1?key_id=share_7e9726e2dccf9ebe6077070e98e78082$alice@server-a.com'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "share_info", "kwargs": {"key_id": "share_7e9726e2dccf9ebe6077070e98e78082$alice@server-a.com"} }');
    """
    key_id = strng.to_text(key_id)
    if not driver.is_on('service_shared_data'):
        return ERROR('service_shared_data() is not started')
    if not key_id.startswith('share_'):
        return ERROR('invalid share id')
    from bitdust.crypt import my_keys
    from bitdust.access import shared_access_coordinator
    from bitdust.storage import backup_fs
    from bitdust.userid import global_id
    if not my_keys.is_active(key_id):
        glob_id = global_id.NormalizeGlobalID(key_id)
        return OK(
            {
                'active': False,
                'key_id': key_id,
                'alias': glob_id['key_alias'],
                'label': my_keys.get_label(key_id) or '',
                'creator': glob_id['idurl'].to_id(),
                'suppliers': [],
                'ecc_map': None,
                'revision': backup_fs.revision(glob_id['idurl'], glob_id['key_alias']),
                'index': None,
                'id': None,
                'name': None,
                'state': None,
            }
        )
    this_share = shared_access_coordinator.get_active_share(key_id)
    if not this_share:
        return OK(
            {
                'active': my_keys.is_active(key_id),
                'key_id': key_id,
                'alias': glob_id['key_alias'],
                'label': my_keys.get_label(key_id) or '',
                'creator': glob_id['idurl'].to_id(),
                'suppliers': None,
                'ecc_map': None,
                'revision': backup_fs.revision(glob_id['idurl'], glob_id['key_alias']),
                'index': None,
                'id': None,
                'name': None,
                'state': None,
            }
        )
    return OK(this_share.to_json())


def share_create(owner_id: str = None, key_size: int = None, label: str = '', active: bool = True):
    """
    Creates a new "share" - virtual location where you or other users can upload/download files.

    This method generates a new RSA private key that will be used to encrypt and decrypt files stored inside that share.

    By default you are the owner of the new share and uploaded files will be stored by your suppliers.
    You can also use `owner_id` parameter if you wish to set another owner for that new share location.
    In that case files will be stored not on your suppliers but on his/her suppliers, if another user authorized the share.

    Optional input parameter `key_size` can be 1024, 2048, 4096. If `key_size` was not passed, default value will be
    populated from the `personal/private-key-size` program setting.

    Parameter `label` can be used to attach some meaningful information about that share location.

    ###### HTTP
        curl -X POST 'localhost:8180/share/create/v1' -d '{"label": "my summer holidays"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "share_create", "kwargs": {"label": "my summer holidays"} }');
    """
    if not driver.is_on('service_shared_data'):
        return ERROR('service_shared_data() is not started')
    from bitdust.lib import utime
    from bitdust.main import settings
    from bitdust.crypt import key
    from bitdust.crypt import my_keys
    from bitdust.storage import backup_fs
    from bitdust.userid import global_id
    from bitdust.userid import my_id
    if not owner_id:
        owner_id = my_id.getID()
    key_id = None
    key_alias = None
    while True:
        random_sample = os.urandom(24)
        key_alias = 'share_%s' % strng.to_text(key.HashMD5(random_sample, hexdigest=True))
        key_id = my_keys.make_key_id(alias=key_alias, creator_glob_id=owner_id)
        if my_keys.is_key_registered(key_id):
            continue
        break
    if not label:
        label = 'share%s' % utime.make_timestamp()
    if not key_size:
        key_size = settings.getPrivateKeySize()
    key_object = my_keys.generate_key(key_id, label=label, active=active, key_size=key_size)
    if key_object is None:
        return ERROR('failed to generate private key %s' % key_id)
    key_info = my_keys.make_key_info(
        key_object,
        key_id=key_id,
        include_private=False,
        include_state=True,
    )
    key_info.pop('include_private', None)
    backup_fs.SaveIndex(customer_idurl=global_id.glob2idurl(owner_id), key_alias=key_alias)
    return OK(
        key_info,
        message='new share %s created successfully' % key_id,
    )


def share_delete(key_id: str):
    """
    Stop the active share identified by the `key_id` and erase the private key.

    ###### HTTP
        curl -X DELETE 'localhost:8180/share/delete/v1' -d '{"key_id": "share_7e9726e2dccf9ebe6077070e98e78082$alice@server-a.com"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "share_delete", "kwargs": {"key_id": "share_7e9726e2dccf9ebe6077070e98e78082$alice@server-a.com"} }');
    """
    key_id = strng.to_text(key_id)
    if not driver.is_on('service_shared_data'):
        return ERROR('service_shared_data() is not started')
    if not key_id.startswith('share_'):
        return ERROR('invalid share id')
    from bitdust.access import shared_access_coordinator
    from bitdust.crypt import my_keys
    this_share = shared_access_coordinator.get_active_share(key_id)
    if not this_share:
        return ERROR('share %s was not opened' % key_id)
    this_share.automat('shutdown')
    my_keys.erase_key(key_id)
    # TODO: cleanup backup_fs as well
    return OK(
        this_share.to_json(),
        message='share %s deleted successfully' % key_id,
    )


def share_grant(key_id: str, trusted_user_id: str, timeout: int = 45, publish_events: bool = True):
    """
    Provide access to given share identified by `key_id` to another trusted user.

    This method will transfer private key to remote user `trusted_user_id` and you both will be
    able to upload/download file to the shared location.

    ###### HTTP
        curl -X PUT 'localhost:8180/share/grant/v1' -d '{"key_id": "share_7e9726e2dccf9ebe6077070e98e78082$alice@server-a.com", "trusted_user_id": "bob@machine-b.net"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "share_grant", "kwargs": {"key_id": "share_7e9726e2dccf9ebe6077070e98e78082$alice@server-a.com", "trusted_user_id": "bob@machine-b.net"} }');
    """
    if not driver.is_on('service_shared_data'):
        return ERROR('service_shared_data() is not started')
    key_id = strng.to_text(key_id)
    trusted_user_id = strng.to_text(trusted_user_id)
    if not key_id.startswith('share_'):
        return ERROR('invalid share id')
    from bitdust.userid import global_id
    from bitdust.userid import id_url
    trusted_user_id = strng.to_text(trusted_user_id)
    remote_idurl = None
    if trusted_user_id.count('@'):
        glob_id = global_id.ParseGlobalID(trusted_user_id)
        remote_idurl = glob_id['idurl']
    else:
        remote_idurl = id_url.field(trusted_user_id)
    if not remote_idurl:
        return ERROR('wrong user id')
    from bitdust.access import shared_access_donor
    ret = Deferred()

    def _on_shared_access_donor_success(result):
        ret.callback(OK(message='access granted', api_method='share_grant') if result else ERROR('grant access failed', api_method='share_grant'))
        return None

    def _on_shared_access_donor_failed(err):
        ret.callback(ERROR(err))
        return None

    d = Deferred()
    d.addCallback(_on_shared_access_donor_success)
    d.addErrback(_on_shared_access_donor_failed)
    d.addTimeout(timeout, clock=reactor)
    shared_access_donor_machine = shared_access_donor.SharedAccessDonor(
        log_events=True,
        publish_events=publish_events,
    )
    shared_access_donor_machine.automat('init', trusted_idurl=remote_idurl, key_id=key_id, result_defer=d)
    return ret


def share_open(key_id: str, publish_events: bool = False):
    """
    Activates given share and initiate required connections to remote suppliers to make possible to upload and download shared files.

    ###### HTTP
        curl -X PUT 'localhost:8180/share/open/v1' -d '{"key_id": "share_7e9726e2dccf9ebe6077070e98e78082$alice@server-a.com"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "share_open", "kwargs": {"key_id": "share_7e9726e2dccf9ebe6077070e98e78082$alice@server-a.com"} }');
    """
    key_id = strng.to_text(key_id)
    if not driver.is_on('service_shared_data'):
        return ERROR('service_shared_data() is not started')
    if not key_id.startswith('share_'):
        return ERROR('invalid share id')
    from bitdust.access import shared_access_coordinator
    from bitdust.contacts import identitycache
    from bitdust.crypt import my_keys
    from bitdust.userid import global_id
    idurl = global_id.glob2idurl(key_id)
    ret = Deferred()

    def _get_active_share(x):
        new_share = False
        active_share = shared_access_coordinator.get_active_share(key_id)
        if not active_share:
            new_share = True
            active_share = shared_access_coordinator.SharedAccessCoordinator(
                key_id=key_id,
                log_events=True,
                publish_events=publish_events,
            )

        def _on_shared_access_coordinator_state_changed(oldstate, newstate, event_string, *args, **kwargs):
            if _Debug:
                lg.args(_DebugLevel, oldstate=oldstate, newstate=newstate, event_string=event_string, active_share=active_share)
            if newstate == 'CONNECTED' and oldstate != newstate:
                active_share.removeStateChangedCallback(_on_shared_access_coordinator_state_changed)
                if new_share:
                    ret.callback(OK(active_share.to_json(), message='share %s opened successfully' % key_id, api_method='share_open'))
                else:
                    ret.callback(OK(active_share.to_json(), message='share %s refreshed successfully' % key_id, api_method='share_open'))
            if newstate == 'DISCONNECTED' and oldstate != newstate:
                active_share.removeStateChangedCallback(_on_shared_access_coordinator_state_changed)
                ret.callback(ERROR('share %s disconnected' % key_id, details=active_share.to_json(), api_method='share_open'))
            return None

        active_share.addStateChangedCallback(_on_shared_access_coordinator_state_changed)
        active_share.automat('restart')

    my_keys.set_active(key_id, True)
    d = identitycache.GetLatest(idurl)
    d.addErrback(lambda *args: ret.callback(ERROR('failed caching identity of the share creator')) and None)
    d.addCallback(_get_active_share)
    return ret


def share_close(key_id: str):
    """
    Disconnects and deactivate given share location.

    ###### HTTP
        curl -X DELETE 'localhost:8180/share/close/v1' -d '{"key_id": "share_7e9726e2dccf9ebe6077070e98e78082$alice@server-a.com"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "share_close", "kwargs": {"key_id": "share_7e9726e2dccf9ebe6077070e98e78082$alice@server-a.com"} }');
    """
    key_id = strng.to_text(key_id)
    if not driver.is_on('service_shared_data'):
        return ERROR('service_shared_data() is not started')
    if not key_id.startswith('share_'):
        return ERROR('invalid share id')
    from bitdust.crypt import my_keys
    from bitdust.access import shared_access_coordinator
    my_keys.set_active(key_id, False)
    this_share = shared_access_coordinator.get_active_share(key_id)
    if not this_share:
        return ERROR('share %s was not opened' % key_id)
    ret = Deferred()
    ret.addTimeout(20, clock=reactor)
    this_share.addStateChangedCallback(lambda *a, **kw: ret.callback(OK(
        this_share.to_json(),
        message='share %s closed' % key_id,
    )))
    this_share.automat('shutdown')
    return ret


def share_history():
    """
    Method is not implemented yet.
    """
    if not driver.is_on('service_shared_data'):
        return ERROR('service_shared_data() is not started')
    # TODO: key share history to be implemented
    return ERROR('method is not implemented yet')


#------------------------------------------------------------------------------


def groups_list(only_active: bool = False, include_mine: bool = True, include_granted: bool = True):
    """
    Returns a list of registered message groups.

    Use `only_active=True` to select only connected and active groups.

    Parameters `include_mine` and `include_granted` can be used to filter groups created by you,
    or by other users that shared a key with you before.

    ###### HTTP
        curl -X GET 'localhost:8180/group/list/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "groups_list", "kwargs": {} }');
    """
    if not driver.is_on('service_private_groups'):
        return ERROR('service_private_groups() is not started')
    from bitdust.access import group_participant
    from bitdust.access import groups
    from bitdust.crypt import my_keys
    from bitdust.userid import global_id
    from bitdust.userid import my_id
    results = []
    if only_active:
        for group_key_id in group_participant.list_active_group_participants():
            _glob_id = global_id.ParseGlobalID(group_key_id)
            to_be_listed = False
            if include_mine and _glob_id['idurl'] == my_id.getIDURL():
                to_be_listed = True
            if include_granted and _glob_id['idurl'] != my_id.getIDURL():
                to_be_listed = True
            if not to_be_listed:
                continue
            the_group = group_participant.get_active_group_participant(group_key_id)
            if not the_group:
                lg.warn('group %s was not found' % group_key_id)
                continue
            results.append(the_group.to_json())
        return RESULT(results)
    for group_key_id in my_keys.known_keys():
        if not group_key_id.startswith('group_'):
            continue
        group_key_alias, group_creator_idurl = my_keys.split_key_id(group_key_id)
        to_be_listed = False
        if include_mine and group_creator_idurl == my_id.getIDURL():
            to_be_listed = True
        if include_granted and group_creator_idurl != my_id.getIDURL():
            to_be_listed = True
        if not to_be_listed:
            continue
        result = {
            'group_key_id': group_key_id,
            'state': None,
            'alias': group_key_alias,
            'label': my_keys.get_label(group_key_id) or '',
            'active': False,
        }
        result.update({
            'group_key_info': my_keys.get_key_info(group_key_id),
        })
        this_group_participant = group_participant.get_active_group_participant(group_key_id)
        if this_group_participant:
            result.update(this_group_participant.to_json())
            results.append(result)
            continue
        offline_group_info = groups.active_groups().get(group_key_id)
        if offline_group_info:
            result.update(offline_group_info)
            result['state'] = 'DISCONNECTED'
            results.append(result)
            continue
        stored_group_info = groups.read_group_info(group_key_id)
        if stored_group_info:
            result.update(stored_group_info)
            result['state'] = 'CLOSED'
            results.append(result)
            continue
        result['state'] = 'CLEANED'
        results.append(result)
    return RESULT(results)


def group_create(creator_id: str = None, key_size: int = None, label: str = '', timeout: int = 30):
    """
    Creates a new messaging group.

    This method generates a new RSA private key that will be used to encrypt and decrypt messages streamed thru that group.

    Optional input parameter `key_size` can be 1024, 2048, 4096. If `key_size` was not passed, default value will be
    populated from the `personal/private-key-size` program setting.

    Parameter `label` can be used to attach some meaningful information about that group.

    ###### HTTP
        curl -X POST 'localhost:8180/group/create/v1' -d '{"label": "chat with my friends"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "group_create", "kwargs": {"label": "chat with my friends"} }');
    """
    if not driver.is_on('service_private_groups'):
        return ERROR('service_private_groups() is not started')
    from bitdust.main import settings
    from bitdust.crypt import my_keys
    from bitdust.access import groups
    from bitdust.userid import my_id
    if not creator_id:
        creator_id = my_id.getID()
    if not key_size:
        key_size = settings.getPrivateKeySize()
    group_key_id = groups.create_new_group(creator_id=creator_id, label=label, key_size=key_size, with_group_info=True)
    if not group_key_id:
        return ERROR('failed to create new group')
    key_info = my_keys.get_key_info(group_key_id, include_private=False, include_signature=False, generate_signature=False)
    key_info.pop('include_private', None)
    key_info['group_key_id'] = key_info.pop('key_id')
    ret = Deferred()
    d = groups.send_group_pub_key_to_suppliers(group_key_id)
    d.addCallback(lambda results: ret.callback(OK(key_info, message='new group %s created successfully' % group_key_id)))
    d.addErrback(lambda err: ret.callback(ERROR('failed to deliver group public key to my suppliers')))
    d.addTimeout(timeout, clock=reactor)
    return ret


def group_info(group_key_id: str):
    """
    Returns detailed info about the message group identified by `group_key_id`.

    ###### HTTP
        curl -X GET 'localhost:8180/group/info/v1?group_key_id=group_95d0fedc46308e2254477fcb96364af9$alice@server-a.com'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "group_info", "kwargs": {"group_key_id": "group_95d0fedc46308e2254477fcb96364af9$alice@server-a.com"} }');
    """
    if not driver.is_on('service_private_groups'):
        return ERROR('service_private_groups() is not started')
    from bitdust.access import groups
    from bitdust.access import group_participant
    from bitdust.crypt import my_keys
    group_key_id = strng.to_text(group_key_id)
    if not group_key_id.startswith('group_'):
        return ERROR('invalid group id')
    group_key_id = my_keys.latest_key_id(group_key_id)
    response = {
        'group_key_id': group_key_id,
        'state': None,
        'alias': my_keys.split_key_id(group_key_id)[0],
        'label': my_keys.get_label(group_key_id) or '',
        'active': False,
    }
    if not my_keys.is_key_registered(group_key_id):
        return ERROR('group key %s was not found' % group_key_id)
    response.update({
        'group_key_info': my_keys.get_key_info(group_key_id),
    })
    this_group_participant = group_participant.get_active_group_participant(group_key_id)
    if this_group_participant:
        response.update(this_group_participant.to_json())
        return OK(response)
    offline_group_info = groups.active_groups().get(group_key_id)
    if offline_group_info:
        response.update(offline_group_info)
        response['state'] = 'DISCONNECTED'
        return OK(response)
    stored_group_info = groups.read_group_info(group_key_id)
    if stored_group_info:
        response.update(stored_group_info)
        response['state'] = 'CLOSED'
        return OK(response)
    response['state'] = 'CLEANED'
    lg.warn('did not found stored group info for %s, but group key exist' % group_key_id)
    return OK(response)


def group_info_dht(group_creator_id: str):
    """
    Read and return list of message brokers stored in the corresponding DHT records for given user.

    ###### HTTP
        curl -X GET 'localhost:8180/group/info/dht/v1?group_creator_id=alice@server-a.com'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "group_info_dht", "kwargs": {"group_creator_id": "alice@server-a.com"} }');
    """
    if not driver.is_on('service_entangled_dht'):
        return ERROR('service_entangled_dht() is not started')
    from bitdust.dht import dht_relations
    from bitdust.access import groups
    from bitdust.userid import global_id
    from bitdust.userid import id_url
    from bitdust.userid import my_id
    customer_idurl = None
    if not group_creator_id:
        customer_idurl = my_id.getID()
    else:
        customer_idurl = strng.to_bin(group_creator_id)
        if global_id.IsValidGlobalUser(group_creator_id):
            customer_idurl = global_id.GlobalUserToIDURL(group_creator_id, as_field=False)
    customer_idurl = id_url.field(customer_idurl)
    ret = Deferred()
    d = dht_relations.read_customer_message_brokers(
        customer_idurl=customer_idurl,
        positions=list(range(groups.REQUIRED_BROKERS_COUNT)),
        as_fields=False,
        use_cache=False,
    )
    d.addCallback(lambda result: ret.callback(RESULT(result, api_method='group_info_dht')))
    d.addErrback(lambda err: ret.callback(ERROR(err)))
    return ret


def group_join(group_key_id: str, publish_events: bool = False, use_dht_cache: bool = True, wait_result: bool = True):
    """
    Activates given messaging group to be able to receive streamed messages or send a new message to the group.

    ###### HTTP
        curl -X POST 'localhost:8180/group/join/v1' -d '{"group_key_id": "group_95d0fedc46308e2254477fcb96364af9$alice@server-a.com"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "group_join", "kwargs": {"group_key_id": "group_95d0fedc46308e2254477fcb96364af9$alice@server-a.com"} }');
    """
    if not driver.is_on('service_private_groups'):
        return ERROR('service_private_groups() is not started')
    group_key_id = strng.to_text(group_key_id)
    if not group_key_id.startswith('group_') and not group_key_id.startswith('person$'):
        return ERROR('invalid group id')
    from bitdust.crypt import my_keys
    from bitdust.userid import id_url
    group_key_id = my_keys.latest_key_id(group_key_id)
    if not my_keys.is_key_registered(group_key_id):
        return ERROR('group key is not registered')
    ret = Deferred()
    started_group_participants = []
    existing_group_participants = []
    creator_idurl = my_keys.get_creator_idurl(group_key_id, as_field=False)

    def _on_group_participant_state_changed(oldstate, newstate, event_string, *args, **kwargs):
        if _Debug:
            lg.args(_DebugLevel, oldstate=oldstate, newstate=newstate, event_string=event_string)
        if newstate == 'CONNECTED' and oldstate != newstate:
            if existing_group_participants:
                existing_group_participants[0].removeStateChangedCallback(_on_group_participant_state_changed)
                ret.callback(OK(existing_group_participants[0].to_json(), message='group is refreshed', api_method='group_join'))
            else:
                started_group_participants[0].removeStateChangedCallback(_on_group_participant_state_changed)
                ret.callback(OK(started_group_participants[0].to_json(), message='group is connected', api_method='group_join'))
        if newstate == 'DISCONNECTED' and oldstate != newstate and oldstate != 'AT_STARTUP':
            if existing_group_participants:
                existing_group_participants[0].removeStateChangedCallback(_on_group_participant_state_changed)
                ret.callback(ERROR('group is disconnected', details=existing_group_participants[0].to_json(), api_method='group_join'))
            else:
                started_group_participants[0].removeStateChangedCallback(_on_group_participant_state_changed)
                ret.callback(ERROR('group is disconnected', details=started_group_participants[0].to_json(), api_method='group_join'))
        return None

    def _do_start_group_participant():
        from bitdust.access import group_participant
        existing_group_participant = group_participant.get_active_group_participant(group_key_id)
        if _Debug:
            lg.args(_DebugLevel, existing_group_participant=existing_group_participant)
        if existing_group_participant:
            existing_group_participants.append(existing_group_participant)
        else:
            existing_group_participant = group_participant.GroupParticipant(
                group_key_id=group_key_id,
                publish_events=publish_events,
            )
            started_group_participants.append(existing_group_participant)
        if existing_group_participant.state in ['SUPPLIERS?', 'SUBSCRIBE!', 'CONNECTED']:
            connecting_word = 'active' if existing_group_participant.state == 'CONNECTED' else 'connecting'
            ret.callback(OK(existing_group_participant.to_json(), message='group is already %s' % connecting_word, api_method='group_join'))
            return None
        if wait_result:
            existing_group_participant.addStateChangedCallback(_on_group_participant_state_changed)
        if started_group_participants:
            started_group_participants[0].automat('init')
        existing_group_participant.automat('reconnect')
        if not wait_result:
            ret.callback(OK(existing_group_participant.to_json(), message='group connection started', api_method='group_join'))
        return None

    def _do_cache_creator_idurl():
        from bitdust.contacts import identitycache
        d = identitycache.immediatelyCaching(creator_idurl)
        d.addErrback(lambda *args: ret.callback(ERROR('failed caching group creator identity')) and None)
        d.addCallback(lambda *args: _do_start_group_participant())

    if id_url.is_cached(creator_idurl):
        _do_start_group_participant()
    else:
        _do_cache_creator_idurl()
    return ret


def group_leave(group_key_id: str, erase_key: bool = False):
    """
    Deactivates given messaging group. If `erase_key=True` will also erase the private key related to that group.

    ###### HTTP
        curl -X DELETE 'localhost:8180/group/leave/v1' -d '{"group_key_id": "group_95d0fedc46308e2254477fcb96364af9$alice@server-a.com", "erase_key": 1}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "group_leave", "kwargs": {"group_key_id": "group_95d0fedc46308e2254477fcb96364af9$alice@server-a.com", "erase_key": 1} }');
    """
    if not driver.is_on('service_private_groups'):
        return ERROR('service_private_groups() is not started')
    from bitdust.access import group_participant
    from bitdust.access import groups
    from bitdust.crypt import my_keys
    group_key_id = strng.to_text(group_key_id)
    if not group_key_id.startswith('group_'):
        return ERROR('invalid group id')
    group_key_id = my_keys.latest_key_id(group_key_id)
    if not my_keys.is_key_registered(group_key_id):
        return ERROR('unknown group key')
    this_group_participant = group_participant.get_active_group_participant(group_key_id)
    if not this_group_participant:
        if erase_key:
            groups.erase_group_info(group_key_id)
            my_keys.erase_key(group_key_id)
            return OK(message='group deleted')
        groups.set_group_active(group_key_id, False)
        groups.save_group_info(group_key_id)
        return OK(message='group deactivated')
    result_json = this_group_participant.to_json()
    result_json['state'] = 'CLOSED'
    this_group_participant.event('disconnect', erase_key=erase_key)
    if erase_key:
        return OK(message='group deactivated and deleted', result=result_json)
    return OK(message='group deactivated', result=result_json)


def group_reconnect(group_key_id: str, use_dht_cache: bool = False):
    """
    Refreshing given messaging group - disconnect from the group first and then join again.
    Helpful method to reconnect with the group suppliers effectively.

    ###### HTTP
        curl -X PUT 'localhost:8180/group/reconnect/v1' -d '{"group_key_id": "group_95d0fedc46308e2254477fcb96364af9$alice@server-a.com"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "group_reconnect", "kwargs": {"group_key_id": "group_95d0fedc46308e2254477fcb96364af9$alice@server-a.com"} }');
    """
    if not driver.is_on('service_private_groups'):
        return ERROR('service_private_groups() is not started')
    from bitdust.access import group_participant
    from bitdust.crypt import my_keys
    group_key_id = strng.to_text(group_key_id)
    if not group_key_id.startswith('group_'):
        return ERROR('invalid group id')
    group_key_id = my_keys.latest_key_id(group_key_id)
    if not my_keys.is_key_registered(group_key_id):
        return ERROR('unknown group key')
    ret = Deferred()
    d = group_participant.restart_active_group_participant(group_key_id)
    if not d:
        return ERROR('group is not active at the moment')
    d.addCallback(lambda resp: ret.callback(OK(resp, api_method='group_reconnect')))
    d.addErrback(lambda err: ret.callback(ERROR(err, api_method='group_reconnect')))
    return ret


def group_share(group_key_id: str, trusted_user_id: str, timeout: int = 45, publish_events: bool = False):
    """
    Provide access to given group identified by `group_key_id` to another trusted user.

    This method will transfer private key to remote user `trusted_user_id` inviting him to the messaging group.

    ###### HTTP
        curl -X PUT 'localhost:8180/group/share/v1' -d '{"group_key_id": "group_95d0fedc46308e2254477fcb96364af9$alice@server-a.com", "trusted_user_id": "bob@machine-b.net"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "group_share", "kwargs": {"key_id": "group_95d0fedc46308e2254477fcb96364af9$alice@server-a.com", "trusted_user_id": "bob@machine-b.net"} }');
    """
    if not driver.is_on('service_private_groups'):
        return ERROR('service_private_groups() is not started')
    group_key_id = strng.to_text(group_key_id)
    if not group_key_id.startswith('group_'):
        return ERROR('invalid group id')
    from bitdust.userid import global_id
    from bitdust.userid import id_url
    trusted_user_id = strng.to_text(trusted_user_id)
    remote_idurl = None
    if trusted_user_id.count('@'):
        glob_id = global_id.ParseGlobalID(trusted_user_id)
        remote_idurl = glob_id['idurl']
    else:
        remote_idurl = id_url.field(trusted_user_id)
    if not remote_idurl:
        return ERROR('wrong user id')
    from bitdust.access import group_access_donor
    ret = Deferred()

    def _on_group_access_donor_success(result):
        ret.callback(OK(message='access granted', api_method='share_grant') if result else ERROR('grant access failed', api_method='group_share'))
        return None

    def _on_group_access_donor_failed(err):
        if _Debug:
            lg.args(_DebugLevel, err=err)
        ret.callback(ERROR(err))
        return None

    d = Deferred()
    d.addCallback(_on_group_access_donor_success)
    d.addErrback(_on_group_access_donor_failed)
    d.addTimeout(timeout, clock=reactor)
    group_access_donor_machine = group_access_donor.GroupAccessDonor(log_events=True, publish_events=publish_events)
    group_access_donor_machine.automat('init', trusted_idurl=remote_idurl, group_key_id=group_key_id, result_defer=d)
    return ret


#------------------------------------------------------------------------------


def friends_list():
    """
    Returns list of all registered correspondents.

    ###### HTTP
        curl -X GET 'localhost:8180/friend/list/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "friends_list", "kwargs": {} }');
    """
    from bitdust.contacts import contactsdb
    from bitdust.userid import global_id
    result = []
    for idurl, alias in contactsdb.correspondents():
        glob_id = global_id.ParseIDURL(idurl)
        # contact_status = 'offline'
        contact_state = 'OFFLINE'
        friend = {
            'idurl': idurl,
            'global_id': glob_id['customer'],
            'idhost': glob_id['idhost'],
            'username': glob_id['user'],
            'alias': alias,
            # 'contact_status': contact_status,
            'contact_state': contact_state,
        }
        if driver.is_on('service_identity_propagate'):
            from bitdust.p2p import online_status
            state_machine_inst = online_status.getInstance(idurl, autocreate=False)
            if state_machine_inst:
                friend.update(state_machine_inst.to_json())
                # friend['contact_status'] = online_status.stateToLabel(state_machine_inst.state)
                friend['contact_state'] = state_machine_inst.state
        result.append(friend)
    return RESULT(result)


def friend_add(trusted_user_id: str, alias: str = '', share_person_key: bool = True):
    """
    Add user to the list of correspondents.

    You can attach an alias to that user as a label to be displayed in the UI.

    ###### HTTP
        curl -X POST 'localhost:8180/friend/add/v1' -d '{"trusted_user_id": "dave@device-d.gov", "alias": "SuperMario"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "friend_add", "kwargs": {"trusted_user_id": "dave@device-d.gov", "alias": "SuperMario"} }');
    """
    if not driver.is_on('service_identity_propagate'):
        return ERROR('service_identity_propagate() is not started')
    from bitdust.contacts import contactsdb
    from bitdust.contacts import identitycache
    from bitdust.main import events
    from bitdust.p2p import online_status
    from bitdust.userid import global_id
    from bitdust.userid import id_url
    from bitdust.userid import my_id
    idurl = strng.to_text(trusted_user_id)
    if global_id.IsValidGlobalUser(trusted_user_id):
        idurl = global_id.GlobalUserToIDURL(trusted_user_id, as_field=False)
    idurl = id_url.field(idurl)
    if not idurl:
        return ERROR('you must specify the global IDURL address of remote user')

    ret = Deferred()

    def _add(idurl, result_defer):
        if idurl == my_id.getIDURL():
            result_defer.callback(ERROR('can not add my own identity as a new friend', api_method='friend_add'))
            return
        added = False
        if not contactsdb.is_correspondent(idurl):
            contactsdb.add_correspondent(idurl, alias)
            contactsdb.save_correspondents()
            added = True
            events.send('friend-added', data=dict(
                idurl=idurl,
                global_id=global_id.idurl2glob(idurl),
                alias=alias,
            ))
        d = online_status.handshake(idurl, channel='friend_add', keep_alive=True)
        if share_person_key:
            from bitdust.access import key_ring
            from bitdust.crypt import my_keys
            my_person_key_id = my_id.getGlobalID(key_alias='person')
            if my_keys.is_key_registered(my_person_key_id):
                d.addCallback(lambda *args: [key_ring.share_key(
                    key_id=my_person_key_id,
                    trusted_idurl=idurl,
                    include_private=False,
                    include_signature=False,
                    timeout=None,
                )])

        d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='api.friend_add')
        if added:
            result_defer.callback(OK(message='new friend has been added', api_method='friend_add'))
        else:
            result_defer.callback(OK(message='this friend has been already added', api_method='friend_add'))
        return

    if id_url.is_cached(idurl):
        _add(idurl, ret)
        return ret

    d = identitycache.immediatelyCaching(idurl)
    d.addErrback(lambda *args: ret.callback(ERROR('failed caching user identity')) and None)
    d.addCallback(lambda *args: _add(idurl, ret))
    return ret


def friend_remove(user_id: str):
    """
    Removes given user from the list of correspondents.

    ###### HTTP
        curl -X DELETE 'localhost:8180/friend/remove/v1' -d '{"user_id": "dave@device-d.gov"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "friend_remove", "kwargs": {"user_id": "dave@device-d.gov"} }');
    """
    if not driver.is_on('service_identity_propagate'):
        return ERROR('service_identity_propagate() is not started')
    from bitdust.contacts import contactsdb
    from bitdust.contacts import identitycache
    from bitdust.main import events
    from bitdust.userid import global_id
    from bitdust.userid import id_url
    idurl = strng.to_text(user_id)
    if global_id.IsValidGlobalUser(user_id):
        idurl = global_id.GlobalUserToIDURL(user_id, as_field=False)
    idurl = id_url.field(idurl)
    if not idurl:
        return ERROR('you must specify IDURL or user ID in short form')

    def _remove():
        if contactsdb.is_correspondent(idurl):
            contactsdb.remove_correspondent(idurl)
            contactsdb.save_correspondents()
            events.send('friend-removed', data=dict(
                idurl=idurl,
                global_id=global_id.idurl2glob(idurl),
            ))
            return OK(message='friend has been removed', api_method='friend_remove')
        return ERROR('friend %s was not found' % idurl.to_id(), api_method='friend_remove')

    if id_url.is_cached(idurl):
        return _remove()

    ret = Deferred()
    d = identitycache.GetLatest(idurl)
    d.addErrback(lambda *args: ret.callback(ERROR('failed caching user identity', api_method='friend_remove')) and None)
    d.addCallback(lambda *args: ret.callback(_remove()))
    return ret


#------------------------------------------------------------------------------


def user_ping(user_id: str, timeout: int = None, retries: int = 1):
    """
    Sends `Identity` packet to remote peer and wait for an `Ack` packet to check connection status.

    Method can be used to check and verify that remote node is on-line at the moment (if you are also on-line).

    ###### HTTP
        curl -X GET 'localhost:8180/user/ping/v1?user_id=carol@computer-c.net'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "suppliers_ping", "kwargs": {} }');
    """
    if not driver.is_on('service_identity_propagate'):
        return ERROR('service_identity_propagate() is not started')
    from bitdust.main import settings
    from bitdust.p2p import online_status
    from bitdust.userid import global_id
    if timeout is None:
        timeout = settings.P2PTimeOut()
    idurl = user_id
    if global_id.IsValidGlobalUser(idurl):
        idurl = global_id.GlobalUserToIDURL(idurl, as_field=False)
    idurl = strng.to_bin(idurl)
    ret = Deferred()
    d = online_status.handshake(
        idurl,
        ack_timeout=timeout,
        ping_retries=int(retries),
        channel='api_user_ping',
        keep_alive=False,
    )
    d.addCallback(lambda ok: ret.callback(OK(message=(ok or 'connected'), api_method='user_ping')))
    d.addErrback(lambda err: ret.callback(ERROR(err, api_method='user_ping')))
    return ret


def user_status(user_id: str):
    """
    Returns short info about current on-line status of the given user.

    ###### HTTP
        curl -X GET 'localhost:8180/user/status/v1?user_id=carol@computer-c.net'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "user_status", "kwargs": {"user_id": "carol@computer-c.net"} }');
    """
    if not driver.is_on('service_identity_propagate'):
        return ERROR('service_identity_propagate() is not started')
    from bitdust.p2p import online_status
    from bitdust.userid import global_id
    from bitdust.userid import id_url
    idurl = user_id
    if global_id.IsValidGlobalUser(idurl):
        idurl = global_id.GlobalUserToIDURL(idurl)
    idurl = id_url.field(idurl)
    if not online_status.isKnown(idurl):
        return ERROR('unknown user')
    # state_machine_inst = contact_status.getInstance(idurl)
    # if not state_machine_inst:
    #     return ERROR('error fetching user status')
    return OK({
        # 'contact_status': online_status.getStatusLabel(idurl),
        'contact_state': online_status.getCurrentState(idurl),
        'idurl': idurl,
        'global_id': global_id.UrlToGlobalID(idurl),
    })


def user_status_check(user_id: str, timeout: int = None):
    """
    Returns current online status of a user and only if node is known but disconnected performs "ping" operation.

    ###### HTTP
        curl -X GET 'localhost:8180/user/status/check/v1?user_id=carol@computer-c.net'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "user_status_check", "kwargs": {"user_id": "carol@computer-c.net"} }');
    """
    if not driver.is_on('service_identity_propagate'):
        return ERROR('service_identity_propagate() is not started')
    from bitdust.main import settings
    from bitdust.p2p import online_status
    from bitdust.userid import global_id
    from bitdust.userid import id_url
    if timeout is None:
        timeout = settings.P2PTimeOut()
    idurl = user_id
    if global_id.IsValidGlobalUser(idurl):
        idurl = global_id.GlobalUserToIDURL(idurl)
    idurl = id_url.field(idurl)
    peer_status = online_status.getInstance(idurl)
    if not peer_status:
        return ERROR('peer is not connected')
    ret = Deferred()
    ping_result = Deferred()
    ping_result.addCallback(
        lambda resp: ret.callback(OK(
            dict(
                idurl=idurl,
                global_id=global_id.UrlToGlobalID(idurl),
                contact_state=peer_status.state,
                # contact_status=online_status.stateToLabel(peer_status.state),
            ),
            api_method='user_status_check',
        ))
    )
    ping_result.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='api.user_status_check')
    ping_result.addErrback(lambda err: ret.errback(err))
    peer_status.automat('ping-now', ping_result, channel=None, ack_timeout=timeout, ping_retries=0)
    return ret


def user_search(nickname: str, attempts: int = 1):
    """
    Doing lookup of a single `nickname` registered in the DHT network.

    ###### HTTP
        curl -X GET 'localhost:8180/user/search/v1?nickname=carol'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "user_search", "kwargs": {"nickname": "carol"} }');
    """
    from bitdust.lib import misc
    from bitdust.userid import global_id
    if not nickname:
        return ERROR('requires nickname of the user')
    if not misc.ValidNickName(nickname):
        return ERROR('invalid nickname')
    if not driver.is_on('service_private_messages'):
        return ERROR('service_private_messages() is not started')

    from bitdust.chat import nickname_observer
    ret = Deferred()

    def _result(result, nik, pos, idurl):
        return ret.callback(OK(
            {
                'result': result,
                'nickname': nik,
                'position': pos,
                'global_id': global_id.UrlToGlobalID(idurl),
                'idurl': idurl,
            },
            api_method='user_search',
        ))

    nickname_observer.find_one(
        nickname,
        attempts=attempts,
        results_callback=_result,
    )
    return ret


def user_observe(nickname: str, attempts: int = 3):
    """
    Reads all records registered for given `nickname` in the DHT network.

    It could be that multiple users chosen same nickname when creating an identity.

    ###### HTTP
        curl -X GET 'localhost:8180/user/observe/v1?nickname=carol'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "user_observe", "kwargs": {"nickname": "carol"} }');
    """
    from bitdust.lib import misc
    from bitdust.userid import global_id
    if not nickname:
        return ERROR('requires nickname of the user')
    if not misc.ValidNickName(nickname):
        return ERROR('invalid nickname')
    if not driver.is_on('service_private_messages'):
        return ERROR('service_private_messages() is not started')

    from bitdust.chat import nickname_observer
    nickname_observer.stop_all()
    ret = Deferred()
    results = []

    def _result(result, nik, pos, idurl):
        if result != 'finished':
            results.append({
                'result': result,
                'nickname': nik,
                'position': pos,
                'global_id': global_id.UrlToGlobalID(idurl),
                'idurl': idurl,
            })
            return None
        ret.callback(RESULT(results, api_method='user_observe'))
        return None

    reactor.callLater(  # @UndefinedVariable
        0.05, nickname_observer.observe_many, nickname, attempts=attempts, results_callback=_result
    )
    return ret


# def nickname_get():
#     """
#     Returns my current nickname.
#
#     ###### HTTP
#         curl -X GET 'localhost:8180/nickname/get/v1'
#
#     ###### WebSocket
#         websocket.send('{"command": "api_call", "method": "queue_producers_list", "kwargs": {} }');
#     """
#     from bitdust.main import settings
#     if not driver.is_on('service_private_messages'):
#         return ERROR('service_private_messages() is not started')
#     return OK({'nickname': settings.getNickName(), })

# def nickname_set(nickname):
#     """
#     Set my nickname register and keep your nickname in DHT
#     network.
#     """
#     from bitdust.lib import misc
#     if not nickname:
#         return ERROR('requires nickname of the user')
#     if not misc.ValidNickName(nickname):
#         return ERROR('invalid nickname')
#     if not driver.is_on('service_private_messages'):
#         return ERROR('service_private_messages() is not started')
#     from bitdust.chat import nickname_holder
#     from bitdust.main import settings
#     from bitdust.userid import my_id
#     settings.setNickName(nickname)
#     ret = Deferred()
#
#     def _nickname_holder_result(result, key):
#         nickname_holder.A().remove_result_callback(_nickname_holder_result)
#         return ret.callback(OK(
#             {
#                 'success': result,
#                 'nickname': key,
#                 'global_id': my_id.getGlobalID(),
#                 'idurl': my_id.getIDURL(),
#             },
#             api_method='nickname_set',
#         ))
#
#     nickname_holder.A().add_result_callback(_nickname_holder_result)
#     nickname_holder.A('set', nickname)
#     return ret

#------------------------------------------------------------------------------


def message_history(recipient_id: str = None, sender_id: str = None, message_type: str = None, offset: int = 0, limit: int = 100):
    """
    Returns chat communications history stored for given user or messaging group.

    ###### HTTP
        curl -X GET 'localhost:8180/message/history/v1?message_type=group_message&recipient_id=group_95d0fedc46308e2254477fcb96364af9$alice@server-a.com'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "message_history", "kwargs": {"recipient_id" : "group_95d0fedc46308e2254477fcb96364af9$alice@server-a.com", "message_type": "group_message"} }');
    """
    if not driver.is_on('service_message_history'):
        return ERROR('service_message_history() is not started')
    from bitdust.chat import message_database
    from bitdust.userid import my_id, global_id
    from bitdust.crypt import my_keys
    if not recipient_id and not sender_id:
        return ERROR('recipient_id or sender_id is required')
    if recipient_id:
        if not recipient_id.count('@'):
            from bitdust.contacts import contactsdb
            recipient_idurl = contactsdb.find_correspondent_by_nickname(recipient_id)
            if not recipient_idurl:
                return ERROR('recipient was not found')
            recipient_id = global_id.UrlToGlobalID(recipient_idurl)
        recipient_glob_id = global_id.ParseGlobalID(recipient_id)
        if not recipient_glob_id['idurl']:
            return ERROR('wrong recipient_id')
        recipient_id = global_id.MakeGlobalID(**recipient_glob_id)
        if not my_keys.is_valid_key_id(recipient_id):
            return ERROR('invalid recipient_id: %s' % recipient_id)
    bidirectional = False
    if message_type in [None, 'private_message']:
        bidirectional = True
        if sender_id is None:
            sender_id = my_id.getGlobalID(key_alias='master')
    if sender_id:
        sender_local_key_id = my_keys.get_local_key_id(sender_id)
        if sender_local_key_id is None:
            lg.warn('local key id for sender %s was not registered' % sender_id)
            return RESULT([])
    if recipient_id:
        recipient_local_key_id = my_keys.get_local_key_id(recipient_id)
        if recipient_local_key_id is None:
            lg.warn('local key id for recipient %s was not registered' % recipient_id)
            return RESULT([])
    messages = [{
        'doc': m,
    } for m in message_database.query_messages(
        sender_id=sender_id,
        recipient_id=recipient_id,
        bidirectional=bidirectional,
        message_types=[
            message_type,
        ] if message_type else [],
        offset=offset,
        limit=limit,
    )]
    if _Debug:
        lg.out(_DebugLevel, 'api.message_history with recipient_id=%s sender_id=%s message_type=%s found %d messages' % (recipient_id, sender_id, message_type, len(messages)))
    return RESULT(messages)


def message_conversations_list(message_types: str = '', offset: int = 0, limit: int = 100):
    """
    Returns list of all known conversations with other users.
    Parameter `message_types` can be used to select conversations of specific types: `group_message`, `private_message`, `personal_message`.

    ###### HTTP
        curl -X GET 'localhost:8180/message/conversation/v1?message_types=group_message,private_message'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "message_conversations_list", "kwargs": {"message_types" : ["group_message", "private_message"]} }');
    """
    if not driver.is_on('service_message_history'):
        return ERROR('service_message_history() is not started')
    from bitdust.chat import message_database
    conversations = message_database.fetch_conversations(
        order_by_time=True,
        message_types=message_types.strip().split(',') if message_types.strip() else [],
        offset=offset,
        limit=limit,
    )
    if _Debug:
        lg.out(_DebugLevel, 'api.message_conversations with message_types=%s found %d conversations' % (message_types, len(conversations)))
    return RESULT(conversations)


def message_send(recipient_id: str, data: str, ping_timeout: int = 15, message_ack_timeout: int = 15):
    """
    Sends a private message to remote peer, `recipient_id` is a string with a nickname, global_id or IDURL of the remote user.

    Message will be encrypted first with public key of the recipient.
    Public key must be already registered locally or populated from remote identity file.
    Corresponding key will be recognized based on `recipient_id` parameter.

    Recipient will receive incoming message of type "private_message" and de-crypt it.
    If recipient is listening on the new private messages it will be marked as "consumed".

    Input `data` must be a JSON dictionary.

    ###### HTTP
        curl -X POST 'localhost:8180/message/send/v1' -d '{"recipient_id": "carlos@computer-c.net", "data": {"message": "Hola Amigo!"}}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "message_send", "kwargs": {"recipient_id": "carlos@computer-c.net", "data": {"message": "Hola Amigos!"}} }');
    """
    if not driver.is_on('service_private_messages'):
        return ERROR('service_private_messages() is not started')
    from bitdust.lib import packetid
    from bitdust.stream import message
    from bitdust.crypt import my_keys
    from bitdust.userid import global_id
    if not recipient_id.count('@'):
        from bitdust.contacts import contactsdb
        recipient_idurl = contactsdb.find_correspondent_by_nickname(recipient_id)
        if not recipient_idurl:
            recipient_idurl = strng.to_bin(recipient_id)
        if not recipient_idurl:
            return ERROR('recipient was not found')
        recipient_id = global_id.glob2idurl(recipient_idurl, as_field=False)
    glob_id = global_id.ParseGlobalID(recipient_id)
    if not glob_id['idurl']:
        return ERROR('wrong recipient')
    target_glob_id = global_id.MakeGlobalID(**glob_id)
    if not my_keys.is_valid_key_id(target_glob_id):
        return ERROR('invalid key_id: %s' % target_glob_id)
    if recipient_id.startswith('person$'):
        return ERROR('method is not implemented yet')
        # TODO: to be implemented
        if not driver.is_on('service_personal_messages'):
            return ERROR('service_personal_messages() is not started')
        if _Debug:
            lg.out(_DebugLevel, 'api.message_send to %r via message_producer' % recipient_id)
        from bitdust.stream import message_producer
        ret = Deferred()
        result = message_producer.push_message(recipient_id, data)
        result.addCallback(lambda ok: ret.callback(OK(message='message sent', api_method='message_send')))
        result.addErrback(lambda err: ret.callback(ERROR(err, api_method='message_send')))
        return ret
    if _Debug:
        lg.out(_DebugLevel, 'api.message_send to %r ping_timeout=%d message_ack_timeout=%d' % (target_glob_id, ping_timeout, message_ack_timeout))
    data['msg_type'] = 'private_message'
    data['action'] = 'read'
    result = message.send_message(
        json_data=data,
        recipient_global_id=target_glob_id,
        ping_timeout=ping_timeout,
        message_ack_timeout=message_ack_timeout,
        packet_id='private_%s' % packetid.UniqueID(),
    )
    ret = Deferred()
    result.addCallback(lambda packet: ret.callback(OK(
        result={
            'consumed': bool(strng.to_text(packet.Payload) != 'unread'),
        },
        message='message sent',
        api_method='message_send',
    ), ), )
    result.addErrback(lambda err: ret.callback(ERROR(err, api_method='message_send')))
    return ret


def message_send_group(group_key_id: str, data: str):
    """
    Sends a "group_message" to a group of users.

    Input `data` must be a JSON dictionary.

    ###### HTTP
        curl -X POST 'localhost:8180/message/send/group/v1' -d '{"group_key_id": "group_95d0fedc46308e2254477fcb96364af9$alice@server-a.com", "data": {"message": "Hola Amigos!"}}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "message_send_group", "kwargs": {"group_key_id": "group_95d0fedc46308e2254477fcb96364af9$alice@server-a.com", "data": {"message": "Hola Amigos!"}} }');
    """
    if not driver.is_on('service_private_groups'):
        return ERROR('service_private_groups() is not started')
    from bitdust.userid import global_id
    from bitdust.crypt import my_keys
    from bitdust.access import group_participant
    if not group_key_id.startswith('group_'):
        return ERROR('invalid group id')
    group_key_id = my_keys.latest_key_id(group_key_id)
    glob_id = global_id.ParseGlobalID(group_key_id)
    if not glob_id['idurl']:
        return ERROR('wrong group id')
    if not my_keys.is_key_registered(group_key_id):
        return ERROR('unknown group key')
    this_group_participant = group_participant.get_active_group_participant(group_key_id)
    if not this_group_participant:
        return ERROR('group is not active')
    if this_group_participant.state != 'CONNECTED':
        return ERROR('group is not synchronized yet')
    if _Debug:
        lg.out(_DebugLevel, 'api.message_send_group to %r' % group_key_id)
    this_group_participant.automat('push-message', json_payload=data, fast=True)
    return OK(message='group message sent')


# def message_send_broadcast(payload):
#     """
#     Sends broadcast message to all peers in the network.
#
#     Message must be provided in `payload` argument is a Json object.
#
#     WARNING! Please, do not send too often and do not send more then
#     several kilobytes per message.
#     """
#     if not driver.is_on('service_broadcasting'):
#         return ERROR('service_broadcasting() is not started')
#     from broadcast import broadcast_service
#     from broadcast import broadcast_listener
#     from broadcast import broadcaster_node
#     msg = broadcast_service.send_broadcast_message(payload)
#     current_states = dict()
#     if broadcaster_node.A():
#         current_states[broadcaster_node.A().name] = broadcaster_node.A().state
#     if broadcast_listener.A():
#         current_states[broadcast_listener.A().name] = broadcast_listener.A().state
#     if _Debug:
#         lg.out(_DebugLevel, 'api.broadcast_send_message : %s, %s' % (msg, current_states))
#     return RESULT([msg, current_states, ])


def message_receive(consumer_callback_id: str, direction: str = 'incoming', message_types: str = 'private_message,group_message', polling_timeout: int = 60):
    """
    This method can be used by clients to listen and process streaming messages.

    If there are no pending messages received yet in the stream, this method will block and will be waiting for any message to come.

    If some messages are already waiting in the stream to be consumed method will return them immediately.
    As soon as client received and processed the response messages are marked as "consumed" and released from the stream.

    Client should call that method again to listen for next messages in the stream. You can use `polling_timeout` parameter
    to control blocking for receiving duration. This is very similar to a long polling technique.

    Once client stopped calling that method and do not "consume" messages anymor given `consumer_callback_id` will be dropped
    after 100 non-collected messages.

    You can set parameter `direction=outgoing` to only populate messages you are sending to others - can be useful for UI clients.

    Also you can use parameter `message_types` to select only specific types of messages: `private_message`, `personal_message` or `group_message`.

    This method is only make sense for HTTP interface, because via a WebSocket it is possible to receive streamed messages instantly.

    ###### HTTP
        curl -X GET 'localhost:8180/message/receive/my-client-group-messages/v1?message_types=group_message'
    """
    if not driver.is_on('service_private_messages'):
        return ERROR('service_private_messages() is not started')
    from bitdust.stream import message
    from bitdust.p2p import p2p_service
    ret = Deferred()
    message_types = message_types.strip().split(',')

    def _on_pending_messages(pending_messages):
        result = []
        packets_to_ack = {}
        for msg in pending_messages:
            try:
                result.append({
                    'data': msg['data'],
                    'recipient': msg['to'],
                    'sender': msg['from'],
                    'time': msg['time'],
                    'message_id': msg['packet_id'],
                    'dir': msg['dir'],
                })
            except:
                lg.exc()
                continue
            if msg['owner_idurl']:
                packets_to_ack[msg['packet_id']] = msg['owner_idurl']
        for packet_id, owner_idurl in packets_to_ack.items():
            p2p_service.SendAckNoRequest(owner_idurl, packet_id)
        packets_to_ack.clear()
        if _Debug:
            lg.out(_DebugLevel, 'api.message_receive._on_pending_messages returning %d results' % len(result))
        ret.callback(RESULT(result, api_method='message_receive'))
        return len(result) > 0

    def _on_consume_error(err):
        if _Debug:
            lg.args(_DebugLevel, err=err)
        if isinstance(err, list) and len(err) > 0:
            err = err[0]
        if isinstance(err, Failure):
            try:
                err = err.getErrorMessage()
            except:
                err = strng.to_text(err)
        if err.lower().count('cancelled'):
            ret.callback(RESULT([], api_method='message_receive'))
            return None
        if not str(err):
            ret.callback(RESULT([], api_method='message_receive'))
            return None
        ret.callback(ERROR(err))
        return None

    d = message.consume_messages(
        consumer_callback_id=consumer_callback_id,
        direction=direction,
        message_types=message_types,
        reset_callback=True,
    )
    d.addCallback(_on_pending_messages)
    d.addErrback(_on_consume_error)
    if polling_timeout is not None:
        d.addTimeout(polling_timeout, clock=reactor)
    if _Debug:
        lg.out(_DebugLevel, 'api.message_receive %r started' % consumer_callback_id)
    return ret


#------------------------------------------------------------------------------


def suppliers_list(customer_id: str = None, verbose: bool = False):
    """
    This method returns a list of your suppliers.
    Those nodes are holding each and every encrypted file created by you or file uploaded by other users that still belongs to you.

    Your BitDust node also able to connect to suppliers employed by other users. It makes possible to upload and download a shared data.
    Information about those external suppliers is cached and can be also accessed here with `customer_id` optional parameter.

    ###### HTTP
        curl -X GET 'localhost:8180/supplier/list/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "suppliers_list", "kwargs": {} }');
    """
    if not driver.is_on('service_customer'):
        return ERROR('service_customer() is not started')
    from bitdust.contacts import contactsdb
    from bitdust.customer import supplier_connector
    from bitdust.p2p import online_status
    from bitdust.lib import misc
    from bitdust.userid import my_id
    from bitdust.userid import id_url
    from bitdust.userid import global_id
    # from bitdust.storage import backup_matrix
    customer_idurl = strng.to_bin(customer_id)
    if not customer_idurl:
        customer_idurl = my_id.getIDURL().to_bin()
    else:
        if global_id.IsValidGlobalUser(customer_id):
            customer_idurl = global_id.GlobalUserToIDURL(customer_id, as_field=False)
    customer_idurl = id_url.field(customer_idurl)
    results = []
    for pos, supplier_idurl in enumerate(contactsdb.suppliers(customer_idurl)):
        if not supplier_idurl:
            r = {
                'position': pos,
                'idurl': '',
                'global_id': '',
                'supplier_state': None,
                'connected': None,
                # 'contact_status': 'offline',
                'contact_state': 'OFFLINE',
            }
            results.append(r)
            continue
        sc = None
        if supplier_connector.is_supplier(supplier_idurl, customer_idurl):
            sc = supplier_connector.by_idurl(supplier_idurl, customer_idurl)
        r = {
            'position': pos,
            'idurl': supplier_idurl,
            'global_id': global_id.UrlToGlobalID(supplier_idurl),
            'supplier_state': None if not sc else sc.state,
            'connected': misc.readSupplierData(supplier_idurl, 'connected', customer_idurl),
            # 'contact_status': 'offline',
            'contact_state': 'OFFLINE',
        }
        if online_status.isKnown(supplier_idurl):
            # r['contact_status'] = online_status.getStatusLabel(supplier_idurl)
            r['contact_state'] = online_status.getCurrentState(supplier_idurl)
        # if contact_status.isKnown(supplier_idurl):
        #     cur_state = contact_status.getInstance(supplier_idurl).state
        #     r['contact_status'] = contact_status.stateToLabel(cur_state)
        #     r['contact_state'] = cur_state
        if verbose:
            # TODO: create separate api method for that: api.supplier_list_files()
            # _files, _total, _report = backup_matrix.GetSupplierStats(pos, customer_idurl=customer_idurl)
            # r['listfiles'] = misc.readSupplierData(supplier_idurl, 'listfiles', customer_idurl).split('\n')
            # r['fragments'] = {
            #     'items': _files,
            #     'files': _total,
            #     'details': _report,
            # }
            r['contract'] = None if not sc else sc.storage_contract
        results.append(r)
    return RESULT(results)


def supplier_change(position: int = None, supplier_id: str = None, new_supplier_id: str = None):
    """
    The method will execute a fire/hire process for given supplier. You can specify which supplier to be replaced by position or ID.

    If optional parameter `new_supplier_id` was not specified another random node will be found via DHT network and it will
    replace the current supplier. Otherwise `new_supplier_id` must be an existing node in the network and
    the process will try to connect and use that node as a new supplier.

    As soon as new node is found and connected, rebuilding of all uploaded data will be automatically started and new supplier
    will start getting reconstructed fragments of your data piece by piece.

    ###### HTTP
        curl -X POST 'localhost:8180/supplier/change/v1' -d '{"position": 1, "new_supplier_id": "carol@computer-c.net"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "supplier_change", "kwargs": {"position": 1, "new_supplier_id": "carol@computer-c.net"} }');
    """
    if not driver.is_on('service_employer'):
        return ERROR('service_employer() is not started')
    from bitdust.contacts import contactsdb
    from bitdust.userid import my_id
    from bitdust.userid import global_id
    customer_idurl = my_id.getIDURL()
    supplier_idurl = None
    if position is not None:
        supplier_idurl = contactsdb.supplier(int(position), customer_idurl=customer_idurl)
    else:
        if global_id.IsValidGlobalUser(supplier_id):
            supplier_idurl = global_id.GlobalUserToIDURL(supplier_id)
    supplier_idurl = strng.to_bin(supplier_idurl)
    if not supplier_idurl or not contactsdb.is_supplier(supplier_idurl, customer_idurl=customer_idurl):
        return ERROR('supplier was not found')
    new_supplier_idurl = new_supplier_id
    if new_supplier_id is not None:
        if global_id.IsValidGlobalUser(new_supplier_id):
            new_supplier_idurl = global_id.GlobalUserToIDURL(new_supplier_id, as_field=False)
        new_supplier_idurl = strng.to_bin(new_supplier_idurl)
        if contactsdb.is_supplier(new_supplier_idurl, customer_idurl=customer_idurl):
            return ERROR('user %s is already a known supplier' % new_supplier_idurl)
    ret = Deferred()

    def _do_change(x):
        from bitdust.customer import fire_hire
        from bitdust.customer import supplier_finder
        if new_supplier_idurl is not None:
            supplier_finder.InsertSupplierToHire(new_supplier_idurl)
        fire_hire.AddSupplierToFire(supplier_idurl)
        fire_hire.A('restart')
        if new_supplier_idurl is not None:
            ret.callback(OK(message='supplier %s will be replaced by %s' % (strng.to_text(supplier_idurl), strng.to_text(new_supplier_idurl)), api_method='supplier_change'))
        else:
            ret.callback(OK(message='supplier %s will be replaced by a randomly selected user' % strng.to_text(supplier_idurl), api_method='supplier_change'))
        return None

    if new_supplier_id is None:
        _do_change(None)
        return ret
    from bitdust.p2p import online_status
    d = online_status.handshake(
        idurl=new_supplier_idurl,
        channel='supplier_change',
        keep_alive=True,
    )
    d.addCallback(_do_change)
    d.addErrback(lambda err: ret.callback(ERROR(err)))
    return ret


def suppliers_ping():
    """
    Sends short requests to all suppliers to verify current connection status.

    ###### HTTP
        curl -X POST 'localhost:8180/supplier/ping/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "suppliers_ping", "kwargs": {} }');
    """
    if not driver.is_on('service_customer'):
        return ERROR('service_customer() is not started')
    from bitdust.p2p import propagate
    propagate.SlowSendSuppliers(0.1)
    return OK(message='sent requests to all suppliers')


def suppliers_list_dht(customer_id: str = None):
    """
    Scans DHT network for key-value pairs related to given customer and returns a list its suppliers.

    ###### HTTP
        curl -X GET 'localhost:8180/supplier/list/dht/v1?customer_id=alice@server-a.com'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "suppliers_list_dht", "kwargs": {"customer_id": "alice@server-a.com"} }');
    """
    if not driver.is_on('service_entangled_dht'):
        return ERROR('service_entangled_dht() is not started')
    from bitdust.dht import dht_relations
    from bitdust.userid import my_id
    from bitdust.userid import id_url
    from bitdust.userid import global_id
    customer_idurl = None
    if not customer_id:
        customer_idurl = my_id.getIDURL().to_bin()
    else:
        customer_idurl = strng.to_bin(customer_id)
        if global_id.IsValidGlobalUser(customer_id):
            customer_idurl = global_id.GlobalUserToIDURL(customer_id, as_field=False)
    customer_idurl = id_url.field(customer_idurl)
    ret = Deferred()
    d = dht_relations.read_customer_suppliers(customer_idurl, as_fields=False, use_cache=False)
    d.addCallback(lambda result: ret.callback(RESULT(result, api_method='suppliers_list_dht')))
    d.addErrback(lambda err: ret.callback(ERROR(err)))
    return ret


#------------------------------------------------------------------------------


def customers_list(verbose: bool = False):
    """
    Method returns list of your customers - nodes for whom you are storing data on that host.

    ###### HTTP
        curl -X GET 'localhost:8180/customer/list/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "customers_list", "kwargs": {} }');
    """
    if not driver.is_on('service_supplier'):
        return ERROR('service_supplier() is not started')
    service_customer_support_on = False
    if driver.is_on('service_customer_support'):
        service_customer_support_on = True
        from bitdust.supplier import customer_assistant
    service_supplier_contracts_on = False
    if driver.is_on('service_supplier_contracts'):
        service_supplier_contracts_on = True
        from bitdust.supplier import storage_contract
    from bitdust.contacts import contactsdb
    from bitdust.p2p import online_status
    from bitdust.userid import global_id
    results = []
    for pos, customer_idurl in enumerate(contactsdb.customers()):
        if not customer_idurl:
            r = {
                'position': pos,
                'global_id': '',
                'idurl': '',
                # 'contact_status': 'offline',
                'contact_state': 'OFFLINE',
                # 'customer_assistant_state': 'OFFLINE',
            }
            results.append(r)
            continue
        r = {
            'position': pos,
            'global_id': global_id.UrlToGlobalID(customer_idurl),
            'idurl': customer_idurl,
            # 'contact_status': 'offline',
            'contact_state': 'OFFLINE',
            # 'customer_assistant_state': 'OFFLINE',
        }
        if online_status.isKnown(customer_idurl):
            # r['contact_status'] = online_status.getStatusLabel(customer_idurl)
            r['contact_state'] = online_status.getCurrentState(customer_idurl)
        if verbose:
            if service_customer_support_on:
                assistant = customer_assistant.by_idurl(customer_idurl)
                if assistant:
                    r['customer_assistant_state'] = assistant.state
            if service_supplier_contracts_on:
                r['contract'] = storage_contract.get_current_customer_contract(customer_idurl)
        results.append(r)
    return RESULT(results)


def customer_reject(customer_id: str, erase_customer_key: bool = True):
    """
    Stop supporting given customer, remove all related files from local disc, close connections with that node.

    ###### HTTP
        curl -X DELETE 'localhost:8180/customer/reject/v1' -d '{"customer_id": "dave@device-d.gov"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "customer_reject", "kwargs": {"customer_id": "dave@device-d.gov"} }');
    """
    if not driver.is_on('service_supplier'):
        return ERROR('service_supplier() is not started')
    from bitdust.contacts import contactsdb
    from bitdust.storage import accounting
    from bitdust.main import settings
    from bitdust.main import events
    from bitdust.supplier import local_tester
    from bitdust.raid import eccmap
    from bitdust.p2p import p2p_service
    from bitdust.lib import packetid
    from bitdust.crypt import my_keys
    from bitdust.userid import global_id
    from bitdust.userid import id_url
    customer_idurl = customer_id
    if global_id.IsValidGlobalUser(customer_id):
        customer_idurl = global_id.GlobalUserToIDURL(customer_id)
    customer_idurl = id_url.field(customer_idurl)
    if not contactsdb.is_customer(customer_idurl):
        return ERROR('customer was not found')
    # send packet to notify about service from us was rejected
    # TODO: - this is not yet handled on other side
    p2p_service.SendFailNoRequest(customer_idurl, packetid.UniqueID(), 'service rejected')
    # remove from customers list
    current_customers = contactsdb.customers()
    current_customers.remove(customer_idurl)
    contactsdb.remove_customer_meta_info(customer_idurl)
    # remove records for this customers from quotas info
    space_dict, _ = accounting.read_customers_quotas()
    consumed_by_cutomer = space_dict.pop(customer_idurl, 0)
    consumed_space = accounting.count_consumed_space(space_dict)
    new_free_space = settings.getDonatedBytes() - int(consumed_space)
    accounting.write_customers_quotas(space_dict, new_free_space)
    contactsdb.update_customers(current_customers)
    contactsdb.save_customers()
    if erase_customer_key:
        # erase customer key
        customer_key_id = my_keys.make_key_id(alias='customer', creator_idurl=customer_idurl)
        resp = key_erase(customer_key_id)
        if resp['status'] != 'OK':
            lg.warn('key %r removal failed' % customer_key_id)
    events.send('existing-customer-terminated', data=dict(
        idurl=customer_idurl,
        ecc_map=eccmap.Current().name,
    ))
    # restart local tester
    local_tester.TestUpdateCustomers()
    return OK(message='all services for client %s have been stopped, %r bytes freed' % (customer_idurl, consumed_by_cutomer))


def customers_ping():
    """
    Check current on-line status of all customers.

    ###### HTTP
        curl -X POST 'localhost:8180/customer/ping/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "customers_ping", "kwargs": {} }');
    """
    if not driver.is_on('service_supplier'):
        return ERROR('service_supplier() is not started')
    from bitdust.p2p import propagate
    propagate.SlowSendCustomers(0.1)
    return OK(message='sent requests to all customers')


#------------------------------------------------------------------------------


def space_donated():
    """
    Returns detailed info about quotas and usage of the storage space you donated to your customers.

    ###### HTTP
        curl -X GET 'localhost:8180/space/donated/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "space_donated", "kwargs": {} }');
    """
    from bitdust.storage import accounting
    result = accounting.report_donated_storage()
    if _Debug:
        lg.out(_DebugLevel, 'api.space_donated finished with %d customers and %d errors' % (len(result['customers']), len(result['errors'])))
    for err in result['errors']:
        if _Debug:
            lg.out(_DebugLevel, '    %s' % err)
    errors = result.pop('errors', [])
    return OK(
        result,
        errors=errors,
    )


def space_consumed():
    """
    Returns info about current usage of the storage space provided by your suppliers.

    ###### HTTP
        curl -X GET 'localhost:8180/space/consumed/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "space_consumed", "kwargs": {} }');
    """
    from bitdust.storage import accounting
    result = accounting.report_consumed_storage()
    if _Debug:
        lg.out(_DebugLevel, 'api.space_consumed finished')
    return OK(result)


def space_local():
    """
    Returns info about current usage of your local disk drive.

    ###### HTTP
        curl -X GET 'localhost:8180/space/local/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "space_local", "kwargs": {} }');
    """
    from bitdust.storage import accounting
    result = accounting.report_local_storage()
    if _Debug:
        lg.out(_DebugLevel, 'api.space_local finished')
    return OK(result)


#------------------------------------------------------------------------------


def services_list(with_configs: bool = False, as_tree: bool = False):
    """
    Returns detailed info about all currently running network services.

    Pass `with_configs=True` to also see current program settings values related to each service.

    This is a very useful method when you need to investigate a problem in the software.

    ###### HTTP
        curl -X GET 'localhost:8180/service/list/v1?with_configs=1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "services_list", "kwargs": {"with_configs": 1} }');
    """
    result = []
    if as_tree:
        ordered = sorted(list(driver.services().items()), key=lambda i: driver.root_distance(i[0]))
    else:
        ordered = sorted(list(driver.services().items()), key=lambda i: i[0])
    for svc_name, svc in ordered:
        svc_info = svc.to_json()
        if with_configs:
            svc_configs = []
            for child in config.conf().listEntries(svc.config_path.replace('/enabled', '')):
                svc_configs.append(config.conf().toJson(child, include_info=False))
            svc_info['configs'] = svc_configs
        if as_tree:
            svc_info['root_distance'] = driver.root_distance(svc_name)
        result.append(svc_info)
    if _Debug:
        lg.out(_DebugLevel, 'api.services_list responded with %d items' % len(result))
    return RESULT(result)


def service_info(service_name: str):
    """
    Returns detailed info about single service.

    ###### HTTP
        curl -X GET 'localhost:8180/service/info/service_private_groups/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "service_info", "kwargs": {"service_name": "service_private_groups"} }');
    """
    svc_info = driver.info(service_name)
    if svc_info is None:
        return ERROR('service was not found')
    return OK(svc_info)


def service_start(service_name: str):
    """
    Starts given service immediately.

    This method also set `True` for correspondent option in the program settings to mark the service as enabled:

        .bitdust/[network name]/config/services/[service name]/enabled

    Other dependent services, if they were enabled before but stopped, also will be started.

    ###### HTTP
        curl -X POST 'localhost:8180/service/start/service_supplier/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "service_start", "kwargs": {"service_name": "service_supplier"} }');
    """
    if _Debug:
        lg.out(_DebugLevel, 'api.service_start : %s' % service_name)
    svc = driver.services().get(service_name, None)
    if svc is None:
        service_name = 'service_' + service_name.replace('-', '_')
        svc = driver.services().get(service_name, None)
    if svc is None:
        lg.warn('service %r was not found' % service_name)
        return ERROR('service %s was not found' % service_name)
    if svc.state == 'ON':
        lg.warn('service %r already started' % service_name)
        return ERROR('service %s already started' % service_name)
    current_config = config.conf().getBool(svc.config_path)
    if current_config:
        lg.warn('service %r already enabled' % service_name)
        return ERROR('service %s already enabled' % service_name)
    config.conf().setBool(svc.config_path, True)
    return OK(message='service %s switched on' % service_name)


def service_stop(service_name: str):
    """
    Stop given service immediately.

    This method also set `False` for correspondent option in the program settings to mark the service as disabled:

        .bitdust/[network name]config/services/[service name]/enabled

    Dependent services will be stopped as well but will not be disabled.

    ###### HTTP
        curl -X POST 'localhost:8180/service/stop/service_supplier/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "service_stop", "kwargs": {"service_name": "service_supplier"} }');
    """
    if _Debug:
        lg.out(_DebugLevel, 'api.service_stop : %s' % service_name)
    svc = driver.services().get(service_name, None)
    if svc is None:
        service_name = 'service_' + service_name.replace('-', '_')
        svc = driver.services().get(service_name, None)
    if svc is None:
        lg.warn('service %r was not found' % service_name)
        return ERROR('service %s was not found' % service_name)
    current_config = config.conf().getBool(svc.config_path)
    if current_config is None:
        lg.warn('config item %r was not found' % svc.config_path)
        return ERROR('config item %s was not found' % svc.config_path)
    if current_config is False:
        lg.warn('service %r already disabled' % service_name)
        return ERROR('service %s already disabled' % service_name)
    config.conf().setBool(svc.config_path, False)
    return OK(message='service %s switched off' % service_name)


def service_restart(service_name: str, wait_timeout: int = 10):
    """
    This method will stop given service and start it again, but only if it is already enabled.
    It will not modify corresponding option for that service in the program settings.

    All dependent services will be restarted as well.

    Very useful method when you need to reload some parts of the application without full process restart.

    ###### HTTP
        curl -X POST 'localhost:8180/service/restart/service_customer/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "service_restart", "kwargs": {"service_name": "service_customer"} }');
    """
    svc = driver.services().get(service_name, None)
    if _Debug:
        lg.out(_DebugLevel, 'api.service_restart : %s' % service_name)
    if svc is None:
        service_name = 'service_' + service_name.replace('-', '_')
        svc = driver.services().get(service_name, None)
    if svc is None:
        lg.warn('service %s was not found' % service_name)
        return ERROR('service %s was not found' % service_name)
    ret = Deferred()
    d = driver.restart(service_name, wait_timeout=wait_timeout)
    d.addCallback(lambda resp: ret.callback(OK(resp, api_method='service_restart')))
    d.addErrback(lambda err: ret.callback(ERROR(err, api_method='service_restart')))
    return ret


def service_health(service_name: str):
    """
    Method will execute "health check" procedure of the given service - each service defines its own way to verify that.

    ###### HTTP
        curl -X POST 'localhost:8180/service/health/service_message_history/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "service_health", "kwargs": {"service_name": "service_message_history"} }');
    """
    if _Debug:
        lg.out(_DebugLevel, 'api.service_health : %s' % service_name)
    ret = Deferred()
    d = driver.is_healthy(service_name)
    d.addCallback(lambda resp: ret.callback(RESULT(resp, api_method='service_health')))
    d.addErrback(lambda err: ret.callback(ERROR(err, api_method='service_health')))
    return ret


#------------------------------------------------------------------------------


def packets_list():
    """
    Returns list of incoming and outgoing signed packets running at the moment.

    ###### HTTP
        curl -X GET 'localhost:8180/packet/list/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "packets_list", "kwargs": {} }');
    """
    if not driver.is_on('service_gateway'):
        return ERROR('service_gateway() is not started')
    from bitdust.transport import packet_in
    from bitdust.transport import packet_out
    result = []
    for pkt_out in packet_out.queue():
        items = []
        for itm in pkt_out.items:
            items.append({
                'transfer_id': itm.transfer_id,
                'proto': itm.proto,
                'host': itm.host,
                'size': itm.size,
                'bytes_sent': itm.bytes_sent,
            })
        result.append(
            {
                'direction': 'outgoing',
                'command': pkt_out.outpacket.Command,
                'packet_id': pkt_out.outpacket.PacketID,
                'label': pkt_out.label,
                'target': pkt_out.remote_idurl,
                'description': pkt_out.description,
                'label': pkt_out.label,
                'response_timeout': pkt_out.response_timeout,
                'items': items,
            }
        )
    for pkt_in in list(packet_in.inbox_items().values()):
        result.append(
            {
                'direction': 'incoming',
                'transfer_id': pkt_in.transfer_id,
                'label': pkt_in.label,
                'target': pkt_in.sender_idurl,
                'label': pkt_in.label,
                'timeout': pkt_in.timeout,
                'proto': pkt_in.proto,
                'host': pkt_in.host,
                'size': pkt_in.size,
                'bytes_received': pkt_in.bytes_received,
            }
        )
    return RESULT(result)


def packets_stats():
    """
    Returns detailed info about overall network usage.

    ###### HTTP
        curl -X GET 'localhost:8180/packet/stats/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "packets_stats", "kwargs": {} }');
    """
    if not driver.is_on('service_gateway'):
        return ERROR('service_gateway() is not started')
    from bitdust.p2p import p2p_stats
    return OK({
        'in': p2p_stats.counters_in(),
        'out': p2p_stats.counters_out(),
    })


#------------------------------------------------------------------------------


def transfers_list():
    """
    Returns list of current data fragments transfers to/from suppliers.

    ###### HTTP
        curl -X GET 'localhost:8180/transfer/list/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "transfers_list", "kwargs": {} }');
    """
    if not driver.is_on('service_data_motion'):
        return ERROR('service_data_motion() is not started')
    from bitdust.stream import io_throttle
    from bitdust.userid import global_id
    result = []
    for supplier_idurl in io_throttle.throttle().ListSupplierQueues():
        r = {
            'idurl': supplier_idurl,
            'global_id': global_id.UrlToGlobalID(supplier_idurl),
            'outgoing': [],
            'incoming': [],
        }
        q = io_throttle.throttle().GetSupplierQueue(supplier_idurl)
        for packet_id in q.ListSendItems():
            i = q.GetSendItem(packet_id)
            if i:
                r['outgoing'].append({
                    'packet_id': i.packetID,
                    'owner_id': i.ownerID,
                    'remote_id': i.remoteID,
                    'customer': i.customerID,
                    'remote_path': i.remotePath,
                    'filename': i.fileName,
                    'created': i.created,
                    'sent': i.sendTime,
                })
        for packet_id in q.ListRequestItems():
            i = q.GetRequestItem(packet_id)
            if i:
                r['incoming'].append(
                    {
                        'packet_id': i.packetID,
                        'owner_id': i.ownerID,
                        'remote_id': i.remoteID,
                        'customer': i.customerID,
                        'remote_path': i.remotePath,
                        'filename': i.fileName,
                        'created': i.created,
                        'requested': i.requestTime,
                    }
                )
        result.append(r)
    return RESULT(result)


def connections_list(protocols: str = None):
    """
    Returns list of opened/active network connections.

    Argument `protocols` can be used to select which protocols to be present in the response:

    ###### HTTP
        curl -X GET 'localhost:8180/connection/list/v1?protocols=tcp,udp,proxy'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "connections_list", "kwargs": {"protocols": "tcp,udp,proxy"]} }');
    """
    if not driver.is_on('service_gateway'):
        return ERROR('service_gateway() is not started')
    from bitdust.lib import net_misc
    from bitdust.transport import gateway
    from bitdust.userid import global_id
    result = []
    if protocols:
        protocols = protocols.split(',')
    else:
        protocols = gateway.list_active_transports()
    for proto in protocols:
        if not gateway.is_ready():
            continue
        if not gateway.is_installed(proto):
            continue
        for connection in gateway.list_active_sessions(proto):
            item = {
                'status': 'unknown',
                'state': 'unknown',
                'proto': proto,
                'host': 'unknown',
                'global_id': 'unknown',
                'idurl': 'unknown',
                'bytes_sent': 0,
                'bytes_received': 0,
            }
            if proto == 'tcp':
                if hasattr(connection, 'stream'):
                    try:
                        host = net_misc.pack_address_text(connection.peer_address)
                    except:
                        host = 'unknown'
                    item.update(
                        {
                            'status': 'active',
                            'state': connection.state,
                            'host': host,
                            'global_id': global_id.UrlToGlobalID(connection.peer_idurl or ''),
                            'idurl': connection.peer_idurl or '',
                            'bytes_sent': connection.total_bytes_sent or 0,
                            'bytes_received': connection.total_bytes_received or 0,
                        }
                    )
                else:
                    try:
                        host = net_misc.pack_address_text(connection.connection_address)
                    except:
                        host = 'unknown'
                    item.update({
                        'status': 'connecting',
                        'host': host,
                    })
            elif proto == 'udp':
                try:
                    host = net_misc.pack_address_text(connection.peer_address)
                except:
                    host = 'unknown'
                item.update(
                    {
                        'status': 'active',
                        'state': connection.state,
                        'host': host,
                        'global_id': global_id.UrlToGlobalID(connection.peer_idurl or ''),
                        'idurl': connection.peer_idurl or '',
                        'bytes_sent': connection.bytes_sent or 0,
                        'bytes_received': connection.bytes_received or 0,
                    }
                )
            elif proto == 'proxy':
                info = connection.to_json()
                item.update(
                    {
                        'status': 'active',
                        'state': info['state'],
                        'host': info['host'] or '',
                        'global_id': global_id.UrlToGlobalID(info['idurl'] or ''),
                        'idurl': info['idurl'] or '',
                        'bytes_sent': info['bytes_sent'] or 0,
                        'bytes_received': info['bytes_received'] or 0,
                    }
                )
            else:
                lg.warn('unknown proto %r: %r' % (proto, connection))
            result.append(item)
    return RESULT(result)


def streams_list(protocols: str = None):
    """
    Returns list of running streams of data fragments with recent upload/download progress percentage.

    ###### HTTP
        curl -X GET 'localhost:8180/stream/list/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "streams_list", "kwargs": {} }');
    """
    if not driver.is_on('service_gateway'):
        return ERROR('service_gateway() is not started')
    from bitdust.transport import gateway
    from bitdust.lib import misc
    result = []
    if protocols:
        protocols = protocols.split(',')
    else:
        protocols = gateway.list_active_transports()
    for proto in protocols:
        if not gateway.is_ready():
            continue
        if not gateway.is_installed(proto):
            continue
        for stream in gateway.list_active_streams(proto):
            item = {
                'proto': proto,
                'stream_id': '',
                'type': '',
                'bytes_current': -1,
                'bytes_total': -1,
                'progress': '0%',
            }
            if proto == 'tcp':
                if hasattr(stream, 'bytes_received'):
                    item.update({'stream_id': stream.file_id, 'type': 'in', 'bytes_current': stream.bytes_received, 'bytes_total': stream.size, 'progress': misc.value2percent(stream.bytes_received, stream.size, 0)})
                elif hasattr(stream, 'bytes_sent'):
                    item.update({'stream_id': stream.file_id, 'type': 'out', 'bytes_current': stream.bytes_sent, 'bytes_total': stream.size, 'progress': misc.value2percent(stream.bytes_sent, stream.size, 0)})
            elif proto == 'udp':
                if hasattr(stream.consumer, 'bytes_received'):
                    item.update(
                        {
                            'stream_id': stream.stream_id,
                            'type': 'in',
                            'bytes_current': stream.consumer.bytes_received,
                            'bytes_total': stream.consumer.size,
                            'progress': misc.value2percent(stream.consumer.bytes_received, stream.consumer.size, 0),
                        }
                    )
                elif hasattr(stream.consumer, 'bytes_sent'):
                    item.update(
                        {
                            'stream_id': stream.stream_id,
                            'type': 'out',
                            'bytes_current': stream.consumer.bytes_sent,
                            'bytes_total': stream.consumer.size,
                            'progress': misc.value2percent(stream.consumer.bytes_sent, stream.consumer.size, 0)
                        }
                    )
            elif proto == 'proxy':
                pass
            result.append(item)
    return RESULT(result)


#------------------------------------------------------------------------------


def queues_list():
    """
    Returns list of all registered streaming queues.

    ###### HTTP
        curl -X GET 'localhost:8180/queue/list/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "queues_list", "kwargs": {} }');
    """
    if not driver.is_on('service_p2p_notifications'):
        return ERROR('service_p2p_notifications() is not started')
    from bitdust.stream import p2p_queue
    return RESULT([{
        'queue_id': queue_id,
        'messages': len(p2p_queue.queue(queue_id)),
    } for queue_id in p2p_queue.queue().keys()])


def queue_consumers_list():
    """
    Returns list of all registered queue consumers.

    ###### HTTP
        curl -X GET 'localhost:8180/queue/consumer/list/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "queue_consumers_list", "kwargs": {} }');
    """
    if not driver.is_on('service_p2p_notifications'):
        return ERROR('service_p2p_notifications() is not started')
    from bitdust.stream import p2p_queue

    def _cmd_name(c):
        try:
            return c.__name__
        except:
            return c

    return RESULT(
        [
            {
                'consumer_id': consumer_info.consumer_id,
                'queues': consumer_info.queues,
                'commands': ['%s: %s' % (_cmd_name(com), ','.join(q_lst) if q_lst else '*') for com, q_lst in consumer_info.commands.items()],
                'state': consumer_info.state,
                'consumed': consumer_info.consumed_messages,
            } for consumer_info in p2p_queue.consumer().values()
        ]
    )


def queue_producers_list():
    """
    Returns list of all registered queue producers.

    ###### HTTP
        curl -X GET 'localhost:8180/queue/producer/list/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "queue_producers_list", "kwargs": {} }');
    """
    if not driver.is_on('service_p2p_notifications'):
        return ERROR('service_p2p_notifications() is not started')
    from bitdust.stream import p2p_queue
    return RESULT([{
        'producer_id': producer_info.producer_id,
        'queues': producer_info.queues,
        'state': producer_info.state,
        'produced': producer_info.produced_messages,
    } for producer_info in p2p_queue.producer().values()])


def queue_keepers_list():
    """
    Returns list of all registered queue keepers.

    ###### HTTP
        curl -X GET 'localhost:8180/queue/keeper/list/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "queue_keepers_list", "kwargs": {} }');
    """
    if not driver.is_on('service_message_broker'):
        return ERROR('service_message_broker() is not started')
    return RESULT([])


def queue_peddlers_list():
    """
    Returns list of all registered message peddlers.

    ###### HTTP
        curl -X GET 'localhost:8180/queue/peddler/list/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "queue_peddlers_list", "kwargs": {} }');
    """
    if not driver.is_on('service_message_broker'):
        return ERROR('service_message_broker() is not started')
    return RESULT([])


def queue_streams_list():
    """
    Returns list of all registered message peddlers.

    ###### HTTP
        curl -X GET 'localhost:8180/queue/stream/list/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "queue_streams_list", "kwargs": {} }');
    """
    if not driver.is_on('service_joint_postman'):
        return ERROR('service_joint_postman() is not started')
    from bitdust.stream import postman
    return RESULT(
        [{
            'queue_id': queue_id,
            'active': mp['active'],
            'consumers': list(mp['consumers'].keys()),
            'producers': list(mp['producers'].keys()),
            'sequence_id': mp['last_sequence_id'],
        } for queue_id, mp in postman.streams().items()]
    )


#------------------------------------------------------------------------------


def events_list():
    """
    Returns an overall statistic of the all logged events since the start of the main process.

    ###### HTTP
        curl -X GET 'localhost:8180/event/list/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "events_list", "kwargs": {} }');
    """
    from bitdust.main import events
    return OK(events.count())


def event_send(event_id: str, data: str = None):
    """
    Method will generate and inject a new event inside the main process.

    This method is provided for testing and development purposes.

    ###### HTTP
        curl -X POST 'localhost:8180/event/send/event-abc/v1' -d '{"data": "{\"some_key\":\"some_value\"}"}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "event_send", "kwargs": {"event_id": "event-abc", "data": "{\"some_key\":\"some_value\"}"} }');
    """
    from bitdust.main import events
    json_payload = data
    if data and strng.is_string(data):
        try:
            json_payload = jsn.loads(strng.to_text(data or '{}'))
        except:
            return ERROR('json data payload is not correct')
    evt = events.send(event_id, data=json_payload)
    if _Debug:
        lg.out(_DebugLevel, 'api.event_send %r was fired to local node' % event_id)
    return OK({
        'event_id': event_id,
        'created': evt.created,
    })


def event_listen(consumer_callback_id: str):
    """
    This method can be used by clients to listen and process all events fired inside the main process.

    If there are no pending events fired yet, this method will block and will be waiting for any new event.

    If some messages are already waiting in the stream to be consumed method will return them immediately.
    As soon as client received and processed the response events are marked as "consumed" and released from the buffer.

    Client should call that method again to listen for next events. This is very similar to a long polling technique.

    This method is only make sense for HTTP interface, because using a WebSocket client will receive application events directly.

    ###### HTTP
        curl -X GET 'localhost:8180/event/listen/my-client-event-hook/v1'

    """
    from bitdust.main import events
    ret = Deferred()

    def _on_pending_events(pending_events):
        result = []
        for evt in pending_events:
            if evt['type'] != 'event':
                continue
            result.append({
                'id': evt['id'],
                'data': evt['data'],
                'time': evt['time'],
            })
        ret.callback(OK(result, api_method='event_listen'))
        return len(result) > 0

    d = events.consume_events(consumer_callback_id)
    d.addCallback(_on_pending_events)
    d.addErrback(lambda err: ret.callback(ERROR(err, api_method='event_listen')))
    return ret


#------------------------------------------------------------------------------


def dht_node_find(node_id_64: str = None, layer_id: int = 0):
    """
    Lookup "closest" (in terms of hashes and cryptography) DHT nodes to a given `node_id_64` value.

    Method can be also used to pick a random DHT node from the network if you do not pass any value to `node_id_64`.

    Parameter `layer_id` specifies which layer of the routing table to be used.

    ###### HTTP
        curl -X GET 'localhost:8180/dht/node/find/v1?node_id_64=4271c8f079695d77f80186ac9365e3df949ff74d'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "dht_node_find", "kwargs": {"node_id_64": "4271c8f079695d77f80186ac9365e3df949ff74d"} }');
    """
    if not driver.is_on('service_entangled_dht'):
        return ERROR('service_entangled_dht() is not started')
    from bitdust.dht import dht_service
    if node_id_64 is None:
        node_id = dht_service.random_key()
        node_id_64 = node_id
    else:
        node_id = node_id_64
    ret = Deferred()

    def _cb(response):
        try:
            if isinstance(response, list):
                return ret.callback(
                    OK(
                        {
                            'my_dht_id': dht_service.node().layers[0],
                            'lookup': node_id_64,
                            'closest_nodes': [{
                                'dht_id': c.id,
                                'address': '%s:%d' % (strng.to_text(c.address, errors='ignore'), c.port),
                            } for c in response],
                        },
                        api_method='dht_node_find',
                    ),
                )
            return ret.callback(ERROR('unexpected DHT response', api_method='dht_node_find'))
        except Exception as exc:
            lg.exc()
            return ret.callback(ERROR(exc, api_method='dht_node_find'))

    def _eb(err):
        lg.err(err)
        ret.callback(ERROR(err, api_method='dht_node_find'))
        return None

    d = dht_service.find_node(node_id, layer_id=layer_id)
    d.addCallback(_cb)
    d.addErrback(_eb)
    return ret


def dht_user_random(layer_id: int = 0, count: int = 1):
    """
    Pick random live nodes from BitDust network.

    Method is used during services discovery, for example when you need to hire a new supplier to store your data.

    Parameter `layer_id` specifies which layer of the routing table to be used.

    ###### HTTP
        curl -X GET 'localhost:8180/dht/user/random/v1?count=2&layer_id=2'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "dht_node_find", "kwargs": {"count": 2, "layer_id": 2} }');
    """
    if not driver.is_on('service_nodes_lookup'):
        return ERROR('service_nodes_lookup() is not started')
    from bitdust.p2p import lookup
    ret = Deferred()

    def _cb(idurls):
        if not idurls:
            ret.callback(ERROR('no users were found', api_method='dht_user_random'))
            return None
        return ret.callback(RESULT(result=idurls, api_method='dht_user_random'))

    def _eb(err):
        lg.err(err)
        ret.callback(ERROR(err, api_method='dht_user_random'))
        return None

    def _process(idurl, node):
        result = Deferred()
        result.callback(idurl)
        return result

    tsk = lookup.start(
        count=count,
        layer_id=layer_id,
        consume=True,
        force_discovery=True,
        process_method=_process,
    )
    tsk.result_defer.addCallback(_cb)
    tsk.result_defer.addErrback(_eb)
    tsk.result_defer.addTimeout(timeout=30, clock=reactor)
    return ret


def dht_value_get(key: str, record_type: str = 'skip_validation', layer_id: int = 0, use_cache_ttl: int = None):
    """
    Fetch single key/value record from DHT network.

    ###### HTTP
        curl -X GET 'localhost:8180/dht/value/get/v1?key=abcd'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "dht_value_get", "kwargs": {"key": "abcd"} }');
    """
    if not driver.is_on('service_entangled_dht'):
        return ERROR('service_entangled_dht() is not started')
    from bitdust.dht import dht_service
    from bitdust.dht import dht_records
    ret = Deferred()

    record_rules = dht_records.get_rules(record_type)
    if not record_rules:
        return ERROR('record must be have correct type and known validation rules')

    def _cb(value):
        if isinstance(value, dict):
            if _Debug:
                lg.out(_DebugLevel, 'api.dht_value_get OK: %r' % value)
            return ret.callback(OK(
                {
                    'read': 'success',
                    'my_dht_id': dht_service.node().layers[0],
                    'key': strng.to_text(key, errors='ignore'),
                    'value': value,
                },
                api_method='dht_value_get',
            ))
        closest_nodes = []
        if isinstance(value, list):
            closest_nodes = value
        if _Debug:
            lg.out(_DebugLevel, 'api.dht_value_get ERROR: %r' % value)
        return ret.callback(
            OK(
                {
                    'read': 'failed',
                    'my_dht_id': dht_service.node().layers[0],
                    'key': strng.to_text(key, errors='ignore'),
                    'closest_nodes': [{
                        'dht_id': c.id,
                        'address': '%s:%d' % (strng.to_text(c.address, errors='ignore'), c.port),
                    } for c in closest_nodes],
                },
                api_method='dht_value_get',
            )
        )

    def _eb(err):
        lg.err(err)
        ret.callback(ERROR(err, api_method='dht_value_get'))
        return None

    d = dht_service.get_valid_data(
        key=key,
        rules=record_rules,
        raise_for_result=False,
        return_details=True,
        layer_id=layer_id,
        use_cache_ttl=use_cache_ttl,
    )
    d.addCallback(_cb)
    d.addErrback(_eb)
    return ret


def dht_value_set(key: str, value: str, expire: int = None, record_type: str = 'skip_validation', layer_id: int = 0):
    """
    Writes given key/value record into DHT network. Input parameter `value` must be a JSON value.

    ###### HTTP
        curl -X POST 'localhost:8180/dht/value/set/v1' -d '{"key": "abcd", "value": "{\"text\":\"A-B-C-D\"}" }'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "dht_value_set", "kwargs": {"key": "abcd", "value": "{\"text\":\"A-B-C-D\"}"} }');
    """
    if not driver.is_on('service_entangled_dht'):
        return ERROR('service_entangled_dht() is not started')

    if not isinstance(value, dict):
        try:
            value = jsn.loads(value)
        except Exception as exc:
            lg.exc()
            return ERROR('input value must be a json')
    try:
        jsn.dumps(value, indent=0, sort_keys=True, separators=(',', ':'))
    except Exception as exc:
        return ERROR(exc)

    from bitdust.dht import dht_service
    from bitdust.dht import dht_records
    ret = Deferred()

    record_rules = dht_records.get_rules(record_type)
    if not record_rules:
        return ERROR('record must be have correct type and known validation rules')

    def _cb(response):
        try:
            if isinstance(response, list):
                if _Debug:
                    lg.out(_DebugLevel, 'api.dht_value_set OK: %r' % response)
                return ret.callback(
                    OK(
                        {
                            'write': 'success' if len(response) > 0 else 'failed',
                            'my_dht_id': dht_service.node().layers[0],
                            'key': strng.to_text(key, errors='ignore'),
                            'value': value,
                            'closest_nodes': [{
                                'dht_id': c.id,
                                'address': '%s:%d' % (strng.to_text(c.address, errors='ignore'), c.port),
                            } for c in response],
                        },
                        api_method='dht_value_set',
                    )
                )
            if _Debug:
                lg.out(_DebugLevel, 'api.dht_value_set ERROR: %r' % response)
            return ret.callback(ERROR('unexpected DHT response', api_method='dht_value_set'))
        except Exception as exc:
            lg.exc()
            return ret.callback(ERROR(exc, api_method='dht_value_set'))

    def _eb(err):
        try:
            nodes = []
            try:
                errmsg = err.value.subFailure.getErrorMessage()
            except:
                try:
                    errmsg = err.getErrorMessage()
                except:
                    errmsg = 'store operation failed'
            try:
                nodes = err.value
            except:
                pass
            closest_nodes = []
            if nodes and isinstance(nodes, list) and hasattr(nodes[0], 'address') and hasattr(nodes[0], 'port'):
                closest_nodes = [{
                    'dht_id': c.id,
                    'address': '%s:%d' % (strng.to_text(c.address, errors='ignore'), c.port),
                } for c in nodes]
            if _Debug:
                lg.out(_DebugLevel, 'api.dht_value_set ERROR: %r' % errmsg)
            return ret.callback(ERROR(
                errmsg,
                details={
                    'write': 'failed',
                    'my_dht_id': dht_service.node().layers[0],
                    'key': strng.to_text(key, errors='ignore'),
                    'closest_nodes': closest_nodes,
                },
                api_method='dht_value_set',
            ))
        except Exception as exc:
            lg.exc()
            return ERROR(exc, api_method='dht_value_set')

    d = dht_service.set_valid_data(
        key=key,
        json_data=value,
        expire=expire or dht_service.KEY_EXPIRE_MAX_SECONDS,
        rules=record_rules,
        collect_results=True,
        layer_id=layer_id,
    )
    d.addCallback(_cb)
    d.addErrback(_eb)
    return ret


def dht_local_db_dump():
    """
    Method used for testing purposes, returns full list of all key/values stored locally on that DHT node.

    ###### HTTP
        curl -X GET 'localhost:8180/dht/db/dump/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "dht_local_db_dump", "kwargs": {} }');
    """
    if not driver.is_on('service_entangled_dht'):
        return ERROR('service_entangled_dht() is not started')
    from bitdust.dht import dht_service
    return RESULT(dht_service.dump_local_db(value_as_json=True))


#------------------------------------------------------------------------------


def blockchain_info():
    """
    Returns details and brief info about current status of blockchain services.

    ###### HTTP
        curl -X GET 'localhost:8180/blockchain/info/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "blockchain_info", "kwargs": {} }');
    """
    if not driver.is_on('service_bismuth_blockchain'):
        return ERROR('service_bismuth_blockchain() is not started')
    ret = {}
    if driver.is_on('service_bismuth_pool'):
        from bitdust.blockchain import bismuth_pool
        ret['mining_pool'] = {
            'address': bismuth_pool.address,
            'connected_node': '{}:{}'.format(bismuth_pool.node_ip, bismuth_pool.node_port) if bismuth_pool.node_ip else None,
            'difficulty': bismuth_pool.new_diff,
        }
    if driver.is_on('service_bismuth_node'):
        from bitdust.blockchain import bismuth_node
        ret['node'] = {
            'app_version': bismuth_node.nod().app_version,
            'protocol_version': bismuth_node.nod().version,
            'port': bismuth_node.nod().port,
            'difficulty': bismuth_node.nod().difficulty[0],
            'blocks': bismuth_node.nod().hdd_block,
            'last_block': bismuth_node.nod().last_block,
            'last_block_ago': bismuth_node.nod().last_block_ago,
            'port': bismuth_node.nod().port,
            'uptime': int(time.time() - bismuth_node.nod().startup_time),
            'address': bismuth_node.nod().keys.address,
            'connections': bismuth_node.nod().peers.consensus_size,
            'connections_list': bismuth_node.nod().peers.peer_opinion_dict,
            'consensus': bismuth_node.nod().peers.consensus,
            'consensus_percent': bismuth_node.nod().peers.consensus_percentage,
        }
    if driver.is_on('service_bismuth_wallet'):
        from bitdust.blockchain import bismuth_wallet
        cur_balance = bismuth_wallet.my_balance()
        ret['wallet'] = {
            'balance': cur_balance,
            'address': bismuth_wallet.my_wallet_address(),
        }
    if driver.is_on('service_bismuth_miner'):
        from bitdust.blockchain import bismuth_miner
        ret['miner'] = {
            'address': bismuth_miner._MinerWalletAddress,
            'name': bismuth_miner._MinerName,
            'connected_mining_pool': '{}:{}'.format(bismuth_miner._MiningPoolHost, bismuth_miner._MiningPoolPort) if bismuth_miner._MiningPoolHost else None,
        }
    return OK(ret)


def blockchain_wallet_balance():
    """
    Returns current balance of your blockchain wallet.

    ###### HTTP
        curl -X GET 'localhost:8180/blockchain/wallet/balance/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "blockchain_wallet_balance", "kwargs": {} }');
    """
    if not driver.is_on('service_bismuth_wallet'):
        return ERROR('service_bismuth_wallet() is not started')
    from bitdust.blockchain import bismuth_wallet
    cur_balance = bismuth_wallet.my_balance()
    return OK({
        'balance': cur_balance,
        'address': bismuth_wallet.my_wallet_address(),
    })


def blockchain_transaction_send(recipient: str, amount: float, operation: str = '', data: str = ''):
    """
    Prepare and sign blockchain transaction and then send it to one of known blockchain nodes.

    ###### HTTP
        curl -X POST 'localhost:8180/blockchain/transaction/send/v1' -d '{"recipient": "abcd...", "amount": 12.3456}'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "blockchain_transaction_send", "kwargs": {"recipient": "abcd...", "amount": 12.3456} }');
    """
    if not driver.is_on('service_bismuth_wallet'):
        return ERROR('service_bismuth_wallet() is not started')
    try:
        amount = float(amount)
    except:
        return ERROR(errors=['amount must be a number'])
    from bitdust.blockchain import bismuth_wallet
    result = bismuth_wallet.send_transaction(recipient, amount, operation, data)
    if result and not isinstance(result, list):
        return OK({
            'transaction_id': result,
        })
    return ERROR(errors=result)


def blockchain_block_produce():
    """
    Will trigger minining one time to produce a single empty block in the blockchain.
    This way foundation miners can initially generate enough coins to be able to sell those coins to customers.

    This method only make sense to use by foundation miners.
    If you are not part of the foundation and your wallet address is not on the list, your transaction will be rejected by other nodes.

    ###### HTTP
        curl -X GET 'localhost:8180/blockchain/block/produce/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "blockchain_block_produce", "kwargs": {} }');
    """
    if not driver.is_on('service_bismuth_miner'):
        return ERROR('service_bismuth_miner() is not started')
    from bitdust.blockchain import bismuth_miner
    bismuth_miner._WantMoreCoins = True
    bismuth_miner._MiningIsOn = False
    return OK()


#------------------------------------------------------------------------------


def billing_info():
    return ERROR('method is not implemented yet')


def billing_offers_list():
    return ERROR('method is not implemented yet')


def billing_offer_create():
    return ERROR('method is not implemented yet')


def billing_bid_create():
    return ERROR('method is not implemented yet')


def billing_bid_accept():
    return ERROR('method is not implemented yet')


#------------------------------------------------------------------------------


def automats_list():
    """
    Returns a list of all currently running state machines.

    This is a very useful method when you need to investigate a problem in the software.

    ###### HTTP
        curl -X GET 'localhost:8180/automat/list/v1'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "automats_list", "kwargs": {} }');
    """
    from bitdust.automats import automat
    result = [a.to_json(short=False) for a in automat.objects().values()]
    if _Debug:
        lg.out(_DebugLevel, 'api.automats_list responded with %d items' % len(result))
    return OK(result)


def automat_info(index: int = None, automat_id: str = None):
    """
    Returns detailed info about given state machine.

    Target instance is selected using one of the identifiers: `index` (integer) or `automat_id` (string).

    ###### HTTP
        curl -X GET 'localhost:8180/automat/info/v1?index=12345'

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "automat_info", "kwargs": {"index": 12345} }');
    """
    if index is None and automat_id is None:
        return ERROR('one of the identifiers must be provided')
    if index is not None and automat_id is not None:
        return ERROR('only one of the identifiers must be provided')
    from bitdust.automats import automat
    inst = None
    if automat_id is not None:
        inst = automat.by_id(automat_id)
    else:
        inst = automat.by_index(int(index))
    if not inst:
        return ERROR('state machine instance was not found')
    return OK(inst.to_json())


def automat_events_start(index: int = None, automat_id: str = None, state_unchanged: bool = False):
    """
    Can be used to capture any state machine updates in real-time: state transitions, incoming events.

    Changes will be published as "events" and can be captured with `event_listen()` API method.

    Positive value of parameter `state_unchanged` will enable all updates from the state machine -
    even when incoming automat event did not changed its state it will be published.

    Target instance is selected using one of the identifiers: `index` (integer) or `automat_id` (string).

    ###### HTTP
        curl -X POST 'localhost:8180/automat/events/start/v1' -d '{"index": 12345, "state_unchanged": true}

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "automat_events_start", "kwargs": {"index": 12345, "state_unchanged": true} }');
    """
    if index is None and automat_id is None:
        return ERROR('one of the identifiers must be provided')
    if index is not None and automat_id is not None:
        return ERROR('only one of the identifiers must be provided')
    from bitdust.automats import automat
    inst = None
    if automat_id is not None:
        inst = automat.by_id(automat_id)
    else:
        inst = automat.by_index(int(index))
    if not inst:
        return ERROR('state machine instance was not found')
    inst.publishEvents(True, publish_event_state_not_changed=state_unchanged)
    return OK(message='started publishing events from the state machine', result=inst.to_json())


def automat_events_stop(index: int = None, automat_id: str = None):
    """
    Turn off publishing of the state machine updates as events.

    Target instance is selected using one of the identifiers: `index` (integer) or `automat_id` (string).

    ###### HTTP
        curl -X POST 'localhost:8180/automat/events/stop/v1' -d '{"index": 12345}

    ###### WebSocket
        websocket.send('{"command": "api_call", "method": "automat_events_stop", "kwargs": {"index": 12345} }');
    """
    if index is None and automat_id is None:
        return ERROR('one of the identifiers must be provided')
    if index is not None and automat_id is not None:
        return ERROR('only one of the identifiers must be provided')
    from bitdust.automats import automat
    inst = None
    if automat_id is not None:
        inst = automat.by_id(automat_id)
    else:
        inst = automat.by_index(int(index))
    if not inst:
        return ERROR('state machine instance was not found')
    inst.publishEvents(False, publish_event_state_not_changed=False)
    return OK(message='stopped publishing events from the state machine', result=inst.to_json())
