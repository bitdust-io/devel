#!/usr/bin/python
# api.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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
from six.moves import map

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 8

#------------------------------------------------------------------------------

import os
import sys
import time
import gc

from twisted.internet.defer import Deferred
from twisted.python.failure import Failure

#------------------------------------------------------------------------------

from lib import strng
from lib import jsn

from logs import lg

from services import driver

#------------------------------------------------------------------------------


def on_api_result_prepared(result):
    # TODO
    return result

#------------------------------------------------------------------------------


def OK(result='', message=None, status='OK', extra_fields=None):
    o = {'status': status, }
    if result:
        o['result'] = result if isinstance(result, list) else [result, ]
    if message is not None:
        o['message'] = message
    if extra_fields is not None:
        o.update(extra_fields)
    o = on_api_result_prepared(o)
    api_method = sys._getframe().f_back.f_code.co_name
    if api_method.count('lambda') or api_method.startswith('_'):
        api_method = sys._getframe(1).f_back.f_code.co_name
    if _Debug:
        if api_method not in [
            'process_health',
            'network_connected',
        ] or _DebugLevel > 10:
            lg.out(_DebugLevel, 'api.%s return OK(%s)' % (api_method, jsn.dumps(o, sort_keys=True)[:150]))
    return o


def RESULT(result=[], message=None, status='OK', errors=None, source=None):
    o = {}
    if source is not None:
        o.update(source)
    o.update({'status': status, 'result': result})
    if message is not None:
        o['message'] = message
    if errors is not None:
        o['errors'] = errors
    o = on_api_result_prepared(o)
    api_method = sys._getframe().f_back.f_code.co_name
    if api_method.count('lambda'):
        api_method = sys._getframe(1).f_back.f_code.co_name
    if _Debug:
        try:
            sample = jsn.dumps(o, ensure_ascii=True, sort_keys=True)[:150]
        except:
            sample = strng.to_text(0, errors='ignore')[:150]
        lg.out(_DebugLevel, 'api.%s return RESULT(%s)' % (api_method, sample))
    return o


def ERROR(errors=[], message=None, status='ERROR', extra_fields=None):
    if isinstance(errors, Exception):
        try:
            errors = str(errors)
        except:
            errors = 'unknown exception'
    elif isinstance(errors, Failure):
        try:
            errors = errors.getErrorMessage()
        except:
            errors = 'unknown failure'
    o = {'status': status,
         'errors': errors if isinstance(errors, list) else [errors, ]}
    if message is not None:
        o['message'] = message
    if extra_fields is not None:
        o.update(extra_fields)
    o = on_api_result_prepared(o)
    api_method = sys._getframe().f_back.f_code.co_name
    if api_method.count('lambda'):
        api_method = sys._getframe(1).f_back.f_code.co_name
    if _Debug:
        lg.out(_DebugLevel, 'api.%s return ERROR(%s)' % (api_method, jsn.dumps(o, sort_keys=True)[:150]))
    return o

#------------------------------------------------------------------------------


def process_stop():
    """
    Stop the main process immediately.

    Return:

        {'status': 'OK', 'result': 'stopped'}
    """
    if _Debug:
        lg.out(_DebugLevel, 'api.process_stop sending event "stop" to the shutdowner() machine')
    from twisted.internet import reactor  # @UnresolvedImport
    from main import shutdowner
    reactor.callLater(0.1, shutdowner.A, 'stop', 'exit')  # @UndefinedVariable
    # shutdowner.A('stop', 'exit')
    return OK('stopped')


def process_restart(showgui=False):
    """
    Restart the main process, if flag show=True the GUI will be opened after
    restart.

    Return:

        {'status': 'OK', 'result': 'restarted'}
    """
    from twisted.internet import reactor  # @UnresolvedImport
    from main import shutdowner
    if showgui:
        if _Debug:
            lg.out(_DebugLevel, 'api.process_restart sending event "stop" to the shutdowner() machine')
        reactor.callLater(0.1, shutdowner.A, 'stop', 'restartnshow')  # @UndefinedVariable
        # shutdowner.A('stop', 'restartnshow')
        return OK('restarted with GUI')
    if _Debug:
        lg.out(_DebugLevel, 'api.process_restart sending event "stop" to the shutdowner() machine')
    # shutdowner.A('stop', 'restart')
    reactor.callLater(0.1, shutdowner.A, 'stop', 'restart')  # @UndefinedVariable
    return OK('restarted')


def process_show():
    """
    Deprecated.
    Opens a default web browser to show the BitDust GUI.

    Return:

        {'status': 'OK',   'result': '"show" event has been sent to the main process'}
    """
    if _Debug:
        lg.out(_DebugLevel, 'api.process_show')
    # TODO: raise up electron window ?
    return OK('"show" event has been sent to the main process')


def process_health():
    """
    Returns true if system is running 

    Return:

        {'status': 'OK' }
    """
    if _Debug:
        lg.out(_DebugLevel + 10, 'api.process_health')
    return OK()


def process_debug():
    """
    Execute a breakpoint inside main thread and start Python shell using standard `pdb.set_trace()` debugger.
    """
    import pdb
    pdb.set_trace()
    return OK()

#------------------------------------------------------------------------------

def config_get(key):
    """
    Returns current value for specific option from program settings.

    Return:

        {'status': 'OK',   'result': [{'type': 'positive integer', 'value': '8', 'key': 'logs/debug-level'}]}
    """
    try:
        key = str(key).strip('/')
    except:
        return ERROR('wrong key')
    if _Debug:
        lg.out(_DebugLevel, 'api.config_get [%s]' % key)
    from main import config
    if key and not config.conf().exist(key):
        return ERROR('option "%s" not exist' % key)

    if key and not config.conf().hasChilds(key):
        return RESULT([config.conf().toJson(key), ], )
    childs = []
    for child in config.conf().listEntries(key):
        if config.conf().hasChilds(child):
            childs.append({
                'key': child,
                'childs': len(config.conf().listEntries(child)),
            })
        else:
            childs.append(config.conf().toJson(child))
    return RESULT(childs)


def config_set(key, value):
    """
    Set a value for given option.

    Return:

        {'status': 'OK', 'result': [{'type': 'positive integer', 'old_value': '8', 'value': '10', 'key': 'logs/debug-level'}]}
    """
    key = str(key)
    from main import config
    v = {}
    if config.conf().exist(key):
        v['old_value'] = config.conf().getValueOfType(key)
    typ_label = config.conf().getTypeLabel(key)
    if _Debug:
        lg.out(_DebugLevel, 'api.config_set [%s]=%s type is %s' % (key, value, typ_label))
    config.conf().setValueOfType(key, value)
    v.update(config.conf().toJson(key))
    return RESULT([v, ])


def config_list(sort=False):
    """
    Provide detailed info about all options and values from settings.

    Return:

        {'status': 'OK',
         'result': [{
            'type': 'boolean',
            'value': 'true',
            'key': 'services/backups/enabled'
         }, {
            'type': 'boolean',
            'value': 'false',
            'key': 'services/backups/keep-local-copies-enabled'
         }, {
            'type': 'diskspace',
            'value': '128 MB',
            'key': 'services/backups/max-block-size'
        }]}
    """
    if _Debug:
        lg.out(_DebugLevel, 'api.config_list')
    from main import config
    r = config.conf().cache()
    r = [config.conf().toJson(key) for key in list(r.keys())]
    if sort:
        r = sorted(r, key=lambda i: i['key'])
    return RESULT(r)


def config_tree():
    """
    Returns all options as a tree.
    """
    if _Debug:
        lg.out(_DebugLevel, 'api.config_list')
    from main import config
    r = {}
    for key in config.conf().cache():
        cursor = r
        for part in key.split('/'):
            if part not in cursor:
                cursor[part] = {}
            cursor = cursor[part]
        cursor.update(config.conf().toJson(key))
    return RESULT(result=[r, ])

#------------------------------------------------------------------------------

def identity_get(include_xml_source=False):
    """
    """
    from userid import my_id
    if not my_id.isLocalIdentityReady():
        return ERROR('local identity is not valid or not exist')
    r = my_id.getLocalIdentity().serialize_json()
    if include_xml_source:
        r['xml'] = my_id.getLocalIdentity().serialize(as_text=True)
    return RESULT([r, ])


def identity_create(username, preferred_servers=[]):
    from lib import misc
    from userid import my_id
    from userid import id_registrator
    try:
        username = str(username)
    except:
        return ERROR('invalid user name')
    if not misc.ValidUserName(username):
        return ERROR('invalid user name')

    ret = Deferred()
    my_id_registrator = id_registrator.A()

    def _id_registrator_state_changed(oldstate, newstate, event_string, *args, **kwargs):
        if ret.called:
            return
        if newstate == 'FAILED':
            ret.callback(ERROR(my_id_registrator.last_message))
            return
        if newstate == 'DONE':
            my_id.loadLocalIdentity()
            if not my_id.isLocalIdentityReady():
                return ERROR('identity creation failed, please try again later')
            r = my_id.getLocalIdentity().serialize_json()
            r['xml'] = my_id.getLocalIdentity().serialize(as_text=True)
            ret.callback(RESULT([r, ]))
            return

    my_id_registrator.addStateChangedCallback(_id_registrator_state_changed)
    my_id_registrator.A('start', username=username, preferred_servers=preferred_servers)
    return ret


def identity_backup(destination_filepath):
    from userid import my_id
    from crypt import key
    from system import bpio
    if not my_id.isLocalIdentityReady():
        return ERROR('local identity is not ready')
    # TextToSave = strng.to_text(my_id.getLocalIDURL()) + u"\n" + key.MyPrivateKey()
    TextToSave = ''
    for id_source in my_id.getLocalIdentity().getSources():
        TextToSave += strng.to_text(id_source) + u'\n'
    TextToSave += key.MyPrivateKey()
    if not bpio.WriteTextFile(destination_filepath, TextToSave):
        del TextToSave
        gc.collect()
        return ERROR('error writing to %s\n' % destination_filepath)
    del TextToSave
    gc.collect()
    return OK(message='WARNING! keep your master key in a safe place and never ever publish it anywhere!')


def identity_recover(private_key_source, known_idurl=None):
    from userid import my_id
    from userid import id_restorer

    if not private_key_source:
        return ERROR('must provide private key in order to recover your identity')
    if len(private_key_source) > 1024 * 10:
        return ERROR('private key is too large')

    idurl_list = []
    pk_source = ''
    try:
        lines = private_key_source.split('\n')
        for i in range(len(lines)):
            line = lines[i]
            if not line.startswith('-----BEGIN RSA PRIVATE KEY-----'):
                idurl_list.append(strng.to_bin(line.strip()))
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

#     idurl = ''
#     pk_source = ''
#     try:
#         lines = private_key_source.split('\n')
#         idurl = lines[0]
#         pk_source = '\n'.join(lines[1:])
#         if idurl != nameurl.FilenameUrl(nameurl.UrlFilename(idurl)):
#             idurl = ''
#             pk_source = private_key_source
#     except:
#         idurl = ''
#         pk_source = private_key_source
#     if not idurl and known_idurl:
#         idurl = known_idurl
#     if not idurl:
#         return ERROR('you must specify the global IDURL address where your identity file was last located')

    ret = Deferred()
    my_id_restorer = id_restorer.A()

    def _id_restorer_state_changed(oldstate, newstate, event_string, *args, **kwargs):
        if ret.called:
            return
        if newstate == 'FAILED':
            ret.callback(ERROR(my_id_restorer.last_message))
            return
        if newstate == 'RESTORED!':
            my_id.loadLocalIdentity()
            if not my_id.isLocalIdentityReady():
                return ERROR('identity recovery FAILED')
            r = my_id.getLocalIdentity().serialize_json()
            r['xml'] = my_id.getLocalIdentity().serialize(as_text=True)
            ret.callback(RESULT([r, ]))
            return

    try:
        my_id_restorer.addStateChangedCallback(_id_restorer_state_changed)
        my_id_restorer.A('start', {'idurl': idurl_list[0], 'keysrc': pk_source, })
        # TODO: iterate over idurl_list to find at least one reliable source
    except Exception as exc:
        lg.exc()
        ret.callback(ERROR(str(exc)))

    return ret

def identity_list():
    """
    """
    from contacts import identitycache
    results = []
    for id_obj in identitycache.Items().values():
        r = id_obj.serialize_json()
        results.append(r)
    results.sort(key=lambda r: r['name'])
    return RESULT(results)

#------------------------------------------------------------------------------

def key_get(key_id, include_private=False):
    """
    Returns details of known private key.
    Use `include_private=True` to get Private Key as openssh formated string.

    Return:

        {'status': 'OK'.
         'result': [{
            'alias': 'cool',
            'creator': 'http://p2p-id.ru/testveselin.xml',
            'key_id': 'cool$testveselin@p2p-id.ru',
            'fingerprint': '50:f9:f1:6d:e3:e4:25:61:0c:81:6f:79:24:4e:78:17',
            'size': '4096',
            'ssh_type': 'ssh-rsa',
            'type': 'RSA',
            'public': 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQCPy7AXI0HuQSdmMF...',
            'private': '-----BEGIN RSA PRIVATE KEY-----\nMIIJKAIBAAKCAgEAj8uw...'
        }]}
    """
    if not driver.is_on('service_keys_registry'):
        return ERROR('service_keys_registry() is not started')
    if _Debug:
        lg.out(_DebugLevel, 'api.key_get')
    from crypt import my_keys
    try:
        r = my_keys.get_key_info(key_id=key_id, include_private=include_private)
    except Exception as exc:
        return ERROR(str(exc))
    return RESULT([r, ])


def keys_list(sort=False, include_private=False):
    """
    List details for known Private Keys.
    Use `include_private=True` to get Private Keys as openssh formated strings.

    Return:
        {'status': 'OK',
         'result': [{
             'alias': 'master',
             'key_id': 'master$veselin@p2p-id.ru',
             'creator': 'http://p2p-id.ru/veselin.xml',
             'fingerprint': '60:ce:ea:98:bf:3d:aa:ba:29:1e:b9:0c:3e:5c:3e:32',
             'size': '2048',
             'ssh_type': 'ssh-rsa',
             'type': 'RSA',
             'public': 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDbpo3VYR5zvLe5...'
             'private': '-----BEGIN RSA PRIVATE KEY-----\nMIIJKAIBAAKCAgEAj8uw...'
         }, {
             'alias': 'another_key01',
             'key_id': 'another_key01$veselin@p2p-id.ru',
             'creator': 'http://p2p-id.ru/veselin.xml',
             'fingerprint': '43:c8:3b:b6:da:3e:8a:3c:48:6f:92:bb:74:b4:05:6b',
             'size': '4096',
             'ssh_type': 'ssh-rsa',
             'type': 'RSA',
             'public': 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQCmgX6j2MwEyY...'
             'private': '-----BEGIN RSA PRIVATE KEY-----\nMIIJKsdAIBSjfAdfguw...'
        }]}
    """
    if not driver.is_on('service_keys_registry'):
        return ERROR('service_keys_registry() is not started')
    if _Debug:
        lg.out(_DebugLevel, 'api.keys_list')
    from crypt import my_keys
    r = []
    for key_id, key_object in my_keys.known_keys().items():
        if not key_object:
            key_object = my_keys.key_obj(key_id)
        key_alias, creator_idurl = my_keys.split_key_id(key_id)
        if not key_alias or not creator_idurl:
            lg.warn('incorrect key_id: %s' % key_id)
            continue
        try:
            key_info = my_keys.make_key_info(key_object, key_id=key_id, include_private=include_private)
        except:
            key_info = my_keys.make_key_info(key_object, key_id=key_id, include_private=False)
        r.append(key_info)
    if sort:
        r = sorted(r, key=lambda i: i['alias'])
    r.insert(0, my_keys.make_master_key_info(include_private=include_private))
    return RESULT(r)


