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


def ERROR(errors=[], message=None, status='ERROR'):
    o = {'status': status,
         'errors': errors if isinstance(errors, list) else [errors, ]}
    if message is not None:
        o['message'] = message
    o = on_api_result_prepared(o)
    return o

#------------------------------------------------------------------------------


def stop():
    """
    Stop the main process immediately.

    Return:

        {'status': 'OK', 'result': 'stopped'}
    """
    lg.out(2, 'api.stop sending event "stop" to the shutdowner() machine')
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
        lg.out(2, 'api.restart forced for GUI, added param "show", sending event "stop" to the shutdowner() machine')
        shutdowner.A('stop', 'restartnshow')
        return OK('restarted with GUI')
    lg.out(2, 'api.restart did not found bpgui process nor forced for GUI, just do the restart, sending event "stop" to the shutdowner() machine')
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
    lg.out(2, 'api.reconnect')
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
    from lib import nameurl
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
        key_id_form_1 = my_keys.make_key_id(key_alias, creator_idurl, output_format=nameurl._FORMAT_GLOBAL_ID_KEY_USER)
        key_id_form_2 = my_keys.make_key_id(key_alias, creator_idurl, output_format=nameurl._FORMAT_GLOBAL_ID_USER_KEY)
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
         }, {
             'alias': 'another_key01',
             'id': 'another_key01$veselin@p2p-id.ru',
             'creator': 'http://p2p-id.ru/veselin.xml',
             'fingerprint': '43:c8:3b:b6:da:3e:8a:3c:48:6f:92:bb:74:b4:05:6b',
             'size': '4096',
             'ssh_type': 'ssh-rsa',
             'type': 'RSA',
             'public': 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQCmgX6j2MwEyY...'
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


def key_create(key_alias, key_size=4096):
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
        }]}
    """
    from crypt import my_keys
    from userid import my_id
    # TODO: add validation for key_alias
    key_alias = key_alias.strip().lower()
    key_id = my_keys.make_key_id(key_alias, creator_idurl=my_id.getLocalID())
    lg.out(4, 'api.key_create id=%s, size=%s' % (key_id, key_size))
    key_object = my_keys.generate_key(key_id, key_size=key_size)
    if key_object is None:
        return ERROR('failed to generate private key "%s"' % key_id)
    return OK({
        'id': key_id,
        'alias': key_alias,
        'creator': my_id.getLocalID(),
        'fingerprint': str(key_object.fingerprint()),
        'type': str(key_object.type()),
        'ssh_type': str(key_object.sshType()),
        'size': str(key_object.size()),
        'public': str(key_object.public().toString('openssh')),
    }, message='new private key "%s" was generated successfully' % key_alias, )


def key_erase(key_id):
    """
    Removes Private Key from the list of known keys and erase local file.

    Return:

        {'status': 'OK',
         'message': 'private key "ccc2" was erased successfully',
        }
    """
    lg.out(4, 'api.keys_list')
    from crypt import my_keys
    key_alias, creator_idurl = my_keys.split_key_id(key_id)
    if not key_alias or not creator_idurl:
        return ERROR('icorrect key_id format')
    if not my_keys.erase_key(key_id):
        return ERROR('failed to erase private key "%s"' % key_alias)
    return OK(message='private key "%s" was erased successfully' % key_alias)


def key_share(key_id, idurl):
    """
    """
    if not driver.is_started('service_keys_registry'):
        return succeed(ERROR('service_keys_registry() is not started'))
    from crypt import my_keys
    key_alias, creator_idurl = my_keys.split_key_id(key_id)
    if not key_alias or not creator_idurl:
        return ERROR('icorrect key_id format')
    from access import key_ring
    result = Deferred()
    d = key_ring.share_private_key(key_id, idurl)
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


def backups_update():
    """
    Sends "restart" event to backup_monitor() Automat, this should start "data
    synchronization" process with remote nodes.

    Return:

        {'status': 'OK', 'result': 'the main loop has been restarted'}
    """
    if not driver.is_started('service_backups'):
        return ERROR('service_backups() is not started')
    from storage import backup_monitor
    backup_monitor.A('restart')
    lg.out(4, 'api.backups_update')
    return OK('the main loop has been restarted')


def backups_list():
    """
    Returns a whole tree of files and folders in the catalog.

    Return:

        {'status': 'OK',
         'result': [{
            'path': '/Users/veselin/Documents',
            'versions': [],
            'type': 'parent',
            'id': '0/0/1',
            'size': 38992196
          }, {
            'path': '/Users/veselin/Documents/python',
            'versions': [],
            'type': 'parent',
            'id': '0/0/1/0',
            'size': 5754439
          }, {
            'path': '/Users/veselin/Documents/python/python27.chm',
            'versions': [{
                'version': 'F20160313043757PM',
                'blocks': 1,
                'size': '11 MB'
            }],
            'type': 'file',
            'id': '0/0/1/0/0',
            'size': 5754439
        }]}
    """
    if not driver.is_started('service_backups'):
        return ERROR('service_backups() is not started')
    from storage import backup_fs
    from lib import diskspace
    result = []
    for pathID, localPath, item in backup_fs.IterateIDs():
        result.append({
            'id': pathID,
            'path': localPath,
            'type': backup_fs.TYPES.get(item.type, '').lower(),
            'size': item.size,
            'versions': map(
                lambda v: {
                    'version': v,
                    'blocks': max(0, item.versions[v][0] + 1),
                    'size': diskspace.MakeStringFromBytes(max(0, item.versions[v][1]))},
                item.versions.keys())})
    lg.out(4, 'api.backups_list %d items returned' % len(result))
    return RESULT(result)


def backups_id_list():
    """
    Returns only list of items uploaded on remote machines.

    Return:

        {'status': 'OK',
         'result': [{
            'backupid': '0/0/1/0/0/F20160313043757PM',
            'path': '/Users/veselin/Documents/python/python27.chm',
            'size': '11 MB'
         }, {
            'backupid': '0/0/0/0/0/0/F20160315052257PM',
            'path': '/Users/veselin/Music/Bob Marley/01-Soul Rebels (1970)/01-Put It On.mp3',
            'size': '8.27 MB'
        }]}
    """
    if not driver.is_started('service_backups'):
        return ERROR('service_backups() is not started')
    from storage import backup_fs
    from contacts import contactsdb
    from lib import diskspace
    result = []
    for _, backupID, versionInfo, localPath in backup_fs.ListAllBackupIDsFull(True, True):
        if versionInfo[1] >= 0 and contactsdb.num_suppliers() > 0:
            szver = diskspace.MakeStringFromBytes(versionInfo[1]) + ' / ' + diskspace.MakeStringFromBytes(versionInfo[1] / contactsdb.num_suppliers())
        else:
            szver = '?'
        szver = diskspace.MakeStringFromBytes(versionInfo[1]) if versionInfo[1] >= 0 else '?'
        result.append({
            'backupid': backupID,
            'size': szver,
            'path': localPath})
    lg.out(4, 'api.backups_id_list %d items returned' % len(result))
    return RESULT(result)


def backup_start_id(pathID):
    """
    Start uploading a given item already existed in the catalog by its path ID.

    Return:

        {'status': 'OK', 'result': 'uploading 0/0/1/0/0 started, local path is: /Users/veselin/Documents/python/python27.chm'}
    """
    if not driver.is_started('service_backups'):
        return ERROR('service_backups() is not started')
    from system import bpio
    from storage import backup_fs
    from storage import backup_control
    from web import control
    pathID = str(pathID)
    local_path = backup_fs.ToPath(pathID)
    if local_path is not None:
        if bpio.pathExist(local_path):
            tsk = backup_control.StartSingle(pathID, local_path)
            backup_fs.Calculate()
            backup_control.Save()
            control.request_update([('pathID', pathID), ])
            lg.out(4, 'api.backup_start_id %s OK!' % pathID)
            return OK(
                'uploading %s started, local path is: %s' % (pathID, local_path),
                extra_fields={'id': pathID, 'key_id': tsk.keyID})
    lg.out(4, 'api.backup_start_id %s not found' % pathID)
    return ERROR('item %s not found' % pathID)


def backup_start_path(path, mount_path=None, key_id=None):
    """
    Start uploading file or folder to remote nodes. It will generate a new path
    ID for this file or folder and add it to the catalog.
    If `mount_path` is `None` method will create a new file (or folder) and
    all parent sub folders will be also added to the catalog:

        ["Users", "Users/veselin", "Users/veselin/Documents", "Users/veselin/Documents/python",]

    Final ID of that item will be combined from parent IDs and target file or folder ID:

        0/0/1/0/0

    In case `mount_path` is set it will act like backup_map_path()
    and start the backup process: item will be created in the `mount_path` location.

    Return:

        {'status': 'OK',
         'result': 'uploading of item 0/0/1/0/0 started, local path is: /Users/veselin/Documents/python/python27.chm',
         'id': '0/0/1/0/0',
         'type': 'file',
         'key_id': 'abc'}
    """
    if not driver.is_started('service_backups'):
        return ERROR('service_backups() is not started')
    from system import bpio
    from system import dirsize
    from storage import backup_fs
    from storage import backup_control
    from web import control
    localPath = bpio.portablePath(unicode(path))
    if not bpio.pathExist(localPath):
        lg.out(4, 'api.backup_start_path local path %s not found' % path)
        return ERROR('local path %s not found' % path)
    result = ''
    pathID = backup_fs.ToID(localPath)
    if pathID is None:
        if mount_path:
            parent_path = os.path.dirname(mount_path)
            if backup_fs.IsFile(parent_path):
                return ERROR('mount path can not be created, file already exist: %s' % parent_path)
            iter_and_iterID = backup_fs.GetIteratorsByPath(parent_path)
            if iter_and_iterID is None:
                _, parent_iter, parent_iterID = backup_fs.AddDir(parent_path, read_stats=False)
                return ERROR('mount path already exist in catalog')
            pathID, _, _ = backup_fs.MapPath(localPath, read_stats=True, iter=parent_iter, iterID=parent_iterID, keyID=key_id)
            fileorfolder = 'folder' if bpio.pathIsDir(localPath) else 'file'
            if fileorfolder == 'folder':
                dirsize.ask(localPath, backup_control.OnFoundFolderSize, (pathID, None))
        else:
            if bpio.pathIsDir(localPath):
                fileorfolder = 'folder'
                pathID, _, _ = backup_fs.AddDir(localPath, read_stats=True, key_id=key_id)
                result += 'new folder was added to catalog: %s, ' % localPath
            else:
                fileorfolder = 'file'
                pathID, _, _ = backup_fs.AddFile(localPath, read_stats=True, key_id=key_id)
        result += 'uploading of item %s started, ' % pathID
        result += 'new %s was added to catalog: %s, ' % (fileorfolder, localPath)
    else:
        item_info = backup_fs.GetByID(pathID)
        if item_info is None:
            lg.out(4, 'api.backup_start_path ERROR failed reading item %s' % pathID)
            return ERROR('failed reading item %s' % pathID)
        fileorfolder = 'file' if item_info.type == backup_fs.FILE else 'folder'
        result += 'uploading of item %s started, ' % pathID
        result += 'local %s path is: %s' % (fileorfolder, localPath)
    backup_control.StartSingle(pathID, localPath, keyID=item_info.key_id)
    backup_fs.Calculate()
    backup_control.Save()
    control.request_update([('pathID', pathID), ])
    lg.out(4, 'api.backup_start_path %s OK!' % path)
    return OK(result, extra_fields={'id': pathID, 'type': fileorfolder, 'key_id': key_id})


def backup_map_path(path, mount_path, key_id=None):
    """
    Create a new top level item in the catalog and point it to given local
    path. This is the simplest way to upload a file and get an ID for that
    remote copy. Given local `path` will be mapped to virtual `mount_path`,
    which must not exist in the catalog yet.

    Return:

        {'status': 'OK',
         'result': [ 'new file was added: 1, local path is /Users/veselin/Pictures/bitdust.png'],
         'id': '1',
         'type': 'file',
         'key_id': 'abc'}
    """
    if not driver.is_started('service_backups'):
        return ERROR('service_backups() is not started')
    from storage import backup_fs
    from storage import backup_control
    from system import dirsize
    from system import bpio
    from web import control
    path = bpio.portablePath(unicode(path))
    pathID = backup_fs.ToID(path)
    if pathID:
        return ERROR('path already exist in catalog: %s' % pathID)
    if backup_fs.Exists(mount_path):
        return ERROR('mount path already exist in catalog')
    parent_path = os.path.dirname(bpio.portablePath(unicode(mount_path)))
    if backup_fs.IsFile(parent_path):
        return ERROR('mount path can not be created, file already exist: %s' % parent_path)
    iter_and_iterID = backup_fs.GetIteratorsByPath(parent_path)
    if iter_and_iterID is None:
        _, parent_iter, parent_iterID = backup_fs.AddDir(parent_path, read_stats=False)
    else:
        parent_iter, parent_iterID = iter_and_iterID
    newPathID, _, _ = backup_fs.MapPath(path, read_stats=True, iter=parent_iter, iterID=parent_iterID, key_id=key_id)
    if os.path.isdir(path):
        fileorfolder = 'folder'
        dirsize.ask(path, backup_control.OnFoundFolderSize, (newPathID, None))
    else:
        fileorfolder = 'file'
    backup_fs.Calculate()
    backup_control.Save()
    control.request_update([('pathID', newPathID), ])
    return OK(
        'new %s was added: %s, local path is %s' % (fileorfolder, newPathID, path),
        extra_fields={'id': newPathID, 'type': fileorfolder, 'key_id': key_id})


def backup_dir_make(dirpath, key_id=None):
    """
    Creates empty folder in catalog.

    Return:

        {'status': 'OK', 'result': 'new folder was added: 0/0/8, local path is /Users/veselin/Desktop/', 'key_id': 'abc'}
    """
    if not driver.is_started('service_backups'):
        return ERROR('service_backups() is not started')
    from storage import backup_fs
    from storage import backup_control
    from system import bpio
    from web import control
    dirpath = '/' + (dirpath.lstrip('/'))
    dirpath = bpio.portablePath(unicode(dirpath))
    pathID = backup_fs.ToID(dirpath)
    if pathID:
        return ERROR('path already exist in catalog: %s' % pathID)
    newPathID, _, _ = backup_fs.AddDir(dirpath, read_stats=False, keyID=key_id)
    backup_fs.Calculate()
    backup_control.Save()
    control.request_update([('pathID', newPathID), ])
    return OK('new folder was added: %s, local path is %s' % (newPathID, dirpath),
              extra_fields={'id': newPathID, 'type': 'folder', 'key_id': key_id})


def backup_dir_add(dirpath, key_id=None):
    """
    Add given folder to the catalog but do not start uploading process. This
    method will create all sub folders in the catalog and keeps the same
    structure as your local folders structure. So the final ID will be
    combination of all parent IDs, separated with "/".

    Return:

        {'status': 'OK', 'result': 'new folder was added: 0/0/2, local path is /Users/veselin/Movies/', 'key_id': 'abc'}
    """
    if not driver.is_started('service_backups'):
        return ERROR('service_backups() is not started')
    from storage import backup_fs
    from storage import backup_control
    from system import dirsize
    from system import bpio
    from web import control
    dirpath = bpio.portablePath(unicode(dirpath))
    pathID = backup_fs.ToID(dirpath)
    if pathID:
        return ERROR('path already exist in catalog: %s' % pathID)
    newPathID, _, _ = backup_fs.AddDir(dirpath, read_stats=True, keyID=key_id)
    dirsize.ask(dirpath, backup_control.OnFoundFolderSize, (newPathID, None))
    backup_fs.Calculate()
    backup_control.Save()
    control.request_update([('pathID', newPathID), ])
    return OK('new folder was added: %s, local path is %s' % (newPathID, dirpath),
              extra_fields={'id': newPathID, 'type': 'folder', 'key_id': key_id})


def backup_file_add(filepath, key_id=None):
    """
    Add a single file to the catalog, skip uploading. This method will create
    all sub folders in the catalog and keeps the same structure as your local
    file path structure. So the final ID of that file in the catalog will be
    combination of all parent IDs, separated with "/".

    Return:

        {'status': 'OK', 'result': 'new file was added: 0/0/3/0, local path is /Users/veselin/Downloads/pytest-2.9.0.tar.gz', 'key_id': 'abc'}
    """
    if not driver.is_started('service_backups'):
        return ERROR('service_backups() is not started')
    from storage import backup_fs
    from storage import backup_control
    from system import bpio
    from web import control
    filepath = bpio.portablePath(unicode(filepath))
    pathID = backup_fs.ToID(filepath)
    if pathID:
        return ERROR('path already exist in catalog: %s' % pathID)
    newPathID, _, _ = backup_fs.AddFile(filepath, read_stats=True, keyID=key_id)
    backup_fs.Calculate()
    backup_control.Save()
    control.request_update([('pathID', newPathID), ])
    return OK('new file was added: %s, local path is %s' % (newPathID, filepath),
              extra_fields={'id': newPathID, 'type': 'file', 'key_id': key_id})


def backup_tree_add(dirpath, key_id=None):
    """
    Recursively reads the entire folder and create items in the catalog. For
    all files and folders it will keeping the same files/folders structure.
    This method will not start any uploads, just append items to the catalog.

    Return:

        {'status': 'OK',
         'result': '21 items were added to catalog, parent path ID is 0/0/1/2, root folder is /Users/veselin/Documents/reports',
         'key_id': 'abc'}
    """
    if not driver.is_started('service_backups'):
        return ERROR('service_backups() is not started')
    from storage import backup_fs
    from storage import backup_control
    from system import bpio
    from web import control
    dirpath = bpio.portablePath(unicode(dirpath))
    newPathID, _, _, num = backup_fs.AddLocalPath(dirpath, read_stats=True, key_id=key_id)
    backup_fs.Calculate()
    backup_control.Save()
    control.request_update([('pathID', newPathID), ])
    if not newPathID:
        return ERROR('nothing was added to catalog')
    return OK('%d items were added to catalog, parent path ID is %s, root folder is %s' % (
        num, newPathID, dirpath),
        extra_fields={'parent_id': newPathID, 'new_items': num, 'key_id': key_id})


def backup_delete_local(backupID):
    """
    Remove only local files belongs to this particular backup. All remote data
    stored on suppliers' machines remain unchanged.

    Return:

        {'status': 'OK',   'result': '8 files were removed with total size of 16 Mb'}
    """
    if not driver.is_started('service_backups'):
        return ERROR('service_backups() is not started')
    from storage import backup_fs
    from storage import backup_matrix
    from main import settings
    from web import control
    num, sz = backup_fs.DeleteLocalBackup(settings.getLocalBackupsDir(), backupID)
    lg.out(4, 'api.backup_delete_local %s : %d, %s' % (backupID, num, sz))
    backup_matrix.EraseBackupLocalInfo(backupID)
    backup_fs.Scan()
    backup_fs.Calculate()
    control.request_update([('backupID', backupID), ])
    return OK("%d files were removed with total size of %s" % (num, sz))


def backup_delete_id(pathID_or_backupID):
    """
    Delete local and remote copies of given item in catalog. This will
    completely remove your data from BitDust network. You can specify either
    path ID of that location or specific version.

    Return:

        {'status': 'OK',   'result': 'version 0/0/1/1/0/F20160313043419PM was deleted from remote peers'}
    """
    if not driver.is_started('service_backups'):
        return ERROR('service_backups() is not started')
    from storage import backup_fs
    from storage import backup_control
    from storage import backup_monitor
    from main import settings
    from web import control
    from lib import packetid
    if not packetid.Valid(pathID_or_backupID):
        lg.out(4, 'api.backup_delete_id invalid item %s' % pathID_or_backupID)
        return OK('invalid item id: %s' % pathID_or_backupID)
    version = None
    if packetid.IsBackupIDCorrect(pathID_or_backupID):
        pathID, version = packetid.SplitBackupID(pathID_or_backupID)
        backupID = pathID + '/' + version
    if version:
        result = backup_control.DeleteBackup(backupID, saveDB=False)
        if not result:
            lg.out(4, 'api.backup_delete_id not found %s' % backupID)
            return ERROR('item %s is not found in catalog' % backupID)
        backup_control.Save()
        backup_monitor.A('restart')
        control.request_update([('backupID', backupID), ])
        lg.out(4, 'api.backup_delete_id %s was deleted' % pathID)
        return OK('version %s was deleted from remote peers' % backupID)
    pathID = pathID_or_backupID
    result = backup_control.DeletePathBackups(pathID, saveDB=False, calculate=False)
    if not result:
        lg.out(4, 'api.backup_delete_id not found %s' % pathID)
        return ERROR('item %s is not found in catalog' % pathID)
    backup_fs.DeleteLocalDir(settings.getLocalBackupsDir(), pathID)
    backup_fs.DeleteByID(pathID)
    backup_fs.Scan()
    backup_fs.Calculate()
    backup_control.Save()
    backup_monitor.A('restart')
    control.request_update([('pathID', pathID), ])
    lg.out(4, 'api.backup_delete_id %s was deleted' % pathID)
    return OK('item %s was deleted from remote peers' % pathID)


def backup_delete_path(localPath):
    """
    Completely remove any data stored on given location from BitDust network.
    All data for given item will be removed from remote peers. Any local files
    related to this path will be removed as well.

    Return:

        {'status': 'OK',   'result': 'item 0/1/2 was deleted from remote peers'}
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
    localPath = bpio.portablePath(unicode(localPath))
    lg.out(4, 'api.backup_delete_path %s' % localPath)
    pathID = backup_fs.ToID(localPath)
    if not pathID:
        lg.out(4, 'api.backup_delete_path %s not found' % localPath)
        return ERROR('path %s is not found in catalog' % localPath)
    if not packetid.Valid(pathID):
        lg.out(4, 'api.backup_delete_path invalid %s' % pathID)
        return ERROR('invalid pathID found %s' % pathID)
    result = backup_control.DeletePathBackups(pathID, saveDB=False, calculate=False)
    if not result:
        lg.out(4, 'api.backup_delete_path %s not found' % pathID)
        return ERROR('item %s is not found in catalog' % pathID)
    backup_fs.DeleteLocalDir(settings.getLocalBackupsDir(), pathID)
    backup_fs.DeleteByID(pathID)
    backup_fs.Scan()
    backup_fs.Calculate()
    backup_control.Save()
    backup_monitor.A('restart')
    control.request_update([('pathID', pathID), ])
    lg.out(4, 'api.backup_delete_path %s was deleted' % pathID)
    return OK('item %s was deleted from remote peers' % pathID)


