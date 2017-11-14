#!/usr/bin/python
# api.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
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
from twisted.conch.test.test_recvline import down

"""
.. module:: api.

Here is a bunch of methods to interact with BitDust software.
"""

#------------------------------------------------------------------------------

_Debug = True

#------------------------------------------------------------------------------

import os
import time

from twisted.internet.defer import Deferred, succeed

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
    return o


def ERROR(errors=[], message=None, status='ERROR', extra_fields=None):
    o = {'status': status,
         'errors': errors if isinstance(errors, list) else [errors, ]}
    if message is not None:
        o['message'] = message
    if extra_fields is not None:
        o.update(extra_fields)
    o = on_api_result_prepared(o)
    return o

#------------------------------------------------------------------------------


def stop():
    """
    Stop the main process immediately.

    Return:

        {'status': 'OK', 'result': 'stopped'}
    """
    lg.out(4, 'api.stop sending event "stop" to the shutdowner() machine')
    from main import shutdowner
    shutdowner.A('stop', 'exit')
    return OK('stopped')


def restart(showgui=False):
    """
    Restart the main process, if flag show=True the GUI will be opened after
    restart.

    Return:

        {'status': 'OK', 'result': 'restarted'}
    """
    from main import shutdowner
    if showgui:
        lg.out(4, 'api.restart forced for GUI, added param "show", sending event "stop" to the shutdowner() machine')
        shutdowner.A('stop', 'restartnshow')
        return OK('restarted with GUI')
    lg.out(4, 'api.restart did not found bpgui process nor forced for GUI, just do the restart, sending event "stop" to the shutdowner() machine')
    shutdowner.A('stop', 'restart')
    return OK('restarted')


def reconnect():
    """
    Sends "reconnect" event to network_connector() Automat in order to refresh
    network connection.

    Return:

        {'status': 'OK', 'result': 'reconnected'}
    """
    if not driver.is_started('service_network'):
        return ERROR('service_network() is not started')
    from p2p import network_connector
    lg.out(4, 'api.reconnect')
    network_connector.A('reconnect')
    return OK('reconnected')


def show():
    """
    Opens a default web browser to show the BitDust GUI.

    Return:

        {'status': 'OK',   'result': '"show" event has been sent to the main process'}
    """
    lg.out(4, 'api.show')
    from main import settings
    if settings.NewWebGUI():
        from web import control
        control.show()
    else:
        from web import webcontrol
        webcontrol.show()
    return OK('"show" event has been sent to the main process')

#------------------------------------------------------------------------------


def config_get(key, default=None):
    """
    Returns current value for specific option from program settings.

    Return:

        {'status': 'OK',   'result': [{'type': 'positive integer', 'value': '8', 'key': 'logs/debug-level'}]}
    """
    key = str(key)
    lg.out(4, 'api.config_get [%s]' % key)
    from main import config
    if not config.conf().exist(key):
        return ERROR('option "%s" not exist' % key)
    return RESULT([{
        'key': key,
        'value': config.conf().getData(key, default),
        'type': config.conf().getTypeLabel(key),
        # 'code': config.conf().getType(key),
        # 'label': config.conf().getLabel(key),
        # 'info': config.conf().getInfo(key)
    }])