def key_create(key_alias, key_size=None, include_private=False):
    """
    Generate new Private Key and add it to the list of known keys with given `key_id`.

    Return:

        {'status': 'OK',
         'message': 'new private key "abcd" was generated successfully',
         'result': [{
            'alias': 'abcd',
            'id': 'abcd$veselin@p2p-id.ru',
            'creator': 'http://p2p-id.ru/veselin.xml',
            'fingerprint': 'bb:16:97:65:59:23:c2:5d:62:9d:ce:7d:36:73:c6:1f',
            'size': '4096',
            'ssh_type': 'ssh-rsa',
            'type': 'RSA',
            'public': 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQC8w2MhOPR/IoQ...'
            'private': '-----BEGIN RSA PRIVATE KEY-----\nMIIJKsdAIBSjfAdfguw...'
        }]}
    """
    if not driver.is_on('service_keys_registry'):
        return ERROR('service_keys_registry() is not started')
    from crypt import my_keys
    from main import settings
    from userid import my_id
    key_alias = str(key_alias)
    key_alias = key_alias.strip().lower()
    key_id = my_keys.make_key_id(key_alias, creator_idurl=my_id.getLocalID())
    if not my_keys.is_valid_key_id(key_id):
        return ERROR('key "%s" is not valid' % key_id)
    if my_keys.is_key_registered(key_id):
        return ERROR('key "%s" already exist' % key_id)
    if not key_size:
        key_size = settings.getPrivateKeySize()
    if _Debug:
        lg.out(_DebugLevel, 'api.key_create id=%s, size=%s' % (key_id, key_size))
    key_object = my_keys.generate_key(key_id, key_size=key_size)
    if key_object is None:
        return ERROR('failed to generate private key "%s"' % key_id)
    return OK(my_keys.make_key_info(
        key_object,
        key_id=key_id,
        include_private=include_private
    ), message='new private key "%s" was generated successfully' % key_alias, )


def key_erase(key_id):
    """
    Removes Private Key from the list of known keys and erase local file.

    Return:

        {'status': 'OK',
         'message': 'private key "ccc2" was erased successfully',
        }
    """
    if not driver.is_on('service_keys_registry'):
        return ERROR('service_keys_registry() is not started')
    from crypt import my_keys
    key_id = str(key_id)
    if _Debug:
        lg.out(_DebugLevel, 'api.keys_list')
    if key_id == 'master':
        return ERROR('"master" key can not be removed')
    key_alias, creator_idurl = my_keys.split_key_id(key_id)
    if not key_alias or not creator_idurl:
        return ERROR('icorrect key_id format')
    if not my_keys.erase_key(key_id):
        return ERROR('failed to erase private key "%s"' % key_alias)
    return OK(message='private key "%s" was erased successfully' % key_alias)


def key_share(key_id, trusted_global_id_or_idurl, include_private=False, timeout=10):
    """
    Connects to remote node and transfer private key to that machine.
    This way remote user will be able to access those of your files which were encrypted with that private key.
    You can also share a public key, this way your supplier will know which data packets can be accessed by
    another customer.

    Returns:

    """
    from userid import global_id
    try:
        trusted_global_id_or_idurl = str(trusted_global_id_or_idurl)
        full_key_id = str(key_id)
    except:
        return ERROR('error reading input parameters')
    if not driver.is_on('service_keys_registry'):
        return ERROR('service_keys_registry() is not started')
    glob_id = global_id.ParseGlobalID(full_key_id)
    if glob_id['key_alias'] == 'master':
        return ERROR('"master" key can not be shared')
    if not glob_id['key_alias'] or not glob_id['idurl']:
        return ERROR('icorrect key_id format')
    idurl = trusted_global_id_or_idurl
    if global_id.IsValidGlobalUser(idurl):
        idurl = global_id.GlobalUserToIDURL(idurl)
    from access import key_ring
    ret = Deferred()
    d = key_ring.share_key(key_id=full_key_id, trusted_idurl=idurl, include_private=include_private, timeout=timeout)
    d.addCallback(
        lambda resp: ret.callback(
            OK(str(resp))))
    d.addErrback(
        lambda err: ret.callback(
            ERROR(err.getErrorMessage())))
    return ret


def key_audit(key_id, untrusted_global_id_or_idurl, is_private=False, timeout=10):
    """
    Connects to remote node identified by `idurl` parameter and request audit
    of a public or private key `key_id` on that machine.
    Returns True in the callback if audit process succeed - that means remote user
    posses that public or private key.

    Returns:
    """
    from userid import global_id
    try:
        untrusted_global_id_or_idurl = str(untrusted_global_id_or_idurl)
        full_key_id = str(key_id)
    except:
        return ERROR('error reading input parameters')
    if not driver.is_on('service_keys_registry'):
        return ERROR('service_keys_registry() is not started')
    glob_id = global_id.ParseGlobalID(full_key_id)
    if not glob_id['key_alias'] or not glob_id['idurl']:
        return ERROR('icorrect key_id format')
    if global_id.IsValidGlobalUser(untrusted_global_id_or_idurl):
        idurl = global_id.GlobalUserToIDURL(untrusted_global_id_or_idurl)
    else:
        idurl = untrusted_global_id_or_idurl
    from access import key_ring
    ret = Deferred()
    if is_private:
        d = key_ring.audit_private_key(key_id=key_id, untrusted_idurl=idurl, timeout=timeout)
    else:
        d = key_ring.audit_public_key(key_id=key_id, untrusted_idurl=idurl, timeout=timeout)
    d.addCallback(
        lambda resp: ret.callback(
            OK(str(resp))))
    d.addErrback(
        lambda err: ret.callback(
            ERROR(err.getErrorMessage())))
    return ret

#------------------------------------------------------------------------------


def filemanager(json_request):
    """
    A service method to execute calls from GUI front-end and interact with web
    browser. This is a special "gates" created only for Ajax calls from GUI. It
    provides same methods as other functions here, but just in a different way.

        Request:
            {"params":{"mode":"stats"}}

        Response:
            {'bytes_donated': 8589934592,
             'bytes_indexed': 43349475,
             'bytes_needed': 104857600,
             'bytes_used_supplier': 21738768,
             'bytes_used_total': 86955072,
             'customers': 0,
             'files_count': 5,
             'folders_count': 0,
             'items_count': 15,
             'max_suppliers': 4,
             'online_suppliers': 0,
             'suppliers': 4,
             'timestamp': 1458669668.288339,
             'value_donated': '8 GB',
             'value_needed': '100 MB',
             'value_used_total': '82.93 MB'}

    You can also access those methods with another API "alias": `filemanager_{ mode }({ extra params })`

    WARNING: Those methods here will be deprecated and removed, use regular API methods instead.
    """
    if not driver.is_on('service_restores'):
        return ERROR('service_restores() is not started')
    from storage import filemanager_api
    return filemanager_api.process(json_request)

#------------------------------------------------------------------------------


def files_sync():
    """
    Sends "restart" event to backup_monitor() Automat, this should start "data
    synchronization" process with remote nodes. Normally all situations
    should be handled automatically so you wont run this method manually,
    but just in case.

    Return:

        {'status': 'OK', 'result': 'the main files sync loop has been restarted'}
    """
    if not driver.is_on('service_backups'):
        return ERROR('service_backups() is not started')
    if _Debug:
        lg.out(_DebugLevel, 'api.files_sync')
    from storage import backup_monitor
    backup_monitor.A('restart')
    if _Debug:
        lg.out(_DebugLevel, 'api.files_sync')
    return OK('the main files sync loop has been restarted')


def files_list(remote_path=None, key_id=None, recursive=True, all_customers=False,
               include_uploads=False, include_downloads=False, ):
    """
    Returns list of known files registered in the catalog under given `remote_path` folder.
    By default returns items from root of the catalog.
    If `key_id` is passed will only return items encrypted using that key.

    Return:
        { u'execution': u'0.001040',
          u'result': [
                       { u'childs': False,
                         u'customer': u'veselin@veselin-p2p.ru',
                         u'remote_path': u'master$veselin@veselin-p2p.ru:cats.png',
                         u'global_id': u'master$veselin@veselin-p2p.ru:1',
                         u'idurl': u'http://veselin-p2p.ru/veselin.xml',
                         u'key_id': u'master$veselin@veselin-p2p.ru',
                         u'latest': u'',
                         u'local_size': -1,
                         u'name': u'cats.png',
                         u'path': u'cats.png',
                         u'path_id': u'1',
                         u'size': 0,
                         u'type': u'file',
                         u'versions': []},
                       { u'childs': False,
                         u'customer': u'veselin@veselin-p2p.ru',
                         u'remote_path': u'master$veselin@veselin-p2p.ru:dogs.jpg',
                         u'global_id': u'master$veselin@veselin-p2p.ru:2',
                         u'idurl': u'http://veselin-p2p.ru/veselin.xml',
                         u'key_id': u'master$veselin@veselin-p2p.ru',
                         u'latest': u'',
                         u'local_size': 345418,
                         u'name': u'dogs.jpg',
                         u'path': u'dogs.jpg',
                         u'path_id': u'2',
                         u'size': 0,
                         u'type': u'file',
                         u'versions': []},
                      ],
          u'status': u'OK'}
    """
    if not driver.is_on('service_backups'):
        return ERROR('service_backups() is not started')
    if _Debug:
        lg.out(_DebugLevel, 'api.files_list remote_path=%s key_id=%s recursive=%s all_customers=%s include_uploads=%s include_downloads=%s' % (
            remote_path, key_id, recursive, all_customers, include_uploads, include_downloads, ))
    from storage import backup_fs
    from system import bpio
    from lib import misc
    from userid import global_id
    from crypt import my_keys
    result = []
    glob_path = global_id.ParseGlobalID(remote_path)
    norm_path = global_id.NormalizeGlobalID(glob_path.copy())
    remotePath = bpio.remotePath(norm_path['path'])
    customer_idurl = norm_path['idurl']
    if not all_customers and customer_idurl not in backup_fs.known_customers():
        return ERROR('customer "%s" not found' % customer_idurl)
    if all_customers:
        lookup = []
        for customer_idurl in backup_fs.known_customers():
            look = backup_fs.ListChildsByPath(
                path=remotePath,
                recursive=recursive,
                iter=backup_fs.fs(customer_idurl),
                iterID=backup_fs.fsID(customer_idurl),
            )
            if isinstance(look, list):
                lookup.extend(look)
            else:
                lg.warn(look)
    else:
        lookup = backup_fs.ListChildsByPath(
            path=remotePath,
            recursive=recursive,
            iter=backup_fs.fs(customer_idurl),
            iterID=backup_fs.fsID(customer_idurl),
        )
    if not isinstance(lookup, list):
        return ERROR(lookup)
    for i in lookup:
        # if not i['item']['k']:
        #     i['item']['k'] = my_id.getGlobalID(key_alias='master')
        if i['path_id'] == 'index':
            continue
        if key_id is not None and key_id != i['item']['k']:
            continue
        if glob_path['key_alias'] and i['item']['k']:
            if i['item']['k'] != my_keys.make_key_id(alias=glob_path['key_alias'], creator_glob_id=glob_path['customer']):
                continue
        key_alias = 'master'
        if i['item']['k']:
            real_key_id = i['item']['k']
            key_alias, real_idurl = my_keys.split_key_id(real_key_id)
            real_customer_id = global_id.UrlToGlobalID(real_idurl)
        else:
            real_key_id = my_keys.make_key_id(alias='master', creator_idurl=customer_idurl)
            real_idurl = customer_idurl
            real_customer_id = global_id.UrlToGlobalID(customer_idurl)
        full_glob_id = global_id.MakeGlobalID(path=i['path_id'], customer=real_customer_id, key_alias=key_alias, )
        full_remote_path = global_id.MakeGlobalID(path=i['path'], customer=real_customer_id, key_alias=key_alias, )
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
            'key_alias': key_alias,
            'childs': i['childs'],
            'versions': i['versions'],
            'uploads': {
                'running': [],
                'pending': [],
            },
            'downloads': [],
        }
        if include_uploads:
            from storage import backup_control
            backup_control.tasks()
            running = []
            for backupID in backup_control.FindRunningBackup(pathID=full_glob_id):
                j = backup_control.jobs().get(backupID)
                if j:
                    running.append({
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
                    })
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
            from storage import restore_monitor
            downloads = []
            for backupID in restore_monitor.FindWorking(pathID=full_glob_id):
                d = restore_monitor.GetWorkingRestoreObject(backupID)
                if d:
                    downloads.append({
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
                    })
            r['downloads'] = downloads
        result.append(r)        
    if _Debug:
        lg.out(_DebugLevel, '    %d items returned' % len(result))
    return RESULT(result)


def file_info(remote_path, include_uploads=True, include_downloads=True):
    """
    """
    if not driver.is_on('service_restores'):
        return ERROR('service_restores() is not started')
    if _Debug:
        lg.out(_DebugLevel, 'api.file_info remote_path=%s include_uploads=%s include_downloads=%s' % (
            remote_path, include_uploads, include_downloads))
    from storage import backup_fs
    from lib import misc
    from lib import packetid
    from system import bpio
    from userid import global_id
    glob_path = global_id.ParseGlobalID(remote_path)
    norm_path = global_id.NormalizeGlobalID(glob_path.copy())
    remotePath = bpio.remotePath(norm_path['path'])
    customer_idurl = norm_path['idurl']
    if customer_idurl not in backup_fs.known_customers():
        return ERROR('customer "%s" not found' % customer_idurl)
    pathID = backup_fs.ToID(remotePath, iter=backup_fs.fs(customer_idurl))
    if not pathID:
        return ERROR('path "%s" was not found in catalog' % remotePath)
    item = backup_fs.GetByID(pathID, iterID=backup_fs.fsID(customer_idurl))
    if not item:
        return ERROR('item "%s" is not found in catalog' % pathID)
    (item_size, item_time, versions) = backup_fs.ExtractVersions(pathID, item)  # , customer_id=norm_path['customer'])
    glob_path_item = norm_path.copy()
    glob_path_item['path'] = pathID
    key_alias = 'master'
    if item.key_id:
        key_alias = packetid.KeyAlias(item.key_id)
    r = {
        'remote_path': global_id.MakeGlobalID(
            path=norm_path['path'], customer=norm_path['customer'], key_alias=key_alias,),
        'global_id': global_id.MakeGlobalID(
            path=pathID,
            customer=norm_path['customer'],
            key_alias=key_alias, ),
        'customer': norm_path['customer'],
        'path_id': pathID,
        'path': remotePath,
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
    }
    if include_uploads:
        from storage import backup_control
        backup_control.tasks()
        running = []
        for backupID in backup_control.FindRunningBackup(pathID=pathID):
            j = backup_control.jobs().get(backupID)
            if j:
                running.append({
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
                })
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
        from storage import restore_monitor
        downloads = []
        for backupID in restore_monitor.FindWorking(pathID=pathID):
            d = restore_monitor.GetWorkingRestoreObject(backupID)
            if d:
                downloads.append({
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
                })
        r['downloads'] = downloads
    if _Debug:
        lg.out(_DebugLevel, 'api.file_info : "%s"' % pathID)
    return RESULT([r, ])


