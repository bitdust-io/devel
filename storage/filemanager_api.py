#!/usr/bin/python
# filemanager_api.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (filemanager_api.py) is part of BitDust Software.
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
..

module:: filemanager_api
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

import os
import sys
import time
import pprint

#------------------------------------------------------------------------------

from lib import strng

from logs import lg

from system import bpio

from lib import packetid
from lib import misc

from main import settings
from main import control

from services import driver

from transport import packet_in
from transport import packet_out

from storage import backup_fs
from storage import backup_control
from storage import backup_monitor
from storage import restore_monitor

from userid import my_id
from userid import global_id

#------------------------------------------------------------------------------


def process(json_request):
    lg.out(12, 'filemanager_api.process %s' % json_request)
    if not driver.is_on('service_backups'):
        return {'result': {
            "success": False,
            "error": "network [service_backups] is not started: %s" % (
                driver.services().get('service_backups', '!!! not found !!!'))}}
    mode = ''
    result = {}
    try:
        if strng.is_string(json_request):
            import json
            json_request = json.loads(json_request)
        mode = json_request['params']['mode']
        if mode == 'config':
            result = _config(json_request['params'])
        elif mode == 'stats':
            result = _stats(json_request['params'])
        elif mode == 'list':
            result = _list(json_request['params'])
        elif mode == 'listlocal':
            result = _list_local(json_request['params'])
        elif mode == 'listall':
            result = _list_all(json_request['params'])
        elif mode == 'upload':
            result = _upload(json_request['params'])
        elif mode == 'delete':
            result = _delete(json_request['params'])
        elif mode == 'deleteversion':
            result = _delete_version(json_request['params'])
        elif mode == 'download':
            result = _download(json_request['params'])
        elif mode == 'tasks':
            result = _list_active_tasks(json_request['params'])
        elif mode == 'packets':
            result = _list_in_out_packets(json_request['params'])
        elif mode == 'connections':
            result = _list_active_connections(json_request['params'])
        elif mode == 'streams':
            result = _list_active_streams(json_request['params'])
        elif mode == 'debuginfo':
            result = _debuginfo(json_request['params'])
        else:
            result = {"result": {"success": False,
                                 "error": 'filemanager method %s not found' % mode}}
    except Exception as exc:
        lg.exc()
        descr = str(sys.exc_info()[0].__name__) + ': ' + str(sys.exc_info()[1])
        result = {"result": {"success": False,
                             "error": descr}}
    # lg.out(4, '    ERROR unknown mode: %s' % mode)
    lg.out(20, '    %s' % pprint.pformat(result))
    return result

#------------------------------------------------------------------------------


def _config(params):
    result = []
    homepath = bpio.portablePath(os.path.expanduser('~'))
    if bpio.Windows():
        # set "c:" as a starting point when pick files for Windows
        # probably should be MyDocuments folder or something else,
        # but lets take that for now
        homepath = homepath[:2]
    result.append({'key': 'homepath',
                   'value': homepath})
    return {'result': result, }


def _stats(params):
    from contacts import contactsdb
    from p2p import online_status
    from lib import diskspace
    result = {}
    result['suppliers'] = contactsdb.num_suppliers()
    result['max_suppliers'] = settings.getSuppliersNumberDesired()
    result['online_suppliers'] = online_status.countOnlineAmong(contactsdb.suppliers())
    result['customers'] = contactsdb.num_customers()
    result['bytes_donated'] = settings.getDonatedBytes()
    result['value_donated'] = diskspace.MakeStringFromBytes(settings.getDonatedBytes())
    result['bytes_needed'] = settings.getNeededBytes()
    result['value_needed'] = diskspace.MakeStringFromBytes(settings.getNeededBytes())
    result['bytes_used_total'] = backup_fs.sizebackups()
    result['value_used_total'] = diskspace.MakeStringFromBytes(backup_fs.sizebackups())
    result['bytes_used_supplier'] = 0 if (contactsdb.num_suppliers() == 0) else (int(backup_fs.sizebackups() / contactsdb.num_suppliers()))
    result['bytes_indexed'] = backup_fs.sizefiles() + backup_fs.sizefolders()
    result['files_count'] = backup_fs.numberfiles()
    result['folders_count'] = backup_fs.numberfolders()
    result['items_count'] = backup_fs.counter()
    result['timestamp'] = time.time()
    return {'result': result, }