def backups_queue():
    """
    Returns a list of paths to be backed up as soon as currently running
    backups finish.

    Return:

        {'status': 'OK',
         'result': [{
             'created': 'Wed Apr 27 15:11:13 2016',
             'id': 3,
             'local_path': '/Users/veselin/Downloads/some-ZIP-file.zip',
             'path_id': '0/0/3/1'
        }]}
    """
    if not driver.is_started('service_backups'):
        return ERROR('service_backups() is not started')
    from storage import backup_control
    lg.out(4, 'api.backups_queue %d tasks in the queue' % len(backup_control.tasks()))
    if not backup_control.tasks():
        return RESULT([], message='there are no tasks in the queue at the moment')
    return RESULT([{
        'id': t.number,
        'path_id': t.pathID,
        'local_path': t.localPath,
        'created': time.asctime(time.localtime(t.created)),
    } for t in backup_control.tasks()])


def backups_running():
    """
    Returns a list of currently running uploads.

    Return:

        {'status': 'OK',
         'result': [{
             'aborting': False,
             'backup_id': '0/0/3/1/F20160424013912PM',
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
        }]}
    """
    if not driver.is_started('service_backups'):
        return ERROR('service_backups() is not started')
    from lib import misc
    from storage import backup_control
    lg.out(4, 'api.backups_running %d items running at the moment' % len(backup_control.jobs()))
    if not backup_control.jobs():
        return RESULT([], message='there are no jobs running at the moment')
    return RESULT([{
        'backup_id': j.backupID,
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


def backup_cancel_pending(path_id):
    """
    Cancel pending task to run backup of given item.

    Return:

        {'status': 'OK', 'result': 'item 123 cancelled'}
    """
    if not driver.is_started('service_backups'):
        return ERROR('service_backups() is not started')
    from storage import backup_control
    lg.out(4, 'api.backup_cancel_pending %s' % path_id)
    if not backup_control.AbortPendingTask(path_id):
        return ERROR(path_id, message='item %s is present in pending queue' % path_id)
    return OK(path_id, message='item %s cancelled' % path_id)


def backup_abort_running(backup_id):
    """
    Abort currently running backup.

    Return:

        {'status': 'OK', 'result': 'backup 0/0/3/1/F20160424013912PM aborted'}
    """
    if not driver.is_started('service_backups'):
        return ERROR('service_backups() is not started')
    from storage import backup_control
    lg.out(4, 'api.backup_abort_running %s' % backup_id)
    if not backup_control.AbortRunningBackup(backup_id):
        return ERROR(backup_id, message='backup %s is not running at the moment' % backup_id)
    return OK(backup_id, message='backup %s aborted' % backup_id)

#------------------------------------------------------------------------------


def restore_single(pathID_or_backupID_or_localPath, destinationPath=None):
    """
    Download data from remote peers to your local machine. You can use
    different methods to select the target data:

      + item ID in the catalog
      + full version identifier
      + local path

    It is possible to select the destination folder to extract requested files to.
    By default this method uses known location from catalog for given item.

    WARNING: Your existing local data will be overwritten!

    Return:

        {'status': 'OK', 'result': 'downloading of version 0/0/1/1/0/F20160313043419PM has been started to /Users/veselin/Downloads/restore/'}
    """
    if not driver.is_started('service_restores'):
        return ERROR('service_restores() is not started')
    from storage import backup_fs
    from storage import backup_control
    from storage import restore_monitor
    from web import control
    from system import bpio
    from lib import packetid
    if not packetid.Valid(pathID_or_backupID_or_localPath):
        localPath = bpio.portablePath(unicode(pathID_or_backupID_or_localPath))
        pathID = backup_fs.ToID(localPath)
        if not pathID:
            lg.out(4, 'api.restore_single path %s not found' % localPath)
            return ERROR('path %s is not found in catalog' % localPath)
        item = backup_fs.GetByID(pathID)
        if not item:
            lg.out(4, 'api.restore_single item %s not found' % pathID)
            return ERROR('item %s is not found in catalog' % pathID)
        version = item.get_latest_version()
        backupID = pathID + '/' + version
    else:
        if packetid.IsBackupIDCorrect(pathID_or_backupID_or_localPath):
            pathID, version = packetid.SplitBackupID(pathID_or_backupID_or_localPath)
            backupID = pathID + '/' + version
        elif packetid.IsPathIDCorrect(pathID_or_backupID_or_localPath):
            pathID = pathID_or_backupID_or_localPath
            item = backup_fs.GetByID(pathID)
            if not item:
                lg.out(4, 'api.restore_single item %s not found' % pathID)
                return ERROR('path %s is not found in catalog' % pathID)
            version = item.get_latest_version()
            if not version:
                lg.out(4, 'api.restore_single not found versions %s' % pathID)
                return ERROR('not found any versions for %s' % pathID)
            backupID = pathID + '/' + version
        else:
            lg.out(4, 'api.restore_single %s not valid location' % pathID_or_backupID_or_localPath)
            return ERROR('not valid location')
    if backup_control.IsBackupInProcess(backupID):
        lg.out(4, 'api.restore_single %s in process' % backupID)
        return ERROR('download not possible, uploading %s is in process' % backupID)
    pathID, version = packetid.SplitBackupID(backupID)
    if restore_monitor.IsWorking(backupID):
        lg.out(4, 'api.restore_single %s scheduled already' % pathID)
        return OK('downloading task for %s already scheduled' % pathID)
    localPath = backup_fs.ToPath(pathID)
    if not localPath:
        lg.out(4, 'api.restore_single %s not found' % pathID)
        return ERROR('location %s not found in catalog' % pathID)
    if destinationPath:
        if len(localPath) > 3 and localPath[1] == ':' and localPath[2] == '/':
            # TODO: - also may need to check other options like network drive (//) or so
            localPath = localPath[3:]
        localDir = os.path.dirname(localPath.lstrip('/'))
        restoreDir = os.path.join(destinationPath, localDir)
        restore_monitor.Start(backupID, restoreDir)
        control.request_update([('pathID', pathID), ])
    else:
        restoreDir = os.path.dirname(localPath)
        restore_monitor.Start(backupID, restoreDir)
        control.request_update([('pathID', pathID), ])
    lg.out(4, 'api.restore_single %s OK!' % backupID)
    return OK('downloading of version %s has been started to %s' % (backupID, restoreDir))


def restores_running():
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
            'created': 'Wed Apr 27 15:11:13 2016',
            'eccmap': 'ecc/4x4',
            'path_id': '0/0/3/1',
            'version': 'F20160427011209PM'
        }]}
    """
    if not driver.is_started('service_restores'):
        return ERROR('service_restores() is not started')
    from storage import restore_monitor
    lg.out(4, 'api.restores_running %d items downloading at the moment' % len(restore_monitor.GetWorkingObjects()))
    if not restore_monitor.GetWorkingObjects():
        return RESULT([], message='there are no downloads running at the moment')
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
        'eccmap': '' if not r.EccMap else r.EccMap.name,
    } for r in restore_monitor.GetWorkingObjects()])


def restore_abort(backup_id):
    """
    Abort currently running restore process.

    Return:

        {'status': 'OK',  'result': 'restoring of item 123 aborted'}
    """
    if not driver.is_started('service_restores'):
        return ERROR('service_restores() is not started')
    from storage import restore_monitor
    lg.out(4, 'api.restore_abort %s' % backup_id)
    if not restore_monitor.Abort(backup_id):
        return ERROR(backup_id, 'item %s is not restoring at the moment' % backup_id)
    return OK(backup_id, 'restoring of item %s aborted' % backup_id)

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
    return RESULT([{
        'position': s[0],
        'idurl': s[1],
        'connected': misc.readSupplierData(s[1], 'connected'),
        'numfiles': len(misc.readSupplierData(s[1], 'listfiles').split('\n')) - 1,
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
        return OK('supplier %s will be replaced by new peer' % idurl)
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
        return ERROR('peer %s is your supplier already' % new_idurl)
    from customer import fire_hire
    from customer import supplier_finder
    supplier_finder.AddSupplierToHire(new_idurl)
    fire_hire.AddSupplierToFire(idurl)
    fire_hire.A('restart')
    return OK('supplier %s will be replaced by %s' % (idurl, new_idurl))


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
    # restart local tester
    local_tester.TestUpdateCustomers()
    return OK('customer %s rejected, %s bytes were freed' % (idurl, consumed_by_cutomer))


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
        return ERROR('service %s not found' % service_name)
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
        return ERROR('service %s was not found' % service_name)
    if svc.state == 'ON':
        lg.out(4, 'api.service_start %s already started' % service_name)
        return ERROR('service %s already started' % service_name)
    current_config = config.conf().getBool(svc.config_path)
    if current_config:
        lg.out(4, 'api.service_start %s already enabled' % service_name)
        return ERROR('service %s already enabled' % service_name)
    config.conf().setBool(svc.config_path, True)
    lg.out(4, 'api.service_start (%s)' % service_name)
    return OK('%s was switched on' % service_name)


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
        return ERROR('service %s not found' % service_name)
    current_config = config.conf().getBool(svc.config_path)
    if current_config is None:
        lg.out(4, 'api.service_stop config item %s was not found' % svc.config_path)
        return ERROR('config item %s was not found' % svc.config_path)
    if current_config is False:
        lg.out(4, 'api.service_stop %s already disabled' % service_name)
        return ERROR('service %s already disabled' % service_name)
    config.conf().setBool(svc.config_path, False)
    lg.out(4, 'api.service_stop (%s)' % service_name)
    return OK('%s was switched off' % service_name)

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
    Sends a text message to remote peer.

    Return:

        {'status': 'OK', 'result': ['signed.Packet[Message(146681300413)]']}
    """
    if not driver.is_started('service_private_messages'):
        return ERROR('service_private_messages() is not started')
    from chat import message
    recipient = str(recipient)
    if not recipient.startswith('http://'):
        from contacts import contactsdb
        recipient = contactsdb.find_correspondent_by_nickname(recipient) or recipient
    result = message.SendMessage(recipient, message_body)
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

    def _message_received(packet, text):
        ret.callback(OK({
            'message': text,
            'from': packet.OwnerID,
        }))
        message.RemoveIncomingMessageCallback(_message_received)
        return True
    message.AddIncomingMessageCallback(_message_received)
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