def file_create(remote_path, as_folder=False):
    """
    """
    if not driver.is_on('service_backups'):
        return ERROR('service_backups() is not started')
    if _Debug:
        lg.out(_DebugLevel, 'api.file_create remote_path=%s as_folder=%s' % (
            remote_path, as_folder, ))
    from storage import backup_fs
    from storage import backup_control
    from system import bpio
    from main import control
    from userid import global_id
    from crypt import my_keys
    parts = global_id.NormalizeGlobalID(global_id.ParseGlobalID(remote_path))
    if not parts['path']:
        return ERROR('invalid "remote_path" format')
    path = bpio.remotePath(parts['path'])
    pathID = backup_fs.ToID(path, iter=backup_fs.fs(parts['idurl']))
    keyID = my_keys.make_key_id(alias=parts['key_alias'], creator_glob_id=parts['customer'])
    keyAlias = parts['key_alias']
    if pathID:
        return ERROR('remote path "%s" already exist in catalog: "%s"' % (path, pathID))
    if as_folder:
        newPathID, parent_iter, parent_iterID = backup_fs.AddDir(
            path,
            read_stats=False,
            iter=backup_fs.fs(parts['idurl']),
            iterID=backup_fs.fsID(parts['idurl']),
            key_id=keyID,
        )
    else:
        parent_path = os.path.dirname(path)
        if not backup_fs.IsDir(parent_path, iter=backup_fs.fs(parts['idurl'])):
            if backup_fs.IsFile(parent_path, iter=backup_fs.fs(parts['idurl'])):
                return ERROR('remote path can not be assigned, file already exist: "%s"' % parent_path)
            parentPathID, parent_iter, parent_iterID = backup_fs.AddDir(
                parent_path,
                read_stats=False,
                iter=backup_fs.fs(parts['idurl']),
                iterID=backup_fs.fsID(parts['idurl']),
                key_id=keyID,
            )
            if _Debug:
                lg.out(_DebugLevel, 'api.file_create parent folder "%s" was created at "%s"' % (parent_path, parentPathID))
        id_iter_iterID = backup_fs.GetIteratorsByPath(
            parent_path,
            iter=backup_fs.fs(parts['idurl']),
            iterID=backup_fs.fsID(parts['idurl']),
        )
        if not id_iter_iterID:
            return ERROR('remote path can not be assigned, parent folder not found: "%s"' % parent_path)
        parentPathID = id_iter_iterID[0]
        newPathID, _, _ = backup_fs.PutItem(
            name=os.path.basename(path),
            parent_path_id=parentPathID,
            as_folder=as_folder,
            iter=id_iter_iterID[1],
            iterID=id_iter_iterID[2],
            key_id=keyID,
        )
        if not newPathID:
            return ERROR('remote path can not be assigned, failed to create a new item: "%s"' % path)
    backup_control.Save()
    control.request_update([('pathID', newPathID), ])
    full_glob_id = global_id.MakeGlobalID(customer=parts['customer'], path=newPathID, key_alias=keyAlias)
    full_remote_path = global_id.MakeGlobalID(customer=parts['customer'], path=parts['path'], key_alias=keyAlias)
    if _Debug:
        lg.out(_DebugLevel, 'api.file_create : "%s"' % full_glob_id)
    return OK(
        'new %s was created in "%s"' % (('folder' if as_folder else 'file'), full_glob_id),
        extra_fields={
            'path_id': newPathID,
            'key_id': keyID,
            'path': path,
            'remote_path': full_remote_path,
            'global_id': full_glob_id,
            'customer': parts['idurl'],
            'type': ('dir' if as_folder else 'file'),
        })


def file_delete(remote_path):
    """
    """
    if not driver.is_on('service_backups'):
        return ERROR('service_backups() is not started')
    if _Debug:
        lg.out(_DebugLevel, 'api.file_delete remote_path=%s' % remote_path)
    from storage import backup_fs
    from storage import backup_control
    from storage import backup_monitor
    from main import settings
    from main import control
    from lib import packetid
    from system import bpio
    from userid import global_id
    parts = global_id.NormalizeGlobalID(global_id.ParseGlobalID(remote_path))
    if not parts['idurl'] or not parts['path']:
        return ERROR('invalid "remote_path" format')
    path = bpio.remotePath(parts['path'])
    pathID = backup_fs.ToID(path, iter=backup_fs.fs(parts['idurl']))
    if not pathID:
        return ERROR('remote path "%s" was not found' % parts['path'])
    if not packetid.Valid(pathID):
        return ERROR('invalid item found: "%s"' % pathID)
    pathIDfull = packetid.MakeBackupID(parts['customer'], pathID)
    keyAlias = parts['key_alias'] or 'master'
    full_glob_id = global_id.MakeGlobalID(customer=parts['customer'], path=pathID, key_alias=keyAlias)
    full_remote_path = global_id.MakeGlobalID(customer=parts['customer'], path=parts['path'], key_alias=keyAlias)
    result = backup_control.DeletePathBackups(pathID=pathIDfull, saveDB=False, calculate=False)
    if not result:
        return ERROR('remote item "%s" was not found' % pathIDfull)
    backup_fs.DeleteLocalDir(settings.getLocalBackupsDir(), pathIDfull)
    backup_fs.DeleteByID(pathID, iter=backup_fs.fs(parts['idurl']), iterID=backup_fs.fsID(parts['idurl']))
    backup_fs.Scan()
    backup_fs.Calculate()
    backup_control.Save()
    backup_monitor.A('restart')
    control.request_update([('pathID', pathIDfull), ])
    if _Debug:
        lg.out(_DebugLevel, 'api.file_delete %s' % parts)
    return OK('item "%s" was deleted from remote suppliers' % pathIDfull, extra_fields={
        'path_id': pathIDfull,
        'path': path,
        'remote_path': full_remote_path,
        'global_id': full_glob_id,
        'customer': parts['idurl'],
    })


def files_uploads(include_running=True, include_pending=True):
    """
    Returns a list of currently running uploads and
    list of pending items to be uploaded.

    Return:

        { 'status': 'OK',
          'result': {
            'running': [{
                'aborting': False,
                'version': '0/0/3/1/F20160424013912PM',
                'block_number': 4,
                'block_size': 16777216,
                'bytes_processed': 67108864,
                'closed': False,
                'eccmap': 'ecc/4x4',
                'eof_state': False,
                'pipe': 0,
                'progress': 75.0142815704418,
                'reading': False,
                'source_path': '/Users/veselin/Downloads/some-ZIP-file.zip',
                'terminating': False,
                'total_size': 89461450,
                'work_blocks': 4
            }],
            'pending': [{
                'created': 'Wed Apr 27 15:11:13 2016',
                'id': 3,
                'source_path': '/Users/veselin/Downloads/another-ZIP-file.zip',
                'path_id': '0/0/3/2'
            }]
        }
    """
    if not driver.is_on('service_backups'):
        return ERROR('service_backups() is not started')
    from lib import misc
    from storage import backup_control
    if _Debug:
        lg.out(_DebugLevel, 'api.file_uploads include_running=%s include_pending=%s' % (include_running, include_pending, ))
        lg.out(_DebugLevel, '     %d jobs running, %d tasks pending' % (
            len(backup_control.jobs()), len(backup_control.tasks())))
    r = {'running': [], 'pending': [], }
    if include_running:
        r['running'].extend([{
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
        } for j in backup_control.jobs().values()])
    if include_pending:
        r['pending'].extend([{
            'task_id': t.number,
            'path_id': t.pathID,
            'source_path': t.localPath,
            'created': time.asctime(time.localtime(t.created)),
        } for t in backup_control.tasks()])
    return RESULT(r)


def file_upload_start(local_path, remote_path, wait_result=False, open_share=False):
    """
    """
    if not driver.is_on('service_backups'):
        return ERROR('service_backups() is not started')
    if _Debug:
        lg.out(_DebugLevel, 'api.file_upload_start local_path=%s remote_path=%s wait_result=%s open_share=%s' % (
            local_path, remote_path, wait_result, open_share, ))
    from system import bpio
    from storage import backup_fs
    from storage import backup_control
    from lib import packetid
    from main import control
    from userid import global_id
    from crypt import my_keys
    if not bpio.pathExist(local_path):
        return ERROR('local file or folder "%s" not exist' % local_path)
    parts = global_id.NormalizeGlobalID(remote_path)
    if not parts['idurl'] or not parts['path']:
        return ERROR('invalid "remote_path" format')
    path = bpio.remotePath(parts['path'])
    pathID = backup_fs.ToID(path, iter=backup_fs.fs(parts['idurl']))
    if not pathID:
        return ERROR('path "%s" not registered yet' % remote_path)
    keyID = my_keys.make_key_id(alias=parts['key_alias'], creator_glob_id=parts['customer'])
    customerID = global_id.MakeGlobalID(customer=parts['customer'], key_alias=parts['key_alias'])
    pathIDfull = packetid.MakeBackupID(customerID, pathID)
    if open_share and parts['key_alias'] != 'master':
        if not driver.is_on('service_shared_data'):
            return ERROR('service_shared_data() is not started')
        from access import shared_access_coordinator
        active_share = shared_access_coordinator.get_active_share(keyID)
        if not active_share:
            active_share = shared_access_coordinator.SharedAccessCoordinator(
                keyID, log_events=True, publish_events=False, )
        if active_share.state != 'CONNECTED':
            active_share.automat('restart')
    if wait_result:
        d = Deferred()
        tsk = backup_control.StartSingle(
            pathID=pathIDfull,
            localPath=local_path,
            keyID=keyID,
        )
        tsk.result_defer.addCallback(lambda result: d.callback(OK(
            'item "%s" uploaded, local path is: "%s"' % (remote_path, local_path),
            extra_fields={
                'remote_path': remote_path,
                'version': result[0],
                'key_id': tsk.keyID,
                'source_path': local_path,
                'path_id': pathID,
            }
        )))
        tsk.result_defer.addErrback(lambda result: d.callback(ERROR(
            'upload task %d for "%s" failed: %s' % (tsk.number, tsk.pathID, result[1], )
        )))
        backup_fs.Calculate()
        backup_control.Save()
        control.request_update([('pathID', pathIDfull), ])
        if _Debug:
            lg.out(_DebugLevel, 'api.file_upload_start %s with %s, wait_result=True' % (remote_path, pathIDfull))
        return d
    tsk = backup_control.StartSingle(
        pathID=pathIDfull,
        localPath=local_path,
        keyID=keyID,
    )
    tsk.result_defer.addCallback(lambda result: lg.info(
        'callback from api.file_upload_start.task(%s) done with %s' % (result[0], result[1], )))
    tsk.result_defer.addErrback(lambda result: lg.err(
        'errback from api.file_upload_start.task(%s) failed with %s' % (result[0], result[1], )))
    backup_fs.Calculate()
    backup_control.Save()
    control.request_update([('pathID', pathIDfull), ])
    if _Debug:
        lg.out(_DebugLevel, 'api.file_upload_start %s with %s' % (remote_path, pathIDfull))
    return OK(
        'uploading "%s" started, local path is: "%s"' % (remote_path, local_path),
        extra_fields={
            'remote_path': remote_path,
            'key_id': tsk.keyID,
            'source_path': local_path,
            'path_id': pathID,
        })


def file_upload_stop(remote_path):
    """
    """
    if not driver.is_on('service_backups'):
        return ERROR('service_backups() is not started')
    if _Debug:
        lg.out(_DebugLevel, 'api.file_upload_stop remote_path=%s' % remote_path)
    from storage import backup_control
    from storage import backup_fs
    from system import bpio
    from userid import global_id
    from lib import packetid
    parts = global_id.NormalizeGlobalID(global_id.ParseGlobalID(remote_path))
    if not parts['idurl'] or not parts['path']:
        return ERROR('invalid "remote_path" format')
    remotePath = bpio.remotePath(parts['path'])
    pathID = backup_fs.ToID(remotePath, iter=backup_fs.fs(parts['idurl']))
    if not pathID:
        return ERROR('remote path "%s" was not found' % parts['path'])
    if not packetid.Valid(pathID):
        return ERROR('invalid item found: "%s"' % pathID)
    pathIDfull = packetid.MakeBackupID(parts['customer'], pathID)
    r = []
    msg = []
    if backup_control.AbortPendingTask(pathIDfull):
        r.append(pathIDfull)
        msg.append('pending item "%s" removed' % pathIDfull)
    for backupID in backup_control.FindRunningBackup(pathIDfull):
        if backup_control.AbortRunningBackup(backupID):
            r.append(backupID)
            msg.append('backup "%s" aborted' % backupID)
    if not r:
        return ERROR('no running or pending tasks for "%s" found' % pathIDfull)
    if _Debug:
        lg.out(_DebugLevel, 'api.file_upload_stop %s' % r)
    return RESULT(r, message=(', '.join(msg)))


def files_downloads():
    """
    Returns a list of currently running downloads.

    Return:

        {'status': 'OK',
         'result': [{
            'aborted': False,
            'backup_id': '0/0/3/1/F20160427011209PM',
            'block_number': 0,
            'bytes_processed': 0,
            'creator_id': 'http://veselin-p2p.ru/veselin.xml',
            'done': False,
            'key_id': 'abc$veselin@veselin-p2p.ru',
            'created': 'Wed Apr 27 15:11:13 2016',
            'eccmap': 'ecc/4x4',
            'path_id': '0/0/3/1',
            'version': 'F20160427011209PM'
        }]}
    """
    if not driver.is_on('service_restores'):
        return ERROR('service_restores() is not started')
    from storage import restore_monitor
    if _Debug:
        lg.out(_DebugLevel, 'api.files_downloads')
        lg.out(_DebugLevel, '    %d items downloading at the moment' % len(restore_monitor.GetWorkingObjects()))
    return RESULT([{
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
    } for r in restore_monitor.GetWorkingObjects()])