def _list(params):
    result = []
    path = params['path']
    if bpio.Linux() or bpio.Mac():
        path = '/' + path.lstrip('/')
    lst = backup_fs.ListByPathAdvanced(path)
    if not isinstance(lst, list):
        lg.warn('backup_fs.ListByPathAdvanced returned: %s' % lst)
        return {"result": [], }
    for item in lst:
        if item[2] == 'index':
            continue
        result.append({
            "type": item[0],
            "name": item[1],
            "id": item[2],
            "rights": "",
            "size": item[3],
            "source_size": item[7].size,
            "date": item[4],
            "dirpath": item[5],
            "has_childs": item[6],
            "content": '1' if item[7].exist() else '',
            "versions": item[8],
        })
    return {'result': result, }


def _list_all(params):
    result = []
    lst = backup_fs.ListAllBackupIDsAdvanced()
    for item in lst:
        if item[2] == 'index':
            continue
        result.append({
            "type": item[0],
            "name": item[1],
            "id": item[2],
            "rights": "",
            "size": item[3],
            "date": item[4],
            "dirpath": item[5],
            "has_childs": item[6],
            "content": '1' if item[7] else '',
            "versions": item[8],
        })
    return {'result': result, }


def _list_local(params):
    result = []
    path = params['path']
    if bpio.Linux() or bpio.Mac():
        path = '/' + path.lstrip('/')
    path = bpio.portablePath(path)
    only_folders = params['onlyFolders']
    if (path == '' or path == '/') and bpio.Windows():
        for itemname in bpio.listLocalDrivesWindows():
            result.append({
                "name": itemname.rstrip('\\').rstrip('/').lower(),
                "rights": "drwxr-xr-x",
                "size": "",
                "date": "",
                "type": "dir",
                "dirpath": path,
            })
    else:
        if bpio.Windows() and len(path) == 2 and path[1] == ':':
            path += '/'
        apath = path
        for itemname in bpio.list_dir_safe(apath):
            itempath = os.path.join(apath, itemname)
            if only_folders and not os.path.isdir(itempath):
                continue
            result.append({
                "name": itemname,
                "rights": "drwxr-xr-x",
                "size": str(os.path.getsize(itempath)),
                "date": str(os.path.getmtime(itempath)),
                "type": "dir" if os.path.isdir(itempath) else "file",
                "dirpath": apath,
            })
    return {'result': result, }


def _upload(params):
    path = params['path']
    if bpio.Linux() or bpio.Mac():
        path = '/' + (path.lstrip('/'))
    localPath = strng.to_text(path)
    if not bpio.pathExist(localPath):
        return {'result': {"success": False, "error": 'local path %s was not found' % path}}
    result = []
    pathID = backup_fs.ToID(localPath)
    if pathID is None:
        if bpio.pathIsDir(localPath):
            pathID, iter, iterID = backup_fs.AddDir(localPath, read_stats=True)
            result.append('new folder was added: %s' % localPath)
        else:
            pathID, iter, iterID = backup_fs.AddFile(localPath, read_stats=True)
            result.append('new file was added: %s' % localPath)
    pathID = global_id.CanonicalID(pathID)
    backup_control.StartSingle(pathID=pathID, localPath=localPath)
    backup_fs.Calculate()
    backup_control.Save()
    control.request_update([('pathID', pathID), ])
    result.append('backup started: %s' % pathID)
    return {'result': result, }


def _download(params):
    # localName = params['name']
    backupID = global_id.CanonicalID(params['backupid'])
    destpath = params['dest_path']
    if bpio.Linux() or bpio.Mac():
        destpath = '/' + destpath.lstrip('/')
    restorePath = bpio.portablePath(destpath)
    # overwrite = params['overwrite']
    customerGlobalID, remotePath, version = packetid.SplitBackupID(backupID)
    pathID = packetid.MakeBackupID(customerGlobalID, remotePath)
    if not customerGlobalID:
        customerGlobalID = my_id.getGlobalID()
    if not packetid.IsCanonicalVersion(version):
        return {'result': {"success": False, "error": "path %s is not valid" % backupID}}
    if not remotePath:
        return {'result': {"success": False, "error": "path %s is not valid" % backupID}}
    if not packetid.Valid(remotePath):
        return {'result': {"success": False, "error": "path %s is not valid" % backupID}}
    if backup_control.IsBackupInProcess(backupID):
        return {'result': {"success": True, "error": None}}
    if backup_control.HasTask(pathID):
        return {'result': {"success": True, "error": None}}
    localPath = backup_fs.ToPath(remotePath)
    if localPath == restorePath:
        restorePath = os.path.dirname(restorePath)

    def _itemRestored(backupID, result):
        customerGlobalID, remotePath, _ = packetid.SplitBackupID(backupID)
        backup_fs.ScanID(remotePath, customer_idurl=global_id.GlobalUserToIDURL(customerGlobalID))
        backup_fs.Calculate()

    restore_monitor.Start(backupID, restorePath, callback=_itemRestored)
    return {'result': {"success": True, "error": None}}