def config_set(key, value):
    """
    Set a value for given option.

    Return:

        {'status': 'OK', 'result': [{'type': 'positive integer', 'old_value': '8', 'value': '10', 'key': 'logs/debug-level'}]}
    """
    key = str(key)
    from main import config
    from main import config_types
    v = {}
    if config.conf().exist(key):
        v['old_value'] = config.conf().getData(key)
    typ = config.conf().getType(key)
    typ_label = config.conf().getTypeLabel(key)
    lg.out(4, 'api.config_set [%s]=%s type is %s' % (key, value, typ_label))
    if not typ or typ in [config_types.TYPE_STRING,
                          config_types.TYPE_TEXT,
                          config_types.TYPE_UNDEFINED, ]:
        config.conf().setData(key, unicode(value))
    elif typ in [config_types.TYPE_BOOLEAN, ]:
        if (isinstance(value, str) or isinstance(value, unicode)):
            vl = value.strip().lower() == 'true'
        else:
            vl = bool(value)
        config.conf().setBool(key, vl)
    elif typ in [config_types.TYPE_INTEGER,
                 config_types.TYPE_POSITIVE_INTEGER,
                 config_types.TYPE_NON_ZERO_POSITIVE_INTEGER, ]:
        config.conf().setInt(key, int(value))
    elif typ in [config_types.TYPE_FOLDER_PATH,
                 config_types.TYPE_FILE_PATH,
                 config_types.TYPE_COMBO_BOX,
                 config_types.TYPE_PASSWORD, ]:
        config.conf().setString(key, value)
    else:
        config.conf().setData(key, unicode(value))
    v.update({'key': key,
              'value': config.conf().getData(key),
              'type': config.conf().getTypeLabel(key)
              # 'code': config.conf().getType(key),
              # 'label': config.conf().getLabel(key),
              # 'info': config.conf().getInfo(key),
              })
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
    lg.out(4, 'api.config_list')
    from main import config
    r = config.conf().cache()
    r = map(lambda key: {
        'key': key,
        'value': str(r[key]).replace('\n', '\\n'),
        'type': config.conf().getTypeLabel(key)}, r.keys())
    if sort:
        r = sorted(r, key=lambda i: i['key'])
    return RESULT(r)

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
            'id': 'cool$testveselin@p2p-id.ru',
            'fingerprint': '50:f9:f1:6d:e3:e4:25:61:0c:81:6f:79:24:4e:78:17',
            'size': '4096',
            'ssh_type': 'ssh-rsa',
            'type': 'RSA',
            'public': 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQCPy7AXI0HuQSdmMF...',
            'private': '-----BEGIN RSA PRIVATE KEY-----\nMIIJKAIBAAKCAgEAj8uw...'
        }]}
    """
    lg.out(4, 'api.key_get')
    from crypt import my_keys
    from crypt import key
    from userid import my_id
    from userid import global_id
    key_id = str(key_id)
    if key_id == 'master':
        r = {
            'id': key_id,
            'alias': 'master',
            'creator': my_id.getLocalID(),
            'fingerprint': str(key.MyPrivateKeyObject().fingerprint()),
            'type': str(key.MyPrivateKeyObject().type()),
            'ssh_type': str(key.MyPrivateKeyObject().sshType()),
            'size': str(key.MyPrivateKeyObject().size()),
            'public': str(key.MyPrivateKeyObject().public().toString('openssh')),
        }
        if include_private:
            r['private'] = str(key.MyPrivateKeyObject().toString('openssh'))
        return RESULT([r, ])
    key_alias, creator_idurl = my_keys.split_key_id(key_id)
    if not key_alias or not creator_idurl:
        return ERROR('icorrect key_id format')
    key_object = my_keys.known_keys().get(key_id)
    if not key_object:
        key_id_form_1 = my_keys.make_key_id(
            alias=key_alias,
            creator_idurl=creator_idurl,
            output_format=global_id._FORMAT_GLOBAL_ID_KEY_USER,
        )
        key_id_form_2 = my_keys.make_key_id(
            alias=key_alias,
            creator_idurl=creator_idurl,
            output_format=global_id._FORMAT_GLOBAL_ID_USER_KEY,
        )
        key_object = my_keys.known_keys().get(key_id_form_1)
        if key_object:
            key_id = key_id_form_1
        else:
            key_object = my_keys.known_keys().get(key_id_form_2)
            if key_object:
                key_id = key_id_form_2
    if not key_object:
        return ERROR('key not found')
    r = {
        'id': key_id,
        'alias': key_alias,
        'creator': creator_idurl,
        'fingerprint': str(key_object.fingerprint()),
        'type': str(key_object.type()),
        'ssh_type': str(key_object.sshType()),
        'size': str(key_object.size()),
        'public': str(key_object.public().toString('openssh')),
    }
    if include_private:
        r['private'] = str(key_object.toString('openssh'))
    return RESULT([r, ])


def keys_list(sort=False, include_private=False):
    """
    List details for known Private Keys.
    Use `include_private=True` to get Private Keys as openssh formated strings.

    Return:
        {'status': 'OK',
         'result': [{
             'alias': 'master',
             'id': 'master$veselin@p2p-id.ru',
             'creator': 'http://p2p-id.ru/veselin.xml',
             'fingerprint': '60:ce:ea:98:bf:3d:aa:ba:29:1e:b9:0c:3e:5c:3e:32',
             'size': '2048',
             'ssh_type': 'ssh-rsa',
             'type': 'RSA',
             'public': 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDbpo3VYR5zvLe5...'
             'private': '-----BEGIN RSA PRIVATE KEY-----\nMIIJKAIBAAKCAgEAj8uw...'
         }, {
             'alias': 'another_key01',
             'id': 'another_key01$veselin@p2p-id.ru',
             'creator': 'http://p2p-id.ru/veselin.xml',
             'fingerprint': '43:c8:3b:b6:da:3e:8a:3c:48:6f:92:bb:74:b4:05:6b',
             'size': '4096',
             'ssh_type': 'ssh-rsa',
             'type': 'RSA',
             'public': 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQCmgX6j2MwEyY...'
             'private': '-----BEGIN RSA PRIVATE KEY-----\nMIIJKsdAIBSjfAdfguw...'
        }]}
    """
    lg.out(4, 'api.keys_list')
    from crypt import my_keys
    from crypt import key
    from userid import my_id
    r = []
    for key_id, key_object in my_keys.known_keys().items():
        key_alias, creator_idurl = my_keys.split_key_id(key_id)
        if not key_alias or not creator_idurl:
            lg.warn('incorrect key_id: %s' % key_id)
            continue
        i = {
            'id': key_id,
            'alias': key_alias,
            'creator': creator_idurl,
            'fingerprint': str(key_object.fingerprint()),
            'type': str(key_object.type()),
            'ssh_type': str(key_object.sshType()),
            'size': str(key_object.size()),
            'public': str(key_object.public().toString('openssh')),
        }
        if include_private:
            i['private'] = str(key_object.toString('openssh'))
        r.append(i)
    if sort:
        r = sorted(r, key=lambda i: i['alias'])
    i = {
        'id': my_keys.make_key_id('master', creator_idurl=my_id.getLocalID()),
        'alias': 'master',
        'creator': my_id.getLocalID(),
        'fingerprint': key.MyPrivateKeyObject().fingerprint(),
        'type': str(key.MyPrivateKeyObject().type()),
        'ssh_type': str(key.MyPrivateKeyObject().sshType()),
        'size': str(key.MyPrivateKeyObject().size()),
        'public': str(key.MyPrivateKeyObject().public().toString('openssh')),
    }
    if include_private:
        i['private'] = str(key.MyPrivateKeyObject().toString('openssh'))
    r.insert(0, i)
    return RESULT(r)


def key_create(key_alias, key_size=4096, include_private=False):
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
    from crypt import my_keys
    from userid import my_id
    key_alias = str(key_alias)
    # TODO: add validation for key_alias
    key_alias = key_alias.strip().lower()
    key_id = my_keys.make_key_id(key_alias, creator_idurl=my_id.getLocalID())
    if my_keys.is_key_registered(key_id):
        return ERROR('key "%s" already exist' % key_id)
    lg.out(4, 'api.key_create id=%s, size=%s' % (key_id, key_size))
    key_object = my_keys.generate_key(key_id, key_size=key_size)
    if key_object is None:
        return ERROR('failed to generate private key "%s"' % key_id)
    r = {
        'id': key_id,
        'alias': key_alias,
        'creator': my_id.getLocalID(),
        'fingerprint': str(key_object.fingerprint()),
        'type': str(key_object.type()),
        'ssh_type': str(key_object.sshType()),
        'size': str(key_object.size()),
        'public': str(key_object.public().toString('openssh')),
        'private': '',
    }
    if include_private:
        r['private'] = str(key_object.toString('openssh'))
    return OK(r, message='new private key "%s" was generated successfully' % key_alias, )


def key_erase(key_id):
    """
    Removes Private Key from the list of known keys and erase local file.

    Return:

        {'status': 'OK',
         'message': 'private key "ccc2" was erased successfully',
        }
    """
    from crypt import my_keys
    key_id = str(key_id)
    lg.out(4, 'api.keys_list')
    if key_id == 'master':
        return ERROR('"master" key can not be removed')
    key_alias, creator_idurl = my_keys.split_key_id(key_id)
    if not key_alias or not creator_idurl:
        return ERROR('icorrect key_id format')
    if not my_keys.erase_key(key_id):
        return ERROR('failed to erase private key "%s"' % key_alias)
    return OK(message='private key "%s" was erased successfully' % key_alias)


def key_share(key_id, idurl):
    """
    Connect to remote node identified by `idurl` parameter and transfer private key `key_id` to that machine.
    This way remote user will be able to access those of your files which were encrypted with that private key.

    Returns:

    """
    from userid import global_id
    full_key_id = str(key_id)
    idurl = str(idurl)
    if not driver.is_started('service_keys_registry'):
        return succeed(ERROR('service_keys_registry() is not started'))
    glob_id = global_id.ParseGlobalID(full_key_id)
    if glob_id['key_alias'] == 'master':
        return ERROR('"master" key can not be shared')
    if not glob_id['key_alias'] or not glob_id['idurl']:
        return ERROR('icorrect key_id format')
    from access import key_ring
    result = Deferred()
    d = key_ring.share_private_key(full_key_id, idurl)
    d.addCallback(
        lambda resp: result.callback(
            OK(str(resp))))
    d.addErrback(
        lambda err: result.callback(
            ERROR(err.getErrorMessage())))
    return result

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
    if not driver.is_started('service_restores'):
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
    if not driver.is_started('service_backups'):
        return ERROR('service_backups() is not started')
    from storage import backup_monitor
    backup_monitor.A('restart')
    lg.out(4, 'api.files_sync')
    return OK('the main files sync loop has been restarted')


def files_list(remote_path=None):
    """
    """
    if not driver.is_started('service_backups'):
        return ERROR('service_backups() is not started')
    from storage import backup_fs
    from system import bpio
    from userid import global_id
    from userid import my_id
    from crypt import my_keys
    glob_path = global_id.ParseGlobalID(remote_path)
    norm_path = global_id.NormalizeGlobalID(glob_path.copy())
    remotePath = bpio.remotePath(norm_path['path'])
    result = []
    lookup = backup_fs.ListChildsByPath(
        remotePath,
        iter=backup_fs.fs(norm_path['idurl']),
        iterID=backup_fs.fsID(norm_path['idurl']),
    )
    if not isinstance(lookup, list):
        return ERROR(lookup)
    for i in lookup:
        glob_path_child = norm_path.copy()
        glob_path_child['path'] = i['path']
        if not i['item']['k']:
            i['item']['k'] = my_id.getGlobalID(key_alias='master')
        if glob_path['key_alias'] and i['item']['k']:
            if i['item']['k'] != my_keys.make_key_id(alias=glob_path['key_alias'], creator_glob_id=glob_path['customer']):
                continue
        result.append({
            'glob_id': global_id.MakeGlobalID(**glob_path_child),
            'customer': norm_path['customer'],
            'idurl': norm_path['idurl'],
            'id': i['path_id'],
            'name': i['name'],
            'path': i['path'],
            'type': backup_fs.TYPES.get(i['type'], '').lower(),
            'size': i['total_size'],
            'local_size': i['item']['s'],
            'latest': i['latest'],
            'key_id': i['item']['k'],
            'childs': i['childs'],
            'versions': i['versions'],
        })
    lg.out(4, 'api.files_list %d items returned' % len(result))
    return RESULT(result)


def file_info(remote_path, include_uploads=True, include_downloads=True):
    """
    """
    if not driver.is_started('service_restores'):
        return ERROR('service_restores() is not started')
    from storage import backup_fs
    from lib import misc
    from system import bpio
    from userid import global_id
    glob_path = global_id.ParseGlobalID(remote_path)
    norm_path = global_id.NormalizeGlobalID(glob_path.copy())
    remotePath = bpio.remotePath(norm_path['path'])
    pathID = backup_fs.ToID(remotePath, iter=backup_fs.fs(norm_path['idurl']))
    if not pathID:
        return ERROR('path "%s" was not found in catalog' % remotePath)
    item = backup_fs.GetByID(pathID, iterID=backup_fs.fsID(norm_path['idurl']))
    if not item:
        return ERROR('item "%s" is not found in catalog' % pathID)
    (item_size, item_time, versions) = backup_fs.ExtractVersions(pathID, item, customer_id=norm_path['customer'])
    item_key = item.key_id
    r = {
        'glob_id': global_id.MakeGlobalID(**norm_path),
        'customer': norm_path['idurl'],
        'id': pathID,
        'path': remotePath,
        'type': backup_fs.TYPES.get(item.type, '').lower(),
        'size': item_size,
        'latest': item_time,
        'key_id': item_key,
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
                'id': t.number,
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
                    'backup_id': r.BackupID,
                    'creator_id': r.CreatorID,
                    'path_id': r.PathID,
                    'version': r.Version,
                    'block_number': r.BlockNumber,
                    'bytes_processed': r.BytesWritten,
                    'created': time.asctime(time.localtime(r.Started)),
                    'aborted': r.AbortState,
                    'done': r.Done,
                    'eccmap': '' if not r.EccMap else r.EccMap.name,
                })
        r['downloads'] = downloads
    lg.out(4, 'api.file_info %s' % r['glob_id'])
    return RESULT([r, ])


def file_create(remote_path, as_folder=False):
    """
    """
    if not driver.is_started('service_backups'):
        return ERROR('service_backups() is not started')
    from storage import backup_fs
    from storage import backup_control
    from system import bpio
    from web import control
    from userid import global_id
    from crypt import my_keys
    parts = global_id.NormalizeGlobalID(global_id.ParseGlobalID(remote_path))
    if not parts['path']:
        return ERROR('invalid "remote_path" format')
    path = bpio.remotePath(parts['path'])
    pathID = backup_fs.ToID(path, iter=backup_fs.fs(parts['idurl']))
    keyID = my_keys.make_key_id(alias=parts['key_alias'], creator_glob_id=parts['customer'])
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
            lg.out(4, 'api.file_create parent folder "%s" was created at "%s"' % (parent_path, parentPathID))
        iter_and_iterID = backup_fs.GetIteratorsByPath(
            parent_path,
            iter=backup_fs.fs(parts['idurl']),
            iterID=backup_fs.fsID(parts['idurl']),
        )
        if not iter_and_iterID:
            return ERROR('remote path can not be assigned, parent folder not found: "%s"' % parent_path)
        _, _, _ = backup_fs.PutItem(
            name=os.path.basename(path),
            as_folder=as_folder,
            iter=iter_and_iterID[0],
            iterID=iter_and_iterID[1],
            key_id=keyID,
        )
        newPathID = backup_fs.ToID(path)
        if not newPathID:
            return ERROR('remote path can not be assigned, failed to create a new item: "%s"' % path)
    backup_control.Save()
    control.request_update([('pathID', newPathID), ])
    lg.out(4, 'api.file_create %s with %s' % (global_id.MakeGlobalID(**parts), newPathID))
    return OK(
        'new %s "%s" was added at remote path "%s"' % (('folder' if as_folder else 'file'), newPathID, path),
        extra_fields={
            'id': newPathID,
            'key_id': keyID,
            'path': path,
            'type': ('dir' if as_folder else 'file'),
        })


def file_delete(remote_path):
    """
    """
    if not driver.is_started('service_backups'):
        return ERROR('service_backups() is not started')
    from storage import backup_fs
    from storage import backup_control
    from storage import backup_monitor
    from main import settings
    from web import control
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
    lg.out(4, 'api.file_delete %s' % parts)
    return OK('item "%s" was deleted from remote suppliers' % pathIDfull)


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
    if not driver.is_started('service_backups'):
        return ERROR('service_backups() is not started')
    from lib import misc
    from storage import backup_control
    lg.out(4, 'api.files_uploads  %d is running, %d is pending' % (
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
            'id': t.number,
            'path_id': t.pathID,
            'source_path': t.localPath,
            'created': time.asctime(time.localtime(t.created)),
        } for t in backup_control.tasks()])
    return RESULT(r)


def file_upload_start(local_path, remote_path, wait_result=True):
    """
    """
    if not driver.is_started('service_backups'):
        return ERROR('service_backups() is not started')
    from system import bpio
    from storage import backup_fs
    from storage import backup_control
    from lib import packetid
    from web import control
    from userid import global_id
    from crypt import my_keys
    if not bpio.pathExist(local_path):
        return ERROR('local file or folder "%s" not exist' % local_path)
    parts = global_id.NormalizeGlobalID(remote_path)
    if not parts['idurl'] or not parts['path']:
        return ERROR('invalid "remote_path" format')
    path = bpio.remotePath(parts['path'])
    pathID = backup_fs.ToID(path, iter=backup_fs.fs(parts['idurl']))
    keyID = my_keys.make_key_id(alias=parts['key_alias'], creator_glob_id=parts['customer'])
    if not pathID:
        return ERROR('path "%s" not registered yet' % path)
    pathIDfull = packetid.MakeBackupID(parts['customer'], pathID)
    if wait_result:
        d = Deferred()
        tsk = backup_control.StartSingle(
            pathID=pathIDfull,
            localPath=local_path,
            keyID=keyID,
        )
        tsk.result_defer.addCallback(lambda backupID, result: d.callback(OK(
            'item "%s" uploaded, local path is: "%s"' % (remote_path, local_path),
            extra_fields={
                'id': remote_path,
                'version': backupID,
                'key_id': tsk.keyID,
                'source_path': local_path,
                'path_id': pathID,
            }
        )))
        tsk.result_defer.addErrback(lambda pathID, err: d.callback(ERROR(
            'upload task %d for "%s" failed: %s' % (tsk.number, tsk.pathID, err)
        )))
        backup_fs.Calculate()
        backup_control.Save()
        control.request_update([('pathID', pathIDfull), ])
        lg.out(4, 'api.file_upload_start %s with %s, wait_result=True' % (remote_path, pathIDfull))
        return d
    tsk = backup_control.StartSingle(
        pathID=pathIDfull,
        localPath=local_path,
        keyID=keyID,
    )
    backup_fs.Calculate()
    backup_control.Save()
    control.request_update([('pathID', pathIDfull), ])
    lg.out(4, 'api.file_upload_start %s with %s' % (remote_path, pathIDfull))
    return OK(
        'uploading "%s" started, local path is: "%s"' % (remote_path, local_path),
        extra_fields={
            'id': remote_path,
            'key_id': tsk.keyID,
            'source_path': local_path,
            'path_id': pathID,
        })


def file_upload_stop(remote_path):
    """
    """
    if not driver.is_started('service_backups'):
        return ERROR('service_backups() is not started')
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
    lg.out(4, 'api.file_upload_stop %s' % r)
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
    if not driver.is_started('service_restores'):
        return ERROR('service_restores() is not started')
    from storage import restore_monitor
    lg.out(4, 'api.files_downloads %d items downloading at the moment' % len(restore_monitor.GetWorkingObjects()))
    return RESULT([{
        'backup_id': r.BackupID,
        'creator_id': r.CreatorID,
        'path_id': r.PathID,
        'version': r.Version,
        'block_number': r.BlockNumber,
        'bytes_processed': r.BytesWritten,
        'created': time.asctime(time.localtime(r.Started)),
        'aborted': r.AbortState,
        'done': r.Done,
        'key_id': r.KeyID,
        'eccmap': '' if not r.EccMap else r.EccMap.name,
    } for r in restore_monitor.GetWorkingObjects()])


def file_download_start(remote_path, destination_path=None, wait_result=False):
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
    if not driver.is_started('service_restores'):
        return ERROR('service_restores() is not started')
    from storage import backup_fs
    from storage import backup_control
    from storage import restore_monitor
    from web import control
    from system import bpio
    from lib import packetid
    from main import settings
    from userid import my_id
    from userid import global_id
    from crypt import my_keys
    lg.out(4, 'api.file_download_start %s to %s, wait_result=%s' % (
        remote_path, destination_path, wait_result))
    glob_path = global_id.NormalizeGlobalID(global_id.ParseGlobalID(remote_path))
    if packetid.Valid(glob_path['path']):
        customerGlobalID, pathID, version = packetid.SplitBackupID(remote_path)
        if not customerGlobalID:
            customerGlobalID = global_id.UrlToGlobalID(my_id.getLocalID())
        item = backup_fs.GetByID(pathID, iterID=backup_fs.fsID(glob_path['customer']))
        if not item:
            return ERROR('path "%s" is not found in catalog' % remote_path)
        if not version:
            version = item.get_latest_version()
        if not version:
            return ERROR('not found any remote versions for "%s"' % remote_path)
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
        backupID = packetid.MakeBackupID(glob_path['customer'], knownPathID, version)
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
    if wait_result:
        d = Deferred()

        def _on_result(backupID, result):
            if result == 'restore done':
                d.callback(OK(
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
                d.callback(ERROR(
                    'downloading version "%s" failed, result: %s' % (backupID, result),
                    extra_fields={
                        'backup_id': backupID,
                        'local_path': destination_path,
                        'path_id': pathID_target,
                        'remote_path': knownPath,
                    },
                ))
            return True

        restore_monitor.Start(
            backupID, destination_path,
            keyID=my_keys.make_key_id(alias=glob_path['key_alias'], creator_glob_id=glob_path['customer']),
            callback=_on_result)
        control.request_update([('pathID', knownPath), ])
        lg.out(4, 'api.file_download_start %s to %s, wait_result=True' % (backupID, destination_path))
        return d
    restore_monitor.Start(backupID, destination_path, keyID=my_keys.make_key_id(alias=glob_path['key_alias'], creator_glob_id=glob_path['customer']))
    control.request_update([('pathID', knownPath), ])
    lg.out(4, 'api.download_start %s to %s' % (backupID, destination_path))
    return OK(
        'started',
        'downloading of version "%s" has been started to "%s"' % (backupID, destination_path),
        extra_fields={
            'backup_id': backupID,
            'local_path': destination_path,
            'path_id': pathID_target,
            'remote_path': knownPath,
        },)


def file_download_stop(remote_path):
    """
    Abort currently running restore process.

    Return:

        {'status': 'OK', 'result': 'restoring of "alice@p2p-host.com:0/1/2" aborted'}
    """
    if not driver.is_started('service_restores'):
        return ERROR('service_restores() is not started')
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
            backupIDs.append(packetid.MakeBackupID(customerGlobalID, pathID, version))
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
            backupIDs.append(packetid.MakeBackupID(glob_path['customer'], knownPathID, version))
    if not backupIDs:
        return ERROR('not found any remote versions for "%s"' % remote_path)
    r = []
    for backupID in backupIDs:
        r.append({'backup_id': backupID, 'aborted': restore_monitor.Abort(backupID), })
    lg.out(4, 'api.file_download_stop %s' % r)
    return RESULT(r)


#------------------------------------------------------------------------------


def suppliers_list():
    """
    This method returns a list of suppliers - nodes which stores your encrypted data on own machines.

    Return:

        {'status': 'OK',
         'result':[{
            'connected': '05-06-2016 13:06:05',
            'idurl': 'http://p2p-id.ru/bitdust_j_vps1014.xml',
            'numfiles': 14,
            'position': 0,
            'status': 'offline'
         }, {
            'connected': '05-06-2016 13:04:57',
            'idurl': 'http://veselin-p2p.ru/bitdust_j_vps1001.xml',
            'numfiles': 14,
            'position': 1,
            'status': 'offline'
        }]}
    """
    if not driver.is_started('service_customer'):
        return ERROR('service_customer() is not started')
    from contacts import contactsdb
    from p2p import contact_status
    from lib import misc
    from userid import my_id
    return RESULT([{
        'position': s[0],
        'idurl': s[1],
        'connected': misc.readSupplierData(s[1], 'connected', my_id.getLocalID()),
        'numfiles': len(misc.readSupplierData(s[1], 'listfiles', my_id.getLocalID()).split('\n')) - 1,
        'status': contact_status.getStatusLabel(s[1]),
    } for s in enumerate(contactsdb.suppliers())])


def supplier_replace(index_or_idurl):
    """
    Execute a fire/hire process for given supplier, another random node will
    replace this supplier. As soon as new supplier is found and connected,
    rebuilding of all uploaded data will be started and the new node will start
    getting a reconstructed fragments.

    Return:

        {'status': 'OK', 'result': 'supplier http://p2p-id.ru/alice.xml will be replaced by new peer'}
    """
    if not driver.is_started('service_customer'):
        return ERROR('service_customer() is not started')
    from contacts import contactsdb
    idurl = index_or_idurl
    if idurl.isdigit():
        idurl = contactsdb.supplier(int(idurl))
    if idurl and contactsdb.is_supplier(idurl):
        from customer import fire_hire
        fire_hire.AddSupplierToFire(idurl)
        fire_hire.A('restart')
        return OK('supplier "%s" will be replaced by new peer' % idurl)
    return ERROR('supplier not found')


def supplier_change(index_or_idurl, new_idurl):
    """
    Doing same as supplier_replace() but new node must be provided by you - you can manually assign a supplier.

    Return:

        {'status': 'OK', 'result': 'supplier http://p2p-id.ru/alice.xml will be replaced by http://p2p-id.ru/bob.xml'}
    """
    if not driver.is_started('service_customer'):
        return ERROR('service_customer() is not started')
    from contacts import contactsdb
    idurl = index_or_idurl
    if idurl.isdigit():
        idurl = contactsdb.supplier(int(idurl))
    if not idurl or not contactsdb.is_supplier(idurl):
        return ERROR('supplier not found')
    if contactsdb.is_supplier(new_idurl):
        return ERROR('peer "%s" is your supplier already' % new_idurl)
    from customer import fire_hire
    from customer import supplier_finder
    supplier_finder.AddSupplierToHire(new_idurl)
    fire_hire.AddSupplierToFire(idurl)
    fire_hire.A('restart')
    return OK('supplier "%s" will be replaced by "%s"' % (idurl, new_idurl))


def suppliers_ping():
    """
    Sends short requests to all suppliers to get their current statuses.

    Return:

        {'status': 'OK',  'result': 'requests to all suppliers was sent'}
    """
    if not driver.is_started('service_customer'):
        return ERROR('service_customer() is not started')
    from p2p import propagate
    propagate.SlowSendSuppliers(0.1)
    return OK('requests to all suppliers was sent')

#------------------------------------------------------------------------------


def customers_list():
    """
    List of customers - nodes who stores own data on your machine.

    Return:

        {'status': 'OK',
         'result': [ {  'idurl': 'http://p2p-id.ru/bob.xml',
                        'position': 0,
                        'status': 'offline'
        }]}
    """
    if not driver.is_started('service_supplier'):
        return ERROR('service_supplier() is not started')
    from contacts import contactsdb
    from p2p import contact_status
    return RESULT([{
        'position': s[0],
        'idurl': s[1],
        'status': contact_status.getStatusLabel(s[1])
    } for s in enumerate(contactsdb.customers())])


def customer_reject(idurl):
    """
    Stop supporting given customer, remove all his files from local disc, close
    connections with that node.

    Return:

        {'status': 'OK', 'result': 'customer http://p2p-id.ru/bob.xml rejected, 536870912 bytes were freed'}
    """
    if not driver.is_started('service_supplier'):
        return ERROR('service_supplier() is not started')
    from contacts import contactsdb
    from storage import accounting
    from main import settings
    from main import events
    from supplier import local_tester
    from p2p import p2p_service
    from lib import packetid
    if not contactsdb.is_customer(idurl):
        return ERROR('customer not found')
    # send packet to notify about service from us was rejected
    # TODO - this is not yet handled on other side
    p2p_service.SendFailNoRequest(idurl, packetid.UniqueID(), 'service rejected')
    # remove from customers list
    current_customers = contactsdb.customers()
    current_customers.remove(idurl)
    contactsdb.update_customers(current_customers)
    contactsdb.save_customers()
    # remove records for this customers from quotas info
    space_dict = accounting.read_customers_quotas()
    consumed_by_cutomer = space_dict.pop(idurl, None)
    consumed_space = accounting.count_consumed_space(space_dict)
    space_dict['free'] = settings.getDonatedBytes() - int(consumed_space)
    accounting.write_customers_quotas(space_dict)
    events.send('existing-customer-terminated', dict(idurl=idurl))
    # restart local tester
    local_tester.TestUpdateCustomers()
    return OK('customer "%s" rejected, "%s" bytes were freed' % (idurl, consumed_by_cutomer))


def customers_ping():
    """
    Sends Identity packet to all customers to check their current statuses.
    Every node will reply with Ack packet on any valid incoming Identiy packet.

    Return:

        {'status': 'OK',  'result': 'requests to all customers was sent'}
    """
    if not driver.is_started('service_supplier'):
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
    lg.out(4, 'api.space_donated finished with %d customers and %d errors' % (
        len(result['customers']), len(result['errors']),))
    for err in result['errors']:
        lg.out(4, '    %s' % err)
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
    lg.out(4, 'api.space_consumed finished')
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
    lg.out(4, 'api.space_local finished')
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
        'timers': (','.join(a.getTimers().keys())),
    } for a in automat.objects().values()]
    lg.out(4, 'api.automats_list responded with %d items' % len(result))
    return RESULT(result)

#------------------------------------------------------------------------------


def services_list():
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
    result = [{
        'index': svc.index,
        'name': name,
        'state': svc.state,
        'enabled': svc.enabled(),
        'installed': svc.installed(),
        'config_path': svc.config_path,
        'depends': svc.dependent_on()
    } for name, svc in sorted(driver.services().items(), key=lambda i: i[0])]
    lg.out(4, 'api.services_list responded with %d items' % len(result))
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
    from main import config
    svc = driver.services().get(service_name, None)
    if svc is None:
        service_name = 'service_' + service_name.replace('-', '_')
        svc = driver.services().get(service_name, None)
    if svc is None:
        lg.out(4, 'api.service_start %s not found' % service_name)
        return ERROR('service "%s" was not found' % service_name)
    if svc.state == 'ON':
        lg.out(4, 'api.service_start %s already started' % service_name)
        return ERROR('service "%s" already started' % service_name)
    current_config = config.conf().getBool(svc.config_path)
    if current_config:
        lg.out(4, 'api.service_start %s already enabled' % service_name)
        return ERROR('service "%s" already enabled' % service_name)
    config.conf().setBool(svc.config_path, True)
    lg.out(4, 'api.service_start (%s)' % service_name)
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
    from main import config
    svc = driver.services().get(service_name, None)
    if svc is None:
        service_name = 'service_' + service_name.replace('-', '_')
        svc = driver.services().get(service_name, None)
    if svc is None:
        lg.out(4, 'api.service_stop %s not found' % service_name)
        return ERROR('service "%s" not found' % service_name)
    current_config = config.conf().getBool(svc.config_path)
    if current_config is None:
        lg.out(4, 'api.service_stop config item %s was not found' % svc.config_path)
        return ERROR('config item "%s" was not found' % svc.config_path)
    if current_config is False:
        lg.out(4, 'api.service_stop %s already disabled' % service_name)
        return ERROR('service "%s" already disabled' % service_name)
    config.conf().setBool(svc.config_path, False)
    lg.out(4, 'api.service_stop (%s)' % service_name)
    return OK('"%s" was switched off' % service_name)

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
    if not driver.is_started('service_gateway'):
        return ERROR('service_gateway() is not started')
    from transport import stats
    return RESULT([{
        'in': stats.counters_in(),
        'out': stats.counters_out(),
    }])


def packets_list():
    """
    Return list of incoming and outgoing packets.
    """
    if not driver.is_started('service_gateway'):
        return ERROR('service_gateway() is not started')
    from transport import packet_in
    from transport import packet_out
    result = []
    for pkt_out in packet_out.queue():
        result.append({
            'name': pkt_out.outpacket.Command,
            'label': pkt_out.label,
            'from_to': 'to',
            'target': pkt_out.remote_idurl,
        })
    for pkt_in in packet_in.items().values():
        result.append({
            'name': pkt_in.transfer_id,
            'label': pkt_in.label,
            'from_to': 'from',
            'target': pkt_in.sender_idurl,
        })
    return RESULT(result)


def connections_list(wanted_protos=None):
    """
    Returns list of opened/active network connections. Argument `wanted_protos`
    can be used to select which protocols to list:

        connections_list(wanted_protos=['tcp', 'udp'])
    """
    if not driver.is_started('service_gateway'):
        return ERROR('service_gateway() is not started')
    from transport import gateway
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
                    'idurl': connection.peer_idurl or '',
                    'bytes_sent': connection.bytes_sent,
                    'bytes_received': connection.bytes_received,
                })
            result.append(item)
    return RESULT(result)


def streams_list(wanted_protos=None):
    """
    Return list of active sending/receiveing files.
    """
    if not driver.is_started('service_gateway'):
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
                'id': '',
                'type': '',
                'bytes_current': -1,
                'bytes_total': -1,
                'progress': '0%',
            }
            if proto == 'tcp':
                if hasattr(stream, 'bytes_received'):
                    item.update({
                        'id': stream.file_id,
                        'type': 'in',
                        'bytes_current': stream.bytes_received,
                        'bytes_total': stream.size,
                        'progress': misc.value2percent(stream.bytes_received, stream.size, 0)
                    })
                elif hasattr(stream, 'bytes_sent'):
                    item.update({
                        'id': stream.file_id,
                        'type': 'out',
                        'bytes_current': stream.bytes_sent,
                        'bytes_total': stream.size,
                        'progress': misc.value2percent(stream.bytes_sent, stream.size, 0)
                    })
            elif proto == 'udp':
                if hasattr(stream.consumer, 'bytes_received'):
                    item.update({
                        'id': stream.stream_id,
                        'type': 'in',
                        'bytes_current': stream.consumer.bytes_received,
                        'bytes_total': stream.consumer.size,
                        'progress': misc.value2percent(stream.consumer.bytes_received, stream.consumer.size, 0)
                    })
                elif hasattr(stream.consumer, 'bytes_sent'):
                    item.update({
                        'id': stream.stream_id,
                        'type': 'out',
                        'bytes_current': stream.consumer.bytes_sent,
                        'bytes_total': stream.consumer.size,
                        'progress': misc.value2percent(stream.consumer.bytes_sent, stream.consumer.size, 0)
                    })
            result.append(item)
    return RESULT(result)

#------------------------------------------------------------------------------


def ping(idurl, timeout=10):
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
    if not driver.is_started('service_identity_propagate'):
        return succeed(ERROR('service_identity_propagate() is not started'))
    from p2p import propagate
    result = Deferred()
    d = propagate.PingContact(idurl, int(timeout))
    d.addCallback(
        lambda resp: result.callback(
            OK(str(resp))))
    d.addErrback(
        lambda err: result.callback(
            ERROR(err.getErrorMessage())))
    return result

def user_ping(idurl, timeout=10):
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
    if not driver.is_started('service_identity_propagate'):
        return succeed(ERROR('service_identity_propagate() is not started'))
    from p2p import propagate
    result = Deferred()
    d = propagate.PingContact(idurl, int(timeout))
    d.addCallback(
        lambda resp: result.callback(
            OK(str(resp))))
    d.addErrback(
        lambda err: result.callback(
            ERROR(err.getErrorMessage())))
    return result

def user_search(nickname):
    """
    Starts nickname_observer() Automat to lookup existing nickname registered
    in DHT network.
    """
    if not driver.is_started('service_private_messages'):
        return ERROR('service_private_messages() is not started')
    from chat import nickname_observer
    nickname_observer.stop_all()
    ret = Deferred()

    def _result(result, nik, pos, idurl):
        return ret.callback(RESULT([{
            'result': result,
            'nickname': nik,
            'position': pos,
            'idurl': idurl,
        }]))
    nickname_observer.find_one(nickname,
                               results_callback=_result)
    # nickname_observer.observe_many(nickname,
    # results_callback=lambda result, nik, idurl: d.callback((result, nik, idurl)))
    return ret

#------------------------------------------------------------------------------


def set_my_nickname(nickname):
    """
    Starts nickname_holder() machine to register and keep your nickname in DHT
    network.
    """
    if not driver.is_started('service_private_messages'):
        return ERROR('service_private_messages() is not started')
    from chat import nickname_holder
    from main import settings
    from userid import my_id
    settings.setNickName(nickname)
    ret = Deferred()

    def _nickname_holder_result(result, key):
        return ret.callback(RESULT([{
            'result': result,
            'nickname': key,
            'idurl': my_id.getLocalID(),
        }]))
    nickname_holder.A('set', (nickname, _nickname_holder_result))
    return ret


def find_peer_by_nickname(nickname):
    """
    Starts nickname_observer() Automat to lookup existing nickname registered
    in DHT network.
    """
    if not driver.is_started('service_private_messages'):
        return ERROR('service_private_messages() is not started')
    from chat import nickname_observer
    nickname_observer.stop_all()
    ret = Deferred()

    def _result(result, nik, pos, idurl):
        return ret.callback(RESULT([{
            'result': result,
            'nickname': nik,
            'position': pos,
            'idurl': idurl,
        }]))
    nickname_observer.find_one(nickname,
                               results_callback=_result)
    # nickname_observer.observe_many(nickname,
    # results_callback=lambda result, nik, idurl: d.callback((result, nik, idurl)))
    return ret

#------------------------------------------------------------------------------


def send_message(recipient, message_body):
    """
    Sends a text message to remote peer, `recipient` is a string with nickname or global_id.

    Return:

        {'status': 'OK', 'result': ['signed.Packet[Message(146681300413)]']}
    """
    if not driver.is_started('service_private_messages'):
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
    if not glob_id['key_alias']:
        glob_id['key_alias'] = 'master'
    target_glob_id = global_id.MakeGlobalID(**glob_id)
    if not my_keys.is_valid_key_id(target_glob_id):
        return ERROR('invalid key_id: %s' % target_glob_id)
#     if not my_keys.is_key_registered(target_glob_id):
#         return ERROR('unknown key_id: %s' % target_glob_id)
    result = message.send_message(
        message_body=message_body,
        recipient_global_id=target_glob_id,
    )
    if isinstance(result, Deferred):
        ret = Deferred()
        result.addCallback(
            lambda packet: ret.callback(
                OK(str(packet.outpacket))))
        result.addErrback(
            lambda err: ret.callback(
                ERROR(err.getErrorMessage())))
        return ret
    return OK(str(result.outpacket))


def receive_one_message():
    """
    This method can be used to listen and process incoming chat messages.

      + creates a callback to receive all incoming messages,
      + wait until one incoming message get received,
      + remove the callback after receiving the message.

    After you received the message you can call this method again,
    this is very simillar to message queue polling interface.

    Return:

        {'status': 'OK',
         'result': [{
            'from': 'http://veselin-p2p.ru/bitdust_j_vps1001.xml',
            'message': 'Hello my dear Friend!'
        }]}
    """
    if not driver.is_started('service_private_messages'):
        return ERROR('service_private_messages() is not started')
    from chat import message
    ret = Deferred()

    def _message_received(request, private_message_object, decrypted_message_body):
        ret.callback(OK({
            'message': decrypted_message_body,
            'recipient': private_message_object.recipient,
            'decrypted': bool(private_message_object.encrypted_session),
            'from': request.OwnerID,
        }))
        message.RemoveIncomingMessageCallback(_message_received)
        return True

    message.AddIncomingMessageCallback(_message_received)
    return ret

#------------------------------------------------------------------------------

def message_send(recipient, message_body):
    """
    Sends a text message to remote peer, `recipient` is a string with nickname or global_id.

    Return:

        {'status': 'OK', 'result': ['signed.Packet[Message(146681300413)]']}
    """
    if not driver.is_started('service_private_messages'):
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
    if not glob_id['key_alias']:
        glob_id['key_alias'] = 'master'
    target_glob_id = global_id.MakeGlobalID(**glob_id)
    if not my_keys.is_valid_key_id(target_glob_id):
        return ERROR('invalid key_id: %s' % target_glob_id)
#     if not my_keys.is_key_registered(target_glob_id):
#         return ERROR('unknown key_id: %s' % target_glob_id)
    lg.out(4, 'api.message_send to "%s" with %d bytes' % (target_glob_id, len(message_body)))
    result = message.send_message(
        message_body=message_body,
        recipient_global_id=target_glob_id,
    )
    if isinstance(result, Deferred):
        ret = Deferred()
        result.addCallback(
            lambda packet: ret.callback(
                OK(str(packet.outpacket))))
        result.addErrback(
            lambda err: ret.callback(
                ERROR(err.getErrorMessage())))
        return ret
    return OK(str(result.outpacket))


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
            'id': '123456788',
            'sender': 'abc$alice@first-host.com',
            'recipient': 'abc$bob@second-host.net',
            'message': 'Hello World!',
            'time': 123456789
        }]}
    """
    if not driver.is_started('service_private_messages'):
        return ERROR('service_private_messages() is not started')
    from chat import message
    ret = Deferred()

    def _on_pending_messages(pending_messages):
        result = []
        for msg in pending_messages:
            if msg['type'] != 'private_message':
                continue
            result.append({
                'message': msg['body'],
                'recipient': msg['to'],
                'sender': msg['from'],
                'time': msg['time'],
                'id': msg['id'],
                'dir': msg['dir'],
            })
        lg.out(4, 'api.message_consumer_request._on_pending_messages returning : %s' % result)
        ret.callback(OK(result))
        return len(result) > 0

    d = message.consume_messages(consumer_id)
    d.addCallback(_on_pending_messages)
    d.addErrback(lambda err: ret.callback(ERROR(str(err))))
    lg.out(4, 'api.message_consumer_request "%s"' % consumer_id)
    return ret

#------------------------------------------------------------------------------


def broadcast_send_message(payload):
    """
    Sends broadcast message to all peers in the network.

    Message must be provided in `payload` argument is a Json object.

    WARNING! Please, do not send too often and do not send more then
    several kilobytes per message.
    """
    if not driver.is_started('service_broadcasting'):
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
    lg.out(4, 'api.broadcast_send_message : %s, %s' % (msg, current_states))
    return RESULT([msg, current_states, ])

#------------------------------------------------------------------------------

def event_send(event_id, json_data=None):
    import json
    from main import events
    events.send(event_id, json.loads(json_data or '{}'))
    return OK('event "%s" sent' % event_id)

#------------------------------------------------------------------------------