def file_download_start(remote_path, destination_path=None, wait_result=False, open_share=True):
    """
    Download data from remote suppliers to your local machine. You can use
    different methods to select the target data with `remote_path` input:

      + "remote path" of the file
      + item ID in the catalog
      + full version identifier with item ID

    It is possible to select the destination folder to extract requested files to.
    By default this method uses specified value from local settings or user home folder

    WARNING: Your existing local data will be overwritten!

    Return:

        {'status': 'OK', 'result': 'downloading of version 0/0/1/1/0/F20160313043419PM has been started to /Users/veselin/'}
    """
    if not driver.is_on('service_restores'):
        return ERROR('service_restores() is not started')
    if _Debug:
        lg.out(_DebugLevel, 'api.file_download_start remote_path=%s destination_path=%s wait_result=%s open_share=%s' % (
            remote_path, destination_path, wait_result, open_share, ))
    from storage import backup_fs
    from storage import backup_control
    from storage import restore_monitor
    from main import control
    from system import bpio
    from lib import packetid
    from main import settings
    from userid import my_id
    from userid import global_id
    from crypt import my_keys
    glob_path = global_id.NormalizeGlobalID(global_id.ParseGlobalID(remote_path))
    if packetid.Valid(glob_path['path']):
        _, pathID, version = packetid.SplitBackupID(remote_path)
        if not pathID and version:
            pathID, version = version, ''
        item = backup_fs.GetByID(pathID, iterID=backup_fs.fsID(glob_path['customer']))
        if not item:
            return ERROR('path "%s" is not found in catalog' % remote_path)
        if not version:
            version = item.get_latest_version()
        if not version:
            return ERROR('not found any remote versions for "%s"' % remote_path)
        key_alias = 'master'
        if item.key_id:
            key_alias = packetid.KeyAlias(item.key_id)
        customerGlobalID = global_id.MakeGlobalID(customer=glob_path['customer'], key_alias=key_alias)
        backupID = packetid.MakeBackupID(customerGlobalID, pathID, version)
    else:
        remotePath = bpio.remotePath(glob_path['path'])
        knownPathID = backup_fs.ToID(remotePath, iter=backup_fs.fs(glob_path['idurl']))
        if not knownPathID:
            return ERROR('path "%s" was not found in catalog' % remotePath)
        item = backup_fs.GetByID(knownPathID, iterID=backup_fs.fsID(glob_path['idurl']))
        if not item:
            return ERROR('item "%s" is not found in catalog' % knownPathID)
        version = glob_path['version']
        if not version:
            version = item.get_latest_version()
        if not version:
            return ERROR('not found any remote versions for "%s"' % remote_path)
        key_alias = 'master'
        if item.key_id:
            key_alias = packetid.KeyAlias(item.key_id)
        customerGlobalID = global_id.MakeGlobalID(customer=glob_path['customer'], key_alias=key_alias)
        backupID = packetid.MakeBackupID(customerGlobalID, knownPathID, version)
    if backup_control.IsBackupInProcess(backupID):
        return ERROR('download not possible, uploading "%s" is in process' % backupID)
    if restore_monitor.IsWorking(backupID):
        return ERROR('downloading task for "%s" already scheduled' % backupID)
    customerGlobalID, pathID_target, version = packetid.SplitBackupID(backupID)
    if not customerGlobalID:
        customerGlobalID = global_id.UrlToGlobalID(my_id.getLocalID())
    knownPath = backup_fs.ToPath(pathID_target, iterID=backup_fs.fsID(global_id.GlobalUserToIDURL(customerGlobalID)))
    if not knownPath:
        return ERROR('location "%s" not found in catalog' % knownPath)
    if not destination_path:
        destination_path = settings.getRestoreDir()
    if not destination_path:
        destination_path = settings.DefaultRestoreDir()
    key_id = my_keys.make_key_id(alias=glob_path['key_alias'], creator_glob_id=glob_path['customer'])
    ret = Deferred()
        
    def _on_result(backupID, result):
        if result == 'restore done':
            ret.callback(OK(
                result,
                'version "%s" downloaded to "%s"' % (backupID, destination_path),
                extra_fields={
                    'backup_id': backupID,
                    'local_path': destination_path,
                    'path_id': pathID_target,
                    'remote_path': knownPath,
                },
            ))
        else:
            ret.callback(ERROR(
                'downloading version "%s" failed, result: %s' % (backupID, result),
                extra_fields={
                    'backup_id': backupID,
                    'local_path': destination_path,
                    'path_id': pathID_target,
                    'remote_path': knownPath,
                },
            ))
        return True
    
    def _start_restore():
        if _Debug:
            lg.out(_DebugLevel, 'api.file_download_start._start_restore %s to %s, wait_result=%s' % (
                backupID, destination_path, wait_result))
        if wait_result:
            restore_monitor.Start(backupID, destination_path, keyID=key_id, callback=_on_result)
            control.request_update([('pathID', knownPath), ])
            return ret
        restore_monitor.Start(backupID, destination_path, keyID=key_id, )
        control.request_update([('pathID', knownPath), ])
        ret.callback(OK(
            'started',
            'downloading of version "%s" has been started to "%s"' % (backupID, destination_path),
            extra_fields={
                'key_id': key_id,
                'backup_id': backupID,
                'local_path': destination_path,
                'path_id': pathID_target,
                'remote_path': knownPath,
            },
        ))
        return True
    
    def _on_share_connected(active_share, callback_id, result):
        if _Debug:
            lg.out(_DebugLevel, 'api.download_start._on_share_connected callback_id=%s result=%s' % (callback_id, result, ))
        if not result:
            if _Debug:
                lg.out(_DebugLevel, '    share %s is now DISCONNECTED, removing callback %s' % (active_share.key_id, callback_id,))
            active_share.remove_connected_callback(callback_id)
            ret.callback(ERROR(
                'downloading version "%s" failed, result: %s' % (backupID, 'share is disconnected'),
                extra_fields={
                    'key_id': active_share.key_id,
                    'backup_id': backupID,
                    'local_path': destination_path,
                    'path_id': pathID_target,
                    'remote_path': knownPath,
                },
            ))
            return True
        if _Debug:
            lg.out(_DebugLevel, '        share %s is now CONNECTED, removing callback %s and starting restore process' % (
                active_share.key_id, callback_id,))
        from twisted.internet import reactor  # @UnresolvedImport
        reactor.callLater(0, active_share.remove_connected_callback, callback_id)  # @UndefinedVariable
        _start_restore()
        return True

    def _open_share():
        if not driver.is_on('service_shared_data'):
            ret.callback(ERROR('service_shared_data() is not started'))
            return False
        from access import shared_access_coordinator
        active_share = shared_access_coordinator.get_active_share(key_id)
        if not active_share:
            active_share = shared_access_coordinator.SharedAccessCoordinator(
                key_id=key_id,
                log_events=True,
                publish_events=False,
            )
            if _Debug:
                lg.out(_DebugLevel, 'api.download_start._open_share opened new share : %s' % active_share.key_id)
        else:
            if _Debug:
                lg.out(_DebugLevel, 'api.download_start._open_share found existing share : %s' % active_share.key_id)
        if active_share.state != 'CONNECTED':
            cb_id = 'file_download_start_' + str(time.time())
            active_share.add_connected_callback(cb_id, lambda _id, _result: _on_share_connected(active_share, _id, _result))
            active_share.automat('restart')
            if _Debug:
                lg.out(_DebugLevel, 'api.download_start._open_share added callback %s to the active share : %s' % (cb_id, active_share.key_id))
        else:
            if _Debug:
                lg.out(_DebugLevel, 'api.download_start._open_share existing share %s is currently CONNECTED' % active_share.key_id)
            _start_restore()
        return True

    if open_share and key_alias != 'master':
        _open_share()
    else:
        if _Debug:
            lg.out(_DebugLevel, '    "open_share" skipped, starting restore')
        _start_restore()
    
    return ret


def file_download_stop(remote_path):
    """
    Abort currently running restore process.

    Return:

        {'status': 'OK', 'result': 'restoring of "alice@p2p-host.com:0/1/2" aborted'}
    """
    if not driver.is_on('service_restores'):
        return ERROR('service_restores() is not started')
    if _Debug:
        lg.out(_DebugLevel, 'api.file_download_stop remote_path=%s' % remote_path)
    from storage import backup_fs
    from storage import restore_monitor
    from system import bpio
    from lib import packetid
    from userid import my_id
    from userid import global_id
    glob_path = global_id.NormalizeGlobalID(global_id.ParseGlobalID(remote_path))
    backupIDs = []
    if packetid.Valid(glob_path['path']):
        customerGlobalID, pathID, version = packetid.SplitBackupID(remote_path)
        if not customerGlobalID:
            customerGlobalID = global_id.UrlToGlobalID(my_id.getLocalID())
        item = backup_fs.GetByID(pathID, iterID=backup_fs.fsID(glob_path['customer']))
        if not item:
            return ERROR('path "%s" is not found in catalog' % remote_path)
        versions = []
        if version:
            versions.append(version)
        if not versions:
            versions.extend(item.get_versions())
        for version in versions:
            backupIDs.append(packetid.MakeBackupID(customerGlobalID, pathID, version,
                                                   key_alias=glob_path['key_alias']))
    else:
        remotePath = bpio.remotePath(glob_path['path'])
        knownPathID = backup_fs.ToID(remotePath, iter=backup_fs.fs(glob_path['idurl']))
        if not knownPathID:
            return ERROR('path "%s" was not found in catalog' % remotePath)
        item = backup_fs.GetByID(knownPathID, iterID=backup_fs.fsID(glob_path['idurl']))
        if not item:
            return ERROR('item "%s" is not found in catalog' % knownPathID)
        versions = []
        if glob_path['version']:
            versions.append(glob_path['version'])
        if not versions:
            versions.extend(item.get_versions())
        for version in versions:
            backupIDs.append(packetid.MakeBackupID(glob_path['customer'], knownPathID, version,
                                                   key_alias=glob_path['key_alias']))
    if not backupIDs:
        return ERROR('not found any remote versions for "%s"' % remote_path)
    r = []
    for backupID in backupIDs:
        r.append({'backup_id': backupID, 'aborted': restore_monitor.Abort(backupID), })
    if _Debug:
        lg.out(_DebugLevel, '    stopping %s' % r)
    return RESULT(r)


def file_explore(local_path):
    """
    """
    from lib import misc
    from system import bpio
    locpath = bpio.portablePath(local_path)
    if not bpio.pathExist(locpath):
        return ERROR('local path not exist')
    misc.ExplorePathInOS(locpath)
    return OK()

#------------------------------------------------------------------------------

def share_list(only_active=False, include_mine=True, include_granted=True):
    """
    """
    if not driver.is_on('service_shared_data'):
        return ERROR('service_shared_data() is not started')
    from access import shared_access_coordinator
    from crypt import my_keys
    from userid import global_id
    from userid import my_id
    results = []
    if only_active:
        for key_id in shared_access_coordinator.list_active_shares():
            _glob_id = global_id.ParseGlobalID(key_id)
            to_be_listed = False
            if include_mine and _glob_id['idurl'] == my_id.getLocalIDURL():
                to_be_listed = True
            if include_granted and _glob_id['idurl'] != my_id.getLocalIDURL():
                to_be_listed = True
            if not to_be_listed:
                continue
            cur_share = shared_access_coordinator.get_active_share(key_id)
            if not cur_share:
                lg.warn('share %s not found' % key_id)
                continue
            results.append(cur_share.to_json())
        return RESULT(results)
    for key_id in my_keys.known_keys():
        if not key_id.startswith('share_'):
            continue
        _glob_id = global_id.ParseGlobalID(key_id)
        to_be_listed = False
        if include_mine and _glob_id['idurl'] == my_id.getLocalIDURL():
            to_be_listed = True
        if include_granted and _glob_id['idurl'] != my_id.getLocalIDURL():
            to_be_listed = True
        if not to_be_listed:
            continue
        results.append({
            'key_id': key_id,
            'idurl': _glob_id['idurl'],
            'state': None,
            'suppliers': [],
        })
    return RESULT(results)


def share_create(owner_id=None, key_size=2048):
    """
    """
    if not driver.is_on('service_shared_data'):
        return ERROR('service_shared_data() is not started')
    from crypt import key
    from crypt import my_keys
    from userid import my_id
    if not owner_id:
        owner_id = my_id.getGlobalID()
    key_id = None
    while True:
        random_sample = os.urandom(24)
        key_alias = 'share_%s' % strng.to_text(key.HashMD5(random_sample, hexdigest=True))
        key_id = my_keys.make_key_id(alias=key_alias, creator_glob_id=owner_id)
        if my_keys.is_key_registered(key_id):
            continue
        break
    key_object = my_keys.generate_key(key_id, key_size=key_size)
    if key_object is None:
        return ERROR('failed to generate private key "%s"' % key_id)
    return OK(my_keys.make_key_info(
        key_object,
        key_id=key_id,
        include_private=False,
    ), message='new share "%s" was generated successfully' % key_id, )


def share_grant(trusted_remote_user, key_id, timeout=30):
    """
    """
    if not driver.is_on('service_shared_data'):
        return ERROR('service_shared_data() is not started')
    from twisted.internet import reactor  # @UnresolvedImport
    key_id = strng.to_text(key_id)
    trusted_remote_user = strng.to_text(trusted_remote_user)
    if not key_id.startswith('share_'):
        return ERROR('invalid share name')
    from userid import global_id
    remote_idurl = strng.to_bin(trusted_remote_user)
    if trusted_remote_user.count('@'):
        glob_id = global_id.ParseGlobalID(trusted_remote_user)
        remote_idurl = glob_id['idurl']
    if not remote_idurl:
        return ERROR('wrong user id')
    from access import shared_access_donor
    ret = Deferred()

    def _on_shared_access_donor_success(result):
        ret.callback(OK() if result else ERROR(result))
        return None

    def _on_shared_access_donor_failed(err):
        ret.callback(ERROR(str(err)))
        return None

    d = Deferred()
    d.addCallback(_on_shared_access_donor_success)
    d.addErrback(_on_shared_access_donor_failed)
    d.addTimeout(timeout, clock=reactor)
    shared_access_donor_machine = shared_access_donor.SharedAccessDonor(log_events=True, publish_events=False, )
    shared_access_donor_machine.automat('init', trusted_idurl=remote_idurl, key_id=key_id, result_defer=d)
    return ret