def _delete(params):
    # localPath = params['path'].lstrip('/')
    pathID = params['id']
    if not packetid.Valid(pathID):
        return {'result': {"success": False, "error": "path %s is not valid" % pathID}}
    if not backup_fs.ExistsID(pathID):
        return {'result': {"success": False, "error": "path %s not found" % pathID}}
    backup_control.DeletePathBackups(pathID, saveDB=False, calculate=False)
    backup_fs.DeleteLocalDir(settings.getLocalBackupsDir(), pathID)
    backup_fs.DeleteByID(pathID)
    backup_fs.Scan()
    backup_fs.Calculate()
    backup_control.Save()
    control.request_update([('pathID', pathID), ])
    backup_monitor.A('restart')
    return {'result': {"success": True, "error": None}}


def _delete_version(params):
    lg.out(6, '_delete_version %s' % str(params))
    backupID = params['backupid']
    if not packetid.Valid(backupID):
        return {'result': {"success": False, "error": "backupID %s is not valid" % backupID}}
    customerGlobalID, remotePath, version = packetid.SplitBackupID(backupID)
    if not customerGlobalID:
        customerGlobalID = my_id.getGlobalID()
    if not backup_fs.ExistsID(remotePath, iterID=backup_fs.fsID(global_id.GlobalUserToIDURL(customerGlobalID))):
        return {'result': {"success": False, "error": "path %s not found" % remotePath}}
    if version:
        backup_control.DeleteBackup(backupID, saveDB=False, calculate=False)
    backup_fs.Scan()
    backup_fs.Calculate()
    backup_control.Save()
    backup_monitor.A('restart')
    control.request_update([('backupID', backupID), ])
    return {'result': {"success": True, "error": None}}


def _rename(params):
    return {'result': {"success": False, "error": "not done yet"}}


def _list_active_tasks(params):
    result = []
    for tsk in backup_control.ListPendingTasks():
        result.append({
            'name': os.path.basename(tsk.localPath),
            'path': os.path.dirname(tsk.localPath),
            'id': tsk.pathID,
            'version': '',
            'customer': '',
            'mode': 'up',
            'progress': '0%', })
    for backupID in backup_control.ListRunningBackups():
        backup_obj = backup_control.GetRunningBackupObject(backupID)
        customerGlobalID, remotePath, versionName = packetid.SplitBackupID(backupID)
        result.append({
            'name': os.path.basename(backup_obj.sourcePath),
            'path': os.path.dirname(backup_obj.sourcePath),
            'id': remotePath,
            'version': versionName,
            'customer': customerGlobalID,
            'mode': 'up',
            'progress': misc.percent2string(backup_obj.progress()), })
    # for backupID in restore_monitor.GetWorkingIDs():
    #     result.append(backupID)
    return {'result': result, }


def _list_in_out_packets(params):
    result = []
    for pkt_out in packet_out.queue():
        result.append({
            'name': pkt_out.outpacket.Command,
            'label': pkt_out.label,
            'from_to': 'to',
            'target': pkt_out.remote_idurl,
        })
    for pkt_in in list(packet_in.inbox_items()).values():
        result.append({
            'name': pkt_in.transfer_id,
            'label': pkt_in.label,
            'from_to': 'from',
            'target': pkt_in.sender_idurl,
        })
    return {'result': result, }


def _list_active_streams(params):
    result = []
    if not driver.is_on('service_gateway'):
        return {'result': result, }
    from transport import gateway
    result = []
    wanted_protos = params.get('protos', [])
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
    return {'result': result, }


def _list_active_connections(params):
    result = []
    if not driver.is_on('service_gateway'):
        return {'result': result, }
    from transport import gateway
    result = []
    wanted_protos = params.get('protos', [])
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
    return {'result': result, }


def _debuginfo(params):
    result = {}
    result['debug'] = lg.get_debug_level()
    result['automats'] = []
    from automats import automat
    for index, A in automat.objects().items():
        result['automats'].append({
            'index': index,
            'id': A.id,
            'name': A.name,
            'state': A.state, })
    return {'result': result, }