def share_open(key_id):
    """
    """
    key_id = strng.to_text(key_id)
    if not driver.is_on('service_shared_data'):
        return ERROR('service_shared_data() is not started')
    if not key_id.startswith('share_'):
        return ERROR('invlid share name')
    from access import shared_access_coordinator
    active_share = shared_access_coordinator.get_active_share(key_id)
    new_share = False
    if not active_share:
        new_share = True
        active_share = shared_access_coordinator.SharedAccessCoordinator(key_id, log_events=True, publish_events=False, )
    ret = Deferred()

    def _on_shared_access_coordinator_state_changed(oldstate, newstate, event_string, *args, **kwargs):
        active_share.removeStateChangedCallback(_on_shared_access_coordinator_state_changed)
        if newstate == 'CONNECTED':
            if new_share:
                ret.callback(OK('share "%s" opened' % key_id, extra_fields=active_share.to_json()))
            else:
                ret.callback(OK('share "%s" refreshed' % key_id, extra_fields=active_share.to_json()))
        else:
            ret.callback(ERROR('share "%s" was not opened' % key_id, extra_fields=active_share.to_json()))
        return None

    active_share.addStateChangedCallback(_on_shared_access_coordinator_state_changed, oldstate=None, newstate='CONNECTED')
    active_share.addStateChangedCallback(_on_shared_access_coordinator_state_changed, oldstate=None, newstate='DISCONNECTED')
    active_share.automat('restart')
    return ret


def share_close(key_id):
    """
    """
    key_id = strng.to_text(key_id)
    if not driver.is_on('service_shared_data'):
        return ERROR('service_shared_data() is not started')
    if not key_id.startswith('share_'):
        return ERROR('invlid share name')
    from access import shared_access_coordinator
    this_share = shared_access_coordinator.get_active_share(key_id)
    if not this_share:
        return ERROR('this share is not opened')
    this_share.automat('shutdown')
    return OK('share "%s" closed' % key_id, extra_fields=this_share.to_json())


def share_history():
    """
    """
    if not driver.is_on('service_shared_data'):
        return ERROR('service_shared_data() is not started')
    return RESULT([],)

#------------------------------------------------------------------------------

def friend_list():
    """
    Returns list of correspondents ids
    """
    from contacts import contactsdb
    from userid import global_id
    result = []
    for idurl, alias in contactsdb.correspondents():
        glob_id = global_id.ParseIDURL(idurl)
        contact_status_label = None
        contact_state = None
        if driver.is_on('service_identity_propagate'):
            from p2p import online_status
            if online_status.isKnown(idurl):
                contact_state = online_status.getCurrentState(idurl)
                contact_status_label = online_status.getStatusLabel(idurl)
            # state_machine_inst = contact_status.getInstance(idurl)
            # if state_machine_inst:
            #     contact_status_label = contact_status.stateToLabel(state_machine_inst.state)
            #     contact_state = state_machine_inst.state
        result.append({
            'idurl': idurl,
            'global_id': glob_id['customer'],
            'idhost': glob_id['idhost'],
            'username': glob_id['user'],
            'alias': alias,
            'contact_status': contact_status_label,
            'contact_state': contact_state,
        })
    return RESULT(result)

def friend_add(idurl_or_global_id, alias=''):
    """
    Add user to the list of friends
    """
    from contacts import contactsdb
    from userid import global_id
    idurl = idurl_or_global_id
    if global_id.IsValidGlobalUser(idurl_or_global_id):
        idurl = global_id.GlobalUserToIDURL(idurl_or_global_id)
    if not idurl:
        return ERROR('you must specify the global IDURL address where your identity file was last located')
    if not contactsdb.is_correspondent(idurl):
        contactsdb.add_correspondent(idurl, alias)
        contactsdb.save_correspondents()
        return OK('new friend has been added')
    return OK('this friend has been already added')

def friend_remove(idurl_or_global_id):
    """
    Remove user from the list of friends
    """
    from contacts import contactsdb
    from userid import global_id
    idurl = idurl_or_global_id
    if global_id.IsValidGlobalUser(idurl_or_global_id):
        idurl = global_id.GlobalUserToIDURL(idurl_or_global_id)
    if not idurl:
        return ERROR('you must specify the global IDURL address where your identity file was last located')
    if contactsdb.is_correspondent(idurl):
        contactsdb.remove_correspondent(idurl)
        contactsdb.save_correspondents()
        return OK('friend has been removed')
    return ERROR('friend not found')

#------------------------------------------------------------------------------

def suppliers_list(customer_idurl_or_global_id=None, verbose=False):
    """
    This method returns a list of suppliers - nodes which stores your encrypted data on own machines.

    Return:

        {'status': 'OK',
         'result':[{
            'connected': '05-06-2016 13:06:05',
            'idurl': 'http://p2p-id.ru/bitdust_j_vps1014.xml',
            'files_count': 14,
            'position': 0,
            'contact_status': 'offline',
            'contact_state': 'OFFLINE'
         }, {
            'connected': '05-06-2016 13:04:57',
            'idurl': 'http://veselin-p2p.ru/bitdust_j_vps1001.xml',
            'files_count': 14,
            'position': 1,
            'contact_status': 'online'
            'contact_state': 'CONNECTED'
        }]}
    """
    if not driver.is_on('service_customer'):
        return ERROR('service_customer() is not started')
    from contacts import contactsdb
    from customer import supplier_connector
    from p2p import online_status
    from lib import misc
    from userid import my_id
    from userid import global_id
    from storage import backup_matrix
    customer_idurl = customer_idurl_or_global_id
    if not customer_idurl:
        customer_idurl = my_id.getLocalID()
    else:
        if global_id.IsValidGlobalUser(customer_idurl):
            customer_idurl = global_id.GlobalUserToIDURL(customer_idurl)
    results = []
    for (pos, supplier_idurl, ) in enumerate(contactsdb.suppliers(customer_idurl)):
        if not supplier_idurl:
            r = {
                'position': pos,
                'idurl': '',
                'global_id': '',
                'supplier_state': None,
                'connected': None,
                'contact_status': None,
                'contact_state': None,
            }
            results.append(r)
            continue
        r = {
            'position': pos,
            'idurl': supplier_idurl,
            'global_id': global_id.UrlToGlobalID(supplier_idurl),
            'supplier_state':
                None if not supplier_connector.is_supplier(supplier_idurl, customer_idurl)
                else supplier_connector.by_idurl(supplier_idurl, customer_idurl).state,
            'connected': misc.readSupplierData(supplier_idurl, 'connected', customer_idurl),
            'contact_status': None,
            'contact_state': None,
        }
        if online_status.isKnown(supplier_idurl):
            r['contact_status'] = online_status.getStatusLabel(supplier_idurl)
            r['contact_state'] = online_status.getCurrentState(supplier_idurl)
        # if contact_status.isKnown(supplier_idurl):
        #     cur_state = contact_status.getInstance(supplier_idurl).state
        #     r['contact_status'] = contact_status.stateToLabel(cur_state)
        #     r['contact_state'] = cur_state
        if verbose:
            _files, _total, _report = backup_matrix.GetSupplierStats(pos, customer_idurl=customer_idurl)
            r['listfiles'] = misc.readSupplierData(supplier_idurl, 'listfiles', customer_idurl)
            r['fragments'] = {
                'items': _files,
                'files': _total,
                'details': _report,
            }
        results.append(r)
    return RESULT(results)


def supplier_replace(index_or_idurl_or_global_id):
    """
    Execute a fire/hire process for given supplier, another random node will
    replace this supplier. As soon as new supplier is found and connected,
    rebuilding of all uploaded data will be started and the new node will start
    getting a reconstructed fragments.

    Return:

        {'status': 'OK', 'result': 'supplier http://p2p-id.ru/alice.xml will be replaced by new peer'}
    """
    if not driver.is_on('service_customer'):
        return ERROR('service_customer() is not started')
    from contacts import contactsdb
    from userid import my_id
    from userid import global_id
    customer_idurl = my_id.getLocalID()
    supplier_idurl = strng.to_text(index_or_idurl_or_global_id)
    if supplier_idurl.isdigit():
        supplier_idurl = contactsdb.supplier(int(supplier_idurl), customer_idurl=customer_idurl)
    else:
        if global_id.IsValidGlobalUser(supplier_idurl):
            supplier_idurl = global_id.GlobalUserToIDURL(supplier_idurl)
    if supplier_idurl and supplier_idurl and contactsdb.is_supplier(supplier_idurl, customer_idurl=customer_idurl):
        from customer import fire_hire
        fire_hire.AddSupplierToFire(supplier_idurl)
        fire_hire.A('restart')
        return OK('supplier "%s" will be replaced by new random peer' % supplier_idurl)
    return ERROR('supplier not found')


def supplier_change(index_or_idurl_or_global_id, new_supplier_idurl_or_global_id):
    """
    Doing same as supplier_replace() but new node must be provided by you - you can manually assign a supplier.

    Return:

        {'status': 'OK', 'result': 'supplier http://p2p-id.ru/alice.xml will be replaced by http://p2p-id.ru/bob.xml'}
    """
    if not driver.is_on('service_customer'):
        return ERROR('service_customer() is not started')
    from contacts import contactsdb
    from userid import my_id
    from userid import global_id
    customer_idurl = my_id.getLocalID()
    supplier_idurl = strng.to_text(index_or_idurl_or_global_id)
    if supplier_idurl.isdigit():
        supplier_idurl = contactsdb.supplier(int(supplier_idurl), customer_idurl=customer_idurl)
    else:
        if global_id.IsValidGlobalUser(supplier_idurl):
            supplier_idurl = global_id.GlobalUserToIDURL(supplier_idurl)
    new_supplier_idurl = new_supplier_idurl_or_global_id
    if global_id.IsValidGlobalUser(new_supplier_idurl):
        new_supplier_idurl = global_id.GlobalUserToIDURL(new_supplier_idurl)
    if not supplier_idurl or not contactsdb.is_supplier(supplier_idurl, customer_idurl=customer_idurl):
        return ERROR('supplier not found')
    if contactsdb.is_supplier(new_supplier_idurl, customer_idurl=customer_idurl):
        return ERROR('peer "%s" is your supplier already' % new_supplier_idurl)
    from customer import fire_hire
    from customer import supplier_finder
    supplier_finder.AddSupplierToHire(new_supplier_idurl)
    fire_hire.AddSupplierToFire(supplier_idurl)
    fire_hire.A('restart')
    return OK('supplier "%s" will be replaced by "%s"' % (supplier_idurl, new_supplier_idurl))


def suppliers_ping():
    """
    Sends short requests to all suppliers to get their current statuses.

    Return:

        {'status': 'OK',  'result': 'requests to all suppliers was sent'}
    """
    if not driver.is_on('service_customer'):
        return ERROR('service_customer() is not started')
    from p2p import propagate
    propagate.SlowSendSuppliers(0.1)
    return OK('requests to all suppliers was sent')


def suppliers_dht_lookup(customer_idurl_or_global_id):
    """
    Scans DHT network for key-value pairs related to given customer and
    returns a list of his "possible" suppliers.
    """
    if not driver.is_on('service_entangled_dht'):
        return ERROR('service_entangled_dht() is not started')
    from dht import dht_relations
    from userid import my_id
    from userid import global_id
    customer_idurl = customer_idurl_or_global_id
    if not customer_idurl:
        customer_idurl = my_id.getLocalID()
    else:
        if global_id.IsValidGlobalUser(customer_idurl):
            customer_idurl = global_id.GlobalUserToIDURL(customer_idurl)
    ret = Deferred()
    d = dht_relations.read_customer_suppliers(customer_idurl)
    d.addCallback(lambda result: ret.callback(RESULT(result)))
    d.addErrback(lambda err: ret.callback(ERROR([err, ])))
    return ret

#------------------------------------------------------------------------------


def customers_list(verbose=False):
    """
    List of customers - nodes who stores own data on your machine.

    Return:

        {'status': 'OK',
         'result': [ {  'idurl': 'http://p2p-id.ru/bob.xml',
                        'position': 0,
                        'status': 'offline'
        }]}
    """
    if not driver.is_on('service_supplier'):
        return ERROR('service_supplier() is not started')
    from contacts import contactsdb
    from p2p import online_status
    from userid import global_id
    results = []
    for pos, customer_idurl in enumerate(contactsdb.customers()):
        if not customer_idurl:
            r = {
                'position': pos,
                'global_id': '',
                'idurl': '',
                'contact_status': None,
                'contact_state': None,
            }
            results.append(r)
            continue
        r = {
            'position': pos,
            'global_id': global_id.UrlToGlobalID(customer_idurl),
            'idurl': customer_idurl,
            'contact_status': None,
            'contact_state': None,
        }
        if online_status.isKnown(customer_idurl):
            r['contact_status'] = online_status.getStatusLabel(customer_idurl)
            r['contact_state'] = online_status.getCurrentState(customer_idurl)
        # if contact_status.isKnown(customer_idurl):
        #     cur_state = contact_status.getInstance(customer_idurl).state
        #     r['contact_status'] = contact_status.stateToLabel(cur_state)
        #     r['contact_state'] = cur_state
        results.append(r)
    return RESULT(results)

def customer_reject(idurl_or_global_id):
    """
    Stop supporting given customer, remove all his files from local disc, close
    connections with that node.

    Return:

        {'status': 'OK', 'result': 'customer http://p2p-id.ru/bob.xml rejected, 536870912 bytes were freed'}
    """
    if not driver.is_on('service_supplier'):
        return ERROR('service_supplier() is not started')
    from contacts import contactsdb
    from storage import accounting
    from main import settings
    from main import events
    from supplier import local_tester
    from p2p import p2p_service
    from lib import packetid
    from userid import global_id
    customer_idurl = idurl_or_global_id
    if global_id.IsValidGlobalUser(customer_idurl):
        customer_idurl = global_id.GlobalUserToIDURL(customer_idurl)
    if not contactsdb.is_customer(customer_idurl):
        return ERROR('customer not found')
    # send packet to notify about service from us was rejected
    # TODO - this is not yet handled on other side
    p2p_service.SendFailNoRequest(customer_idurl, packetid.UniqueID(), 'service rejected')
    # remove from customers list
    current_customers = contactsdb.customers()
    current_customers.remove(customer_idurl)
    contactsdb.update_customers(current_customers)
    contactsdb.remove_customer_meta_info(customer_idurl)
    contactsdb.save_customers()
    # remove records for this customers from quotas info
    space_dict = accounting.read_customers_quotas()
    consumed_by_cutomer = space_dict.pop(customer_idurl, None)
    consumed_space = accounting.count_consumed_space(space_dict)
    space_dict[b'free'] = settings.getDonatedBytes() - int(consumed_space)
    accounting.write_customers_quotas(space_dict)
    events.send('existing-customer-terminated', dict(idurl=customer_idurl))
    # restart local tester
    local_tester.TestUpdateCustomers()
    return OK('customer "%s" rejected, "%s" bytes were freed' % (customer_idurl, consumed_by_cutomer))


def customers_ping():
    """
    Sends Identity packet to all customers to check their current statuses.
    Every node will reply with Ack packet on any valid incoming Identiy packet.

    Return:

        {'status': 'OK',  'result': 'requests to all customers was sent'}
    """
    if not driver.is_on('service_supplier'):
        return ERROR('service_supplier() is not started')
    from p2p import propagate
    propagate.SlowSendCustomers(0.1)
    return OK('requests to all customers was sent')

#------------------------------------------------------------------------------


def space_donated():
    """
    Returns detailed statistics about your donated space usage.

    Return:

        {'status': 'OK',
         'result': [{
            'consumed': 0,
            'consumed_percent': '0%',
            'consumed_str': '0 bytes',
            'customers': [],
            'customers_num': 0,
            'donated': 1073741824,
            'donated_str': '1024 MB',
            'free': 1073741824,
            'old_customers': [],
            'real': 0,
            'used': 0,
            'used_percent': '0%',
            'used_str': '0 bytes'
        }]}
    """
    from storage import accounting
    result = accounting.report_donated_storage()
    if _Debug:
        lg.out(_DebugLevel, 'api.space_donated finished with %d customers and %d errors' % (
        len(result['customers']), len(result['errors']),))
    for err in result['errors']:
        if _Debug:
            lg.out(_DebugLevel, '    %s' % err)
    errors = result.pop('errors', [])
    return RESULT([result, ], errors=errors,)


def space_consumed():
    """
    Returns some info about your current usage of BitDust resources.

    Return:

        {'status': 'OK',
         'result': [{
            'available': 907163720,
            'available_per_supplier': 907163720,
            'available_per_supplier_str': '865.14 MB',
            'available_str': '865.14 MB',
            'needed': 1073741824,
            'needed_per_supplier': 1073741824,
            'needed_per_supplier_str': '1024 MB',
            'needed_str': '1024 MB',
            'suppliers_num': 2,
            'used': 166578104,
            'used_per_supplier': 166578104,
            'used_per_supplier_str': '158.86 MB',
            'used_percent': '0.155%',
            'used_str': '158.86 MB'
        }]}
    """
    from storage import accounting
    result = accounting.report_consumed_storage()
    if _Debug:
        lg.out(_DebugLevel, 'api.space_consumed finished')
    return RESULT([result, ])


def space_local():
    """
    Returns detailed statistics about current usage of your local disk.

    Return:

        {'status': 'OK',
         'result': [{
            'backups': 0,
            'backups_str': '0 bytes',
            'customers': 0,
            'customers_str': '0 bytes',
            'diskfree': 103865696256,
            'diskfree_percent': '0.00162%',
            'diskfree_str': '96.73 GB',
            'disktotal': 63943473102848,
            'disktotal_str': '59552 GB',
            'temp': 48981,
            'temp_str': '47.83 KB',
            'total': 45238743,
            'total_percent': '0%',
            'total_str': '43.14 MB'
        }]}
    """
    from storage import accounting
    result = accounting.report_local_storage()
    if _Debug:
        lg.out(_DebugLevel, 'api.space_local finished')
    return RESULT([result, ],)

#------------------------------------------------------------------------------

def automats_list():
    """
    Returns a list of all currently running state machines.

    Return:

        {'status': 'OK',
         'result': [{
            'index': 1,
            'name': 'initializer',
            'state': 'READY',
            'timers': ''
          }, {
            'index': 2,
            'name': 'shutdowner',
            'state': 'READY',
            'timers': ''
        }]}
    """
    from automats import automat
    result = [{
        'index': a.index,
        'name': a.name,
        'state': a.state,
        'timers': (','.join(list(a.getTimers().keys()))),
    } for a in automat.objects().values()]
    if _Debug:
        lg.out(_DebugLevel, 'api.automats_list responded with %d items' % len(result))
    return RESULT(result)

#------------------------------------------------------------------------------


def services_list(show_configs=False):
    """
    Returns detailed info about all currently running network services.

    Return:

        {'status': 'OK',
         'result': [{
            'config_path': 'services/backup-db/enabled',
            'depends': ['service_list_files', 'service_data_motion'],
            'enabled': True,
            'index': 3,
            'installed': True,
            'name': 'service_backup_db',
            'state': 'ON'
          }, {
            'config_path': 'services/backups/enabled',
            'depends': ['service_list_files', 'service_employer', 'service_rebuilding'],
            'enabled': True,
            'index': 4,
            'installed': True,
            'name': 'service_backups',
            'state': 'ON'
        }]}
    """
    from main import config
    result = []
    for name, svc in sorted(list(driver.services().items()), key=lambda i: i[0]):
        svc_info = {
            'index': svc.index,
            'name': name,
            'state': svc.state,
            'enabled': svc.enabled(),
            'installed': svc.installed(),
            'depends': svc.dependent_on()
        }
        if show_configs:
            svc_configs = []
            for child in config.conf().listEntries(svc.config_path.replace('/enabled', '')):
                svc_configs.append(config.conf().toJson(child))
            svc_info['configs'] = svc_configs
        result.append(svc_info)
    if _Debug:
        lg.out(_DebugLevel, 'api.services_list responded with %d items' % len(result))
    return RESULT(result)


def service_info(service_name):
    """
    Returns detailed info for single service.

    Return:

        {'status': 'OK',
         'result': [{
            'config_path': 'services/tcp-connections/enabled',
            'depends': ['service_network'],
            'enabled': True,
            'index': 24,
            'installed': True,
            'name': 'service_tcp_connections',
            'state': 'ON'
        }]}
    """
    svc = driver.services().get(service_name, None)
    if svc is None:
        service_name = 'service_' + service_name.replace('-', '_')
        svc = driver.services().get(service_name, None)
    if svc is None:
        return ERROR('service "%s" not found' % service_name)
    return RESULT([{
        'index': svc.index,
        'name': svc.service_name,
        'state': svc.state,
        'enabled': svc.enabled(),
        'installed': svc.installed(),
        'config_path': svc.config_path,
        'depends': svc.dependent_on()
    }])


def service_start(service_name):
    """
    Start given service immediately. This method also set `True` for
    correspondent option in the program settings:

        .bitdust/config/services/[service name]/enabled

    If some other services, which is dependent on that service,
    were already enabled, they will be started also.

    Return:

        {'status': 'OK', 'result': 'service_tcp_connections was switched on'}
    """
    if _Debug:
        lg.out(_DebugLevel, 'api.service_start : %s' % service_name)
    from main import config
    svc = driver.services().get(service_name, None)
    if svc is None:
        service_name = 'service_' + service_name.replace('-', '_')
        svc = driver.services().get(service_name, None)
    if svc is None:
        lg.warn('service "%s" not found' % service_name)
        return ERROR('service "%s" was not found' % service_name)
    if svc.state == 'ON':
        lg.warn('service "%s" already started' % service_name)
        return ERROR('service "%s" already started' % service_name)
    current_config = config.conf().getBool(svc.config_path)
    if current_config:
        lg.warn('service "%s" already enabled' % service_name)
        return ERROR('service "%s" already enabled' % service_name)
    config.conf().setBool(svc.config_path, True)
    return OK('"%s" was switched on' % service_name)


def service_stop(service_name):
    """
    Stop given service immediately. It will also set `False` for correspondent
    option in the settings.

        .bitdust/config/services/[service name]/enabled

    Dependent services will be stopped as well.

    Return:

        {'status': 'OK', 'result': 'service_tcp_connections was switched off'}
    """
    if _Debug:
        lg.out(_DebugLevel, 'api.service_stop : %s' % service_name)
    from main import config
    svc = driver.services().get(service_name, None)
    if svc is None:
        service_name = 'service_' + service_name.replace('-', '_')
        svc = driver.services().get(service_name, None)
    if svc is None:
        lg.warn('service "%s" not found' % service_name)
        return ERROR('service "%s" not found' % service_name)
    current_config = config.conf().getBool(svc.config_path)
    if current_config is None:
        lg.warn('config item "%s" was not found' % svc.config_path)
        return ERROR('config item "%s" was not found' % svc.config_path)
    if current_config is False:
        lg.warn('service "%s" already disabled' % service_name)
        return ERROR('service "%s" already disabled' % service_name)
    config.conf().setBool(svc.config_path, False)
    return OK('"%s" was switched off' % service_name)


def service_restart(service_name, wait_timeout=10):
    """
    Stop given service and start it again, but only if it is already enabled.
    Do not change corresponding `.bitdust/config/services/[service name]/enabled` option.
    Dependent services will be "restarted" as well.
    Return:

        {'status': 'OK', 'result': 'service_tcp_connections was restarted'}
    """
    svc = driver.services().get(service_name, None)
    if _Debug:
        lg.out(_DebugLevel, 'api.service_restart : %s' % service_name)
    if svc is None:
        service_name = 'service_' + service_name.replace('-', '_')
        svc = driver.services().get(service_name, None)
    if svc is None:
        lg.warn('service "%s" not found' % service_name)
        return ERROR('service "%s" not found' % service_name)
    ret = Deferred()
    d = driver.restart(service_name, wait_timeout=wait_timeout)
    d.addCallback(
        lambda resp: ret.callback(OK(resp)))
    d.addErrback(
        lambda err: ret.callback(ERROR(err.getErrorMessage())))
    return ret

#------------------------------------------------------------------------------


def packets_stats():
    """
    Returns detailed info about current network usage.

    Return:

        {'status': 'OK',
         'result': [{
            'in': {
                'failed_packets': 0,
                'total_bytes': 0,
                'total_packets': 0,
                'unknown_bytes': 0,
                'unknown_packets': 0
            },
            'out': {
                'http://p2p-id.ru/bitdust_j_vps1014.xml': 0,
                'http://veselin-p2p.ru/bitdust_j_vps1001.xml': 0,
                'failed_packets': 8,
                'total_bytes': 0,
                'total_packets': 0,
                'unknown_bytes': 0,
                'unknown_packets': 0
        }}]}
    """
    if not driver.is_on('service_gateway'):
        return ERROR('service_gateway() is not started')
    from p2p import p2p_stats
    return RESULT([{
        'in': p2p_stats.counters_in(),
        'out': p2p_stats.counters_out(),
    }])


def packets_list():
    """
    Return list of incoming and outgoing packets.
    """
    if not driver.is_on('service_gateway'):
        return ERROR('service_gateway() is not started')
    from transport import packet_in
    from transport import packet_out
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
        result.append({
            'direction': 'outgoing',
            'command': pkt_out.outpacket.Command,
            'packet_id': pkt_out.outpacket.PacketID,
            'label': pkt_out.label,
            'target': pkt_out.remote_idurl,
            'description': pkt_out.description,
            'label': pkt_out.label,
            'response_timeout': pkt_out.response_timeout,
            'items': items,
        })
    for pkt_in in list(packet_in.inbox_items().values()):
        result.append({
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
        })
    return RESULT(result)

#------------------------------------------------------------------------------

def transfers_list():
    """
    """
    if not driver.is_on('service_data_motion'):
        return ERROR('service_data_motion() is not started')
    from customer import io_throttle
    from userid import global_id
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
                r['incoming'].append({
                    'packet_id': i.packetID,
                    'owner_id': i.ownerID,
                    'remote_id': i.remoteID,
                    'customer': i.customerID,
                    'remote_path': i.remotePath,
                    'filename': i.fileName,
                    'created': i.created,
                    'requested': i.requestTime,
                })
        result.append(r)
    return RESULT(result)

#------------------------------------------------------------------------------

def connections_list(wanted_protos=None):
    """
    Returns list of opened/active network connections. Argument `wanted_protos`
    can be used to select which protocols to list:

        connections_list(wanted_protos=['tcp', 'udp'])
    """
    if not driver.is_on('service_gateway'):
        return ERROR('service_gateway() is not started')
    from transport import gateway
    from userid import global_id
    result = []
    if not wanted_protos:
        wanted_protos = gateway.list_active_transports()
    for proto in wanted_protos:
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
                        host = '%s:%s' % (connection.peer_address[0], connection.peer_address[1])
                    except:
                        host = 'unknown'
                    item.update({
                        'status': 'active',
                        'state': connection.state,
                        'host': host,
                        'global_id': global_id.UrlToGlobalID(connection.peer_idurl or ''),
                        'idurl': connection.peer_idurl or '',
                        'bytes_sent': connection.total_bytes_sent,
                        'bytes_received': connection.total_bytes_received,
                    })
                else:
                    try:
                        host = '%s:%s' % (connection.connection_address[0], connection.connection_address[1])
                    except:
                        host = 'unknown'
                    item.update({
                        'status': 'connecting',
                        'host': host,
                    })
            elif proto == 'udp':
                try:
                    host = '%s:%s' % (connection.peer_address[0], connection.peer_address[1])
                except:
                    host = 'unknown'
                item.update({
                    'status': 'active',
                    'state': connection.state,
                    'host': host,
                    'global_id': global_id.UrlToGlobalID(connection.peer_idurl or ''),
                    'idurl': connection.peer_idurl or '',
                    'bytes_sent': connection.bytes_sent,
                    'bytes_received': connection.bytes_received,
                })
            result.append(item)
    return RESULT(result)

#------------------------------------------------------------------------------

def streams_list(wanted_protos=None):
    """
    Return list of active sending/receiveing files.
    """
    if not driver.is_on('service_gateway'):
        return ERROR('service_gateway() is not started')
    from transport import gateway
    from lib import misc
    result = []
    if not wanted_protos:
        wanted_protos = gateway.list_active_transports()
    for proto in wanted_protos:
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
                    item.update({
                        'stream_id': stream.file_id,
                        'type': 'in',
                        'bytes_current': stream.bytes_received,
                        'bytes_total': stream.size,
                        'progress': misc.value2percent(stream.bytes_received, stream.size, 0)
                    })
                elif hasattr(stream, 'bytes_sent'):
                    item.update({
                        'stream_id': stream.file_id,
                        'type': 'out',
                        'bytes_current': stream.bytes_sent,
                        'bytes_total': stream.size,
                        'progress': misc.value2percent(stream.bytes_sent, stream.size, 0)
                    })
            elif proto == 'udp':
                if hasattr(stream.consumer, 'bytes_received'):
                    item.update({
                        'stream_id': stream.stream_id,
                        'type': 'in',
                        'bytes_current': stream.consumer.bytes_received,
                        'bytes_total': stream.consumer.size,
                        'progress': misc.value2percent(stream.consumer.bytes_received, stream.consumer.size, 0)
                    })
                elif hasattr(stream.consumer, 'bytes_sent'):
                    item.update({
                        'stream_id': stream.stream_id,
                        'type': 'out',
                        'bytes_current': stream.consumer.bytes_sent,
                        'bytes_total': stream.consumer.size,
                        'progress': misc.value2percent(stream.consumer.bytes_sent, stream.consumer.size, 0)
                    })
            result.append(item)
    return RESULT(result)

#------------------------------------------------------------------------------

def queue_list():
    """
    """
    from p2p import p2p_queue
    return RESULT([{
        'queue_id': queue_id,
        'messages': len(p2p_queue.queue(queue_id)),
    } for queue_id in p2p_queue.queue().keys()])

#------------------------------------------------------------------------------

def user_ping(idurl_or_global_id, timeout=10, retries=2):
    """
    Sends Identity packet to remote peer and wait for Ack packet to check connection status.
    The "ping" command performs following actions:
      1. Request remote identity source by idurl,
      2. Sends my Identity to remote contact addresses, taken from identity,
      3. Wait first Ack packet from remote peer,
      4. Failed by timeout or identity fetching error.
    You can use this method to check and be sure that remote node is alive at the moment.
    Return:
        {'status': 'OK', 'result': '(signed.Packet[Ack(Identity) bob|bob for alice], in_70_19828906(DONE))'}
    """
    if not driver.is_on('service_identity_propagate'):
        return ERROR('service_identity_propagate() is not started')
    from p2p import propagate
    from userid import global_id
    idurl = idurl_or_global_id
    if global_id.IsValidGlobalUser(idurl):
        idurl = global_id.GlobalUserToIDURL(idurl)
    ret = Deferred()
    d = propagate.PingContact(idurl, timeout=int(timeout), retries=int(retries))
    d.addCallback(
        lambda resp: ret.callback(
            OK(str(resp))))
    d.addErrback(
        lambda err: ret.callback(
            ERROR(err.getErrorMessage())))
    return ret


def user_status(idurl_or_global_id):
    """
    """
    if not driver.is_on('service_identity_propagate'):
        return ERROR('service_identity_propagate() is not started')
    from p2p import online_status
    from userid import global_id
    idurl = idurl_or_global_id
    if global_id.IsValidGlobalUser(idurl):
        idurl = global_id.GlobalUserToIDURL(idurl)
    if not online_status.isKnown(idurl):
        return ERROR('unknown user')
    # state_machine_inst = contact_status.getInstance(idurl)
    # if not state_machine_inst:
    #     return ERROR('error fetching user status')
    return RESULT([{
        'contact_status': online_status.getStatusLabel(idurl),
        'contact_state': online_status.getCurrentState(idurl),
        'idurl': idurl,
        'global_id': global_id.UrlToGlobalID(idurl),
    }])


def user_status_check(idurl_or_global_id, timeout=5):
    """
    """
    if not driver.is_on('service_identity_propagate'):
        return ERROR('service_identity_propagate() is not started')
    from p2p import online_status
    from userid import global_id
    idurl = idurl_or_global_id
    if global_id.IsValidGlobalUser(idurl):
        idurl = global_id.GlobalUserToIDURL(idurl)
    peer_status = online_status.getInstance(idurl)
    if not peer_status:
        return ERROR('failed to check peer status')
    ret = Deferred()

    def _on_peer_status_state_changed(oldstate, newstate, event_string, *args, **kwargs):
        if newstate not in ['CONNECTED', 'OFFLINE', ]:
            return None
        if newstate == 'OFFLINE' and oldstate == 'OFFLINE' and not event_string == 'ping-failed':
            return None
        ret.callback(OK(extra_fields=dict(
            idurl=idurl,
            global_id=global_id.UrlToGlobalID(idurl),
            contact_state=newstate,
            contact_status=online_status.stateToLabel(newstate),
        )))
        return None

    def _do_clean(x):
        peer_status.removeStateChangedCallback(_on_peer_status_state_changed)
        return None

    ret.addBoth(_do_clean)

    peer_status.addStateChangedCallback(_on_peer_status_state_changed)
    peer_status.automat('ping-now', timeout)
    return ret


def user_search(nickname, attempts=1):
    """
    Starts nickname_observer() Automat to lookup existing nickname registered
    in DHT network.
    """
    from lib import misc
    from userid import global_id
    if not nickname:
        return ERROR('requires nickname of the user')
    if not misc.ValidNickName(nickname):
        return ERROR('invalid nickname')
    if not driver.is_on('service_private_messages'):
        return ERROR('service_private_messages() is not started')

    from chat import nickname_observer
    # nickname_observer.stop_all()
    ret = Deferred()

    def _result(result, nik, pos, idurl):
        return ret.callback(RESULT([{
            'result': result,
            'nickname': nik,
            'position': pos,
            'global_id': global_id.UrlToGlobalID(idurl),
            'idurl': idurl,
        }]))

    nickname_observer.find_one(
        nickname,
        attempts=attempts,
        results_callback=_result,
    )
    return ret


def user_observe(nickname, attempts=3):
    """
    Starts nickname_observer() Automat to lookup existing nickname registered
    in DHT network.
    """
    from lib import misc
    from userid import global_id
    if not nickname:
        return ERROR('requires nickname of the user')
    if not misc.ValidNickName(nickname):
        return ERROR('invalid nickname')
    if not driver.is_on('service_private_messages'):
        return ERROR('service_private_messages() is not started')

    from chat import nickname_observer
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
        ret.callback(RESULT(results, ))
        return None

    from twisted.internet import reactor  # @UnresolvedImport
    reactor.callLater(0.05, nickname_observer.observe_many,  # @UndefinedVariable
        nickname,
        attempts=attempts,
        results_callback=_result,
    )
    return ret

#------------------------------------------------------------------------------

def nickname_get():
    """
    """
    from main import settings
    if not driver.is_on('service_private_messages'):
        return ERROR('service_private_messages() is not started')
    return OK(extra_fields={'nickname': settings.getNickName(), })


def nickname_set(nickname):
    """
    Starts nickname_holder() machine to register and keep your nickname in DHT
    network.
    """
    from lib import misc
    if not nickname:
        return ERROR('requires nickname of the user')
    if not misc.ValidNickName(nickname):
        return ERROR('invalid nickname')
    if not driver.is_on('service_private_messages'):
        return ERROR('service_private_messages() is not started')
    from chat import nickname_holder
    from main import settings
    from userid import my_id
    settings.setNickName(nickname)
    ret = Deferred()

    def _nickname_holder_result(result, key):
        nickname_holder.A().remove_result_callback(_nickname_holder_result)
        return ret.callback(OK(extra_fields={
            'result': result,
            'nickname': key,
            'global_id': my_id.getGlobalID(),
            'idurl': my_id.getLocalID(),
        }))

    nickname_holder.A().add_result_callback(_nickname_holder_result)
    nickname_holder.A('set', nickname)
    return ret

#------------------------------------------------------------------------------

def message_history(user):
    """
    Returns chat history with that user.
    """
    if not driver.is_on('service_message_history'):
        return ERROR('service_message_history() is not started')
    from chat import message_db
    from userid import my_id, global_id
    from crypt import my_keys
    if user is None:
        return ERROR('User id is required')
    if not user.count('@'):
        from contacts import contactsdb
        user_idurl = contactsdb.find_correspondent_by_nickname(user)
        if not user_idurl:
            return ERROR('user not found')
        user = global_id.UrlToGlobalID(user_idurl)
    glob_id = global_id.ParseGlobalID(user)
    if not glob_id['idurl']:
        return ERROR('wrong user')
    target_glob_id = global_id.MakeGlobalID(**glob_id)
    if not my_keys.is_valid_key_id(target_glob_id):
        return ERROR('invalid key_id: %s' % target_glob_id)
    if _Debug:
        lg.out(_DebugLevel, 'api.message_history with "%s"' % target_glob_id)
    key = '{}:{}'.format(my_id.getGlobalID(key_alias='master'), target_glob_id)
    messages = [m for m in message_db.get_many(index_name='sender_recipient_glob_id', key=key)]
    messages.reverse()
    return RESULT(messages)


def message_send(recipient, json_data, timeout=5):
    """
    Sends a text message to remote peer, `recipient` is a string with nickname or global_id.

    Return:

        {'status': 'OK', 'result': ['signed.Packet[Message(146681300413)]']}
    """
    if not driver.is_on('service_private_messages'):
        return ERROR('service_private_messages() is not started')
    from chat import message
    from userid import global_id
    from crypt import my_keys
    if not recipient.count('@'):
        from contacts import contactsdb
        recipient_idurl = contactsdb.find_correspondent_by_nickname(recipient)
        if not recipient_idurl:
            return ERROR('recipient not found')
        recipient = global_id.UrlToGlobalID(recipient_idurl)
    glob_id = global_id.ParseGlobalID(recipient)
    if not glob_id['idurl']:
        return ERROR('wrong recipient')
    target_glob_id = global_id.MakeGlobalID(**glob_id)
    if not my_keys.is_valid_key_id(target_glob_id):
        return ERROR('invalid key_id: %s' % target_glob_id)
#     if not my_keys.is_key_registered(target_glob_id):
#         return ERROR('unknown key_id: %s' % target_glob_id)
    if _Debug:
        lg.out(_DebugLevel, 'api.message_send to "%s"' % target_glob_id)
    result = message.send_message(
        json_data=json_data,
        recipient_global_id=target_glob_id,
        timeout=timeout,
    )
    ret = Deferred()
    result.addCallback(
        lambda packet: ret.callback(
            OK(str(packet))))
    result.addErrback(
        lambda err: ret.callback(
            ERROR(err.getErrorMessage())))
    return ret


def message_receive(consumer_id):
    """
    This method can be used to listen and process incoming chat messages by specific consumer.
    If there are no messages received yet, this method will be waiting for any incomings.
    If some messages was already received, but not "consumed" yet method will return them imediately.
    After you got response and processed the messages you should call this method again to listen
    for more incomings again. This is simillar to message queue polling interface.
    If you do not "consume" messages, after 100 un-collected messages "consumer" will be dropped.
    Both, incoming and outgoing, messages will be populated here.

    Return:

        {'status': 'OK',
         'result': [{
            'type': 'private_message',
            'dir': 'incoming',
            'message_id': '123456788',
            'sender': 'messages$alice@first-host.com',
            'recipient': 'messages$bob@second-host.net',
            'data': {
                'message': 'Hello BitDust!'
            },
            'time': 123456789
        }]}
    """
    if not driver.is_on('service_private_messages'):
        return ERROR('service_private_messages() is not started')
    from chat import message
    ret = Deferred()

    def _on_pending_messages(pending_messages):
        result = []
        for msg in pending_messages:
            if msg['type'] != 'private_message':
                continue
            result.append({
                'data': msg['data'],
                'recipient': msg['to'],
                'sender': msg['from'],
                'time': msg['time'],
                'message_id': msg['id'],
                'dir': msg['dir'],
            })
        if _Debug:
            lg.out(_DebugLevel, 'api.message_receive._on_pending_messages returning : %s' % result)
        ret.callback(OK(result))
        return len(result) > 0

    d = message.consume_messages(consumer_id)
    d.addCallback(_on_pending_messages)
    d.addErrback(lambda err: ret.callback(ERROR(str(err))))
    if _Debug:
        lg.out(_DebugLevel, 'api.message_receive "%s"' % consumer_id)
    return ret


def messages_get_all(index_name, limit, offset, with_doc, with_storage):
    if not driver.is_on('service_private_messages'):
        return ERROR('service_private_messages() is not started')
    from chat import message_db
    r = [m for m in message_db.get_all(index_name, limit, offset, with_doc, with_storage)]
    return RESULT(r)


#------------------------------------------------------------------------------


def broadcast_send_message(payload):
    """
    Sends broadcast message to all peers in the network.

    Message must be provided in `payload` argument is a Json object.

    WARNING! Please, do not send too often and do not send more then
    several kilobytes per message.
    """
    if not driver.is_on('service_broadcasting'):
        return ERROR('service_broadcasting() is not started')
    from broadcast import broadcast_service
    from broadcast import broadcast_listener
    from broadcast import broadcaster_node
    msg = broadcast_service.send_broadcast_message(payload)
    current_states = dict()
    if broadcaster_node.A():
        current_states[broadcaster_node.A().name] = broadcaster_node.A().state
    if broadcast_listener.A():
        current_states[broadcast_listener.A().name] = broadcast_listener.A().state
    if _Debug:
        lg.out(_DebugLevel, 'api.broadcast_send_message : %s, %s' % (msg, current_states))
    return RESULT([msg, current_states, ])

#------------------------------------------------------------------------------

def event_send(event_id, json_data=None):
    from main import events
    json_payload = None
    json_length = 0
    if json_data and strng.is_string(json_data):
        json_length = len(json_data)
        try:
            json_payload = jsn.loads(strng.to_text(json_data or '{}'))
        except:
            return ERROR('json data payload is not correct')
    evt = events.send(event_id, data=json_payload)
    if _Debug:
        lg.out(_DebugLevel, 'api.event_send "%s" was fired to local node with %d bytes payload' % (event_id, json_length, ))
    return OK({'event_id': event_id, 'created': evt.created, })

def events_listen(consumer_id):
    from main import events
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
        # if _Debug:
        #     lg.out(_DebugLevel, 'api.events_listen._on_pending_events returning : %s' % result)
        ret.callback(OK(result))
        return len(result) > 0

    d = events.consume_events(consumer_id)
    d.addCallback(_on_pending_events)
    d.addErrback(lambda err: ret.callback(ERROR(str(err))))
    # if _Debug:
    #     lg.out(_DebugLevel, 'api.events_listen "%s"' % consumer_id)
    return ret

#------------------------------------------------------------------------------

def network_stun(udp_port=None, dht_port=None):
    """
    """
    from stun import stun_client
    ret = Deferred()
    d = stun_client.safe_stun(udp_port=udp_port, dht_port=dht_port)
    d.addBoth(lambda r: ret.callback(RESULT([r, ])))
    return ret


def network_reconnect():
    """
    Sends "reconnect" event to network_connector() Automat in order to refresh
    network connection.

    Return:

        {'status': 'OK', 'result': 'reconnected'}
    """
    if not driver.is_on('service_network'):
        return ERROR('service_network() is not started')
    from p2p import network_connector
    if _Debug:
        lg.out(_DebugLevel, 'api.network_reconnect')
    network_connector.A('reconnect')
    return OK('reconnected')


def network_connected(wait_timeout=5):
    """
    Be sure BitDust software is connected to other nodes in the network.
    If all is good this method will block for `wait_timeout` seconds.
    In case of some network issues method will return result asap.
    """
    if _Debug:
        lg.out(_DebugLevel + 10, 'api.network_connected  wait_timeout=%r' % wait_timeout)
    if not driver.is_on('service_network'):
        return ERROR('service_network() is not started')
    from twisted.internet import reactor  # @UnresolvedImport
    from userid import my_id
    from automats import automat
    ret = Deferred()

    p2p_connector_lookup = automat.find('p2p_connector')
    if p2p_connector_lookup:
        p2p_connector_machine = automat.objects().get(p2p_connector_lookup[0])
        if p2p_connector_machine and p2p_connector_machine.state == 'CONNECTED':
            proxy_receiver_lookup = automat.find('proxy_receiver')
            if proxy_receiver_lookup:
                proxy_receiver_machine = automat.objects().get(proxy_receiver_lookup[0])
                if proxy_receiver_machine and proxy_receiver_machine.state == 'LISTEN':
                    wait_timeout_defer = Deferred()
                    wait_timeout_defer.addTimeout(wait_timeout, clock=reactor)
                    wait_timeout_defer.addBoth(lambda _: ret.callback(OK({
                        'service_network': 'started',
                        'service_gateway': 'started',
                        'service_p2p_hookups': 'started',
                        'service_proxy_transport': 'started',
                        'proxy_receiver_state': proxy_receiver_machine.state,
                    })))
                    return ret
            else:
                wait_timeout_defer = Deferred()
                wait_timeout_defer.addTimeout(wait_timeout, clock=reactor)
                wait_timeout_defer.addBoth(lambda _: ret.callback(OK({
                    'service_network': 'started',
                    'service_gateway': 'started',
                    'service_p2p_hookups': 'started',
                    'service_proxy_transport': 'disabled',
                    'p2p_connector_state': p2p_connector_machine.state,
                })))
                return ret

    if not my_id.isLocalIdentityReady():
        lg.warn('local identity is not valid or not exist')
        return ERROR('local identity is not valid or not exist', extra_fields={'reason': 'identity_not_exist'})
    if not driver.is_enabled('service_network'):
        lg.warn('service_network() is disabled')
        return ERROR('service_network() is disabled', extra_fields={'reason': 'service_network_disabled'})
    if not driver.is_enabled('service_gateway'):
        lg.warn('service_gateway() is disabled')
        return ERROR('service_gateway() is disabled', extra_fields={'reason': 'service_gateway_disabled'})
    if not driver.is_enabled('service_p2p_hookups'):
        lg.warn('service_p2p_hookups() is disabled')
        return ERROR('service_p2p_hookups() is disabled', extra_fields={'reason': 'service_p2p_hookups_disabled'})

    def _do_p2p_connector_test():
        try:
            p2p_connector_lookup = automat.find('p2p_connector')
            if not p2p_connector_lookup:
                lg.warn('disconnected, reason is "p2p_connector_not_found"')
                ret.callback(ERROR('disconnected', extra_fields={'reason': 'p2p_connector_not_found'}))
                return None
            p2p_connector_machine = automat.objects().get(p2p_connector_lookup[0])
            if not p2p_connector_machine:
                lg.warn('disconnected, reason is "p2p_connector_not_exist"')
                ret.callback(ERROR('disconnected', extra_fields={'reason': 'p2p_connector_not_exist'}))
                return None
            if p2p_connector_machine.state != 'CONNECTED':
                lg.warn('disconnected, reason is "p2p_connector_disconnected", sending "check-synchronize" event to p2p_connector()')
                p2p_connector_machine.automat('check-synchronize')
                ret.callback(ERROR('disconnected', extra_fields={'reason': 'p2p_connector_disconnected'}))
                return None
            # ret.callback(OK('connected'))
            _do_service_proxy_transport_test()
        except:
            lg.exc()
            ret.callback(ERROR('disconnected', extra_fields={'reason': 'p2p_connector_error'}))
        return None

    def _do_service_proxy_transport_test():
        if not driver.is_enabled('service_proxy_transport'):
            ret.callback(OK({
                'service_network': 'started',
                'service_gateway': 'started',
                'service_p2p_hookups': 'started',
                'service_proxy_transport': 'disabled',
            }))
            return None
        try:
            proxy_receiver_lookup = automat.find('proxy_receiver')
            if not proxy_receiver_lookup:
                lg.warn('disconnected, reason is "proxy_receiver_not_found"')
                ret.callback(ERROR('disconnected', extra_fields={'reason': 'proxy_receiver_not_found'}))
                return None
            proxy_receiver_machine = automat.objects().get(proxy_receiver_lookup[0])
            if not proxy_receiver_machine:
                lg.warn('disconnected, reason is "proxy_receiver_not_exist"')
                ret.callback(ERROR('disconnected', extra_fields={'reason': 'proxy_receiver_not_exist'}))
                return None
            if proxy_receiver_machine.state != 'LISTEN':
                lg.warn('disconnected, reason is "proxy_receiver_disconnected", sending "start" event to proxy_receiver()')
                proxy_receiver_machine.automat('start')
                ret.callback(ERROR('disconnected', extra_fields={'reason': 'proxy_receiver_disconnected'}))
                return None
            ret.callback(OK({
                'service_network': 'started',
                'service_gateway': 'started',
                'service_p2p_hookups': 'started',
                'service_proxy_transport': 'started',
                'proxy_receiver_state': proxy_receiver_machine.state,
            }))
        except:
            lg.exc()
            ret.callback(ERROR('disconnected', extra_fields={'reason': 'proxy_receiver_error'}))
        return None

    def _on_service_restarted(resp, service_name):
        if service_name == 'service_network':
            _do_service_test('service_gateway')
        elif service_name == 'service_gateway':
            _do_service_test('service_p2p_hookups')
        else:
            _do_p2p_connector_test()
        return resp

    def _do_service_restart(service_name):
        d = service_restart(service_name, wait_timeout=wait_timeout)
        d.addCallback(_on_service_restarted, service_name)
        d.addErrback(lambda err: ret.callback(dict(
            list(ERROR(err.getErrorMessage()).items()) + list({'reason': '{}_restart_error'.format(service_name)}.items()))))
        return None

    def _do_service_test(service_name):
        try:
            svc_info = service_info(service_name)
            svc_state = svc_info['result'][0]['state']
        except:
            lg.exc('service "%s" test failed' % service_name)
            ret.callback(ERROR('disconnected', extra_fields={'reason': '{}_info_error'.format(service_name)}))
            return None
        if svc_state != 'ON':
            _do_service_restart(service_name)
            return None
        if service_name == 'service_network':
            reactor.callLater(0, _do_service_test, 'service_gateway')  # @UndefinedVariable
        elif service_name == 'service_gateway':
            reactor.callLater(0, _do_service_test, 'service_p2p_hookups')  # @UndefinedVariable
        elif service_name == 'service_p2p_hookups':
            reactor.callLater(0, _do_p2p_connector_test)  # @UndefinedVariable
        elif service_name == 'service_proxy_transport':
            reactor.callLater(0, _do_service_proxy_transport_test)  # @UndefinedVariable
        else:
            raise Exception('unknown service to test %s' % service_name)
        return None

    _do_service_test('service_network')
    return ret


def network_status(show_suppliers=True, show_customers=True, show_cache=True,
                   show_tcp=True, show_udp=True, show_proxy=True, ):
    """
    """
    if not driver.is_on('service_network'):
        return ERROR('service_network() is not started')
    from automats import automat
    from main import settings
    from userid import my_id
    from userid import global_id

    def _tupl_addr_to_str(addr):
        if not addr:
            return None
        return ':'.join(map(str, addr))

    r = {
        'p2p_connector_state': None,
        'network_connector_state': None,
        'idurl': None,
        'global_id': None,
    }
    p2p_connector_lookup = automat.find('p2p_connector')
    if p2p_connector_lookup:
        p2p_connector_machine = automat.objects().get(p2p_connector_lookup[0])
        if p2p_connector_machine:
            r['p2p_connector_state'] = p2p_connector_machine.state
    network_connector_lookup = automat.find('network_connector')
    if network_connector_lookup:
        network_connector_machine = automat.objects().get(network_connector_lookup[0])
        if network_connector_machine:
            r['network_connector_state'] = network_connector_machine.state
    if my_id.isLocalIdentityReady():
        r['idurl'] = my_id.getLocalID()
        r['global_id'] = my_id.getGlobalID()
    if True in [show_suppliers, show_customers, show_cache, ]:
        if not driver.is_on('service_p2p_hookups'):
            return ERROR('service_p2p_hookups() is not started')
        from contacts import contactsdb
        from p2p import online_status
        if show_suppliers:
            connected = 0
            items = []
            for idurl in contactsdb.all_suppliers():
                i = {
                    'idurl': idurl,
                    'global_id': global_id.UrlToGlobalID(idurl),
                    'state': None
                }
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
        if show_customers:
            connected = 0
            items = []
            for idurl in contactsdb.customers():
                i = {
                    'idurl': idurl,
                    'global_id': global_id.UrlToGlobalID(idurl),
                    'state': None
                }
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
        if show_cache:
            from contacts import identitycache
            connected = 0
            items = []
            for idurl in identitycache.Items().keys():
                i = {
                    'idurl': idurl,
                    'global_id': global_id.UrlToGlobalID(idurl),
                    'state': None
                }
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
    if True in [show_tcp, show_udp, show_proxy, ]:
        from transport import gateway
        if show_tcp:
            r['tcp'] = {
                'sessions': [],
                'streams': [],
            }
            if driver.is_on('service_tcp_transport'):
                sessions = []
                for s in gateway.list_active_sessions('tcp'):
                    i = {
                        'peer': getattr(s, 'peer', None),
                        'state': getattr(s, 'state', None),
                        'id': getattr(s, 'id', None),
                        'idurl': getattr(s, 'peer_idurl', None),
                        'address': _tupl_addr_to_str(getattr(s, 'peer_address', None)),
                        'external_address': _tupl_addr_to_str(getattr(s, 'peer_external_address', None)),
                        'connection_address': _tupl_addr_to_str(getattr(s, 'connection_address', None)),
                        'bytes_received': getattr(s, 'total_bytes_received', 0),
                        'bytes_sent': getattr(s, 'total_bytes_sent', 0),
                    }
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
        if show_udp:
            from lib import udp
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
                    sessions.append({
                        'peer': s.peer_id,
                        'state': s.state,
                        'id': s.id,
                        'idurl': s.peer_idurl,
                        'address': _tupl_addr_to_str(s.peer_address),
                        'bytes_received': s.bytes_sent,
                        'bytes_sent': s.bytes_received,
                        'outgoing': len(s.file_queue.outboxFiles),
                        'incoming': len(s.file_queue.inboxFiles),
                        'queue': len(s.file_queue.outboxQueue),
                        'dead_streams': len(s.file_queue.dead_streams),
                    })
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
        if show_proxy:
            r['proxy'] = {
                'sessions': [],
            }
            if driver.is_on('service_proxy_transport'):
                sessions = []
                for s in gateway.list_active_sessions('proxy'):
                    i = {
                        'state': s.state,
                        'id': s.id,
                    }
                    if getattr(s, 'router_proto_host', None):
                        i['proto'] = s.router_proto_host[0]
                        i['peer'] = s.router_proto_host[1]
                    if getattr(s, 'router_idurl', None):
                        i['idurl'] = s.router_idurl
                        i['router'] = global_id.UrlToGlobalID(s.router_idurl)
                    if getattr(s, 'traffic_out', None):
                        i['bytes_sent'] = s.traffic_out
                    if getattr(s, 'traffic_in', None):
                        i['bytes_received'] = s.traffic_in
                    if getattr(s, 'pending_packets', None):
                        i['queue'] = len(s.pending_packets)
                    sessions.append(i)
                r['proxy']['sessions' ] = sessions
    return RESULT([r, ])

#------------------------------------------------------------------------------

def dht_node_find(node_id_64=None):
    if not driver.is_on('service_entangled_dht'):
        return ERROR('service_entangled_dht() is not started')
    from dht import dht_service
    if node_id_64 is None:
        node_id = dht_service.random_key()
        node_id_64 = node_id
    else:
        node_id = node_id_64
    ret = Deferred()

    def _cb(response):
        try:
            if isinstance(response, list):
                return ret.callback(OK({
                    'my_dht_id': dht_service.node().id,
                    'lookup': node_id_64, 
                    'closest_nodes': [{
                        'dht_id': c.id,
                        'address': '%s:%d' % (strng.to_text(c.address, errors='ignore'), c.port),
                    } for c in response],
                }))
            return ret.callback(ERROR('unexpected DHT response'))
        except Exception as exc:
            lg.exc()
            return ret.callback(ERROR(exc))

    def _eb(err):
        lg.err(str(err))
        ret.callback(ERROR(str(err)))
        return None

    d = dht_service.find_node(node_id)
    d.addCallback(_cb)
    d.addErrback(_eb)
    return ret


def dht_value_get(key, record_type='skip_validation'):
    if not driver.is_on('service_entangled_dht'):
        return ERROR('service_entangled_dht() is not started')
    from dht import dht_service
    from dht import dht_records
    ret = Deferred()

    record_rules = dht_records.get_rules(record_type)
    if not record_rules:
        return ERROR('record must be have correct type and known validation rules')

    def _cb(value):
        if isinstance(value, dict):
            if _Debug:
                lg.out(_DebugLevel, 'api.dht_value_get OK: %r' % value)
            return ret.callback(OK({
                'read': 'success',
                'my_dht_id': dht_service.node().id,
                'key': strng.to_text(key, errors='ignore'),
                'value': value,
            }))
        closest_nodes = []
        if isinstance(value, list):
            closest_nodes = value
        if _Debug:
            lg.out(_DebugLevel, 'api.dht_value_get ERROR: %r' % value)
        return ret.callback(OK({
            'read': 'failed',
            'my_dht_id': dht_service.node().id,
            'key': strng.to_text(key, errors='ignore'),
            'closest_nodes': [{
                'dht_id': c.id,
                'address': '%s:%d' % (strng.to_text(c.address, errors='ignore'), c.port),
            } for c in closest_nodes],
        }))

    def _eb(err):
        lg.err(str(err))
        ret.callback(ERROR(err))
        return None

    d = dht_service.get_valid_data(
        key=key,
        rules=record_rules,
        raise_for_result=False,
        return_details=True,
    )
    d.addCallback(_cb)
    d.addErrback(_eb)
    return ret


def dht_value_set(key, value, expire=None, record_type='skip_validation'):
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

    from dht import dht_service
    from dht import dht_records
    ret = Deferred()

    record_rules = dht_records.get_rules(record_type)
    if not record_rules:
        return ERROR('record must be have correct type and known validation rules')

    def _cb(response):
        try:
            if isinstance(response, list):
                if _Debug:
                    lg.out(_DebugLevel, 'api.dht_value_set OK: %r' % response)
                return ret.callback(OK({
                    'write': 'success' if len(response) > 0 else 'failed',
                    'my_dht_id': dht_service.node().id,
                    'key': strng.to_text(key, errors='ignore'),
                    'value': value,
                    'closest_nodes': [{
                        'dht_id': c.id,
                        'address': '%s:%d' % (strng.to_text(c.address, errors='ignore'), c.port),
                    } for c in response],
                }))
            if _Debug:
                lg.out(_DebugLevel, 'api.dht_value_set ERROR: %r' % response)
            return ret.callback(ERROR('unexpected DHT response'))
        except Exception as exc:
            lg.exc()
            return ret.callback(ERROR(exc))

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
            return ret.callback(ERROR(errmsg, extra_fields={
                'write': 'failed',
                'my_dht_id': dht_service.node().id,
                'key': strng.to_text(key, errors='ignore'),
                'closest_nodes': closest_nodes,
            }))
        except Exception as exc:
            lg.exc()
            return ERROR(exc)

    d = dht_service.set_valid_data(
        key=key,
        json_data=value,
        expire=expire or dht_service.KEY_EXPIRE_MAX_SECONDS,
        rules=record_rules,
        collect_results=True,
    )
    d.addCallback(_cb)
    d.addErrback(_eb)
    return ret


def dht_local_db_dump():
    if not driver.is_on('service_entangled_dht'):
        return ERROR('service_entangled_dht() is not started')
    from dht import dht_service
    return RESULT(dht_service.dump_local_db(value_as_json=True))

#------------------------------------------------------------------------------
