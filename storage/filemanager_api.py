#!/usr/bin/python
#filemanager_api.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: filemanager_api

"""

#------------------------------------------------------------------------------ 

import os
import time
import pprint
import traceback

from logs import lg

from system import bpio

from lib import packetid
from lib import misc

from main import settings

from storage import backup_fs
from storage import backup_control
from storage import backup_monitor
from storage import restore_monitor
from web import control 

from services import driver

#------------------------------------------------------------------------------ 

def process(json_request):
    # lg.out(4, 'filemanager_api.process %s' % json_request)
    if not driver.is_started('service_backups'):
        return { 'result': {
            "success": False,
            "error": "network [service_backups] is not started: %s" % (
               driver.services().get('service_backups', '!!! not found !!!')) }}
    mode = ''
    result = []
    try:
        if isinstance(json_request, str) or isinstance(json_request, unicode):
            import json
            json_request = json.loads(json_request)
        mode = json_request['params']['mode']
        if mode == 'list':
            result = _list(json_request['params'])
        elif mode == 'listlocal':
            result = _list_local(json_request['params'])
        elif mode == 'upload':
            result = _upload(json_request['params'])
        elif mode == 'delete':
            result = _delete(json_request['params'])
        elif mode == 'download':
            result = _download(json_request['params'])
        # lg.out(14, '    %s' % pprint.pformat(result))
        return result
    except:
        lg.exc()
        return { "result": { "success": False, "error": traceback.format_exc() }} 
    lg.out(4, '    ERROR unknown mode: %s' % mode)
    return { "result": { "success": False, "error": 'mode %s not supported' % mode }}

#------------------------------------------------------------------------------ 

def _list(params):
    result = []
    path = params['path'].lstrip('/')
    lst = backup_fs.ListByPathAdvanced(path)
    if not isinstance(lst, list):
        lg.warn('backup_fs.ListByPathAdvanced returned: %s' % lst)
        return { "result": [], }
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
            "status": item[5],
        })
    return { 'result': result, }

#------------------------------------------------------------------------------ 

def _list_local(params):
    result = []
    path = params['path'].lstrip('/')
    only_folders = params['onlyFolders']
    if ( path == '' or path == '/' ) and bpio.Windows():
        for itemname in bpio.listLocalDrivesWindows():
            result.append({
                "name": itemname.rstrip('\\').rstrip('/').lower(),
                "rights": "drwxr-xr-x",
                "size": "",
                "date": "",
                "type": "dir",
            })
    else:
        if bpio.Windows() and len(path) == 2 and path[1] == ':':
            path += '/' 
        apath = os.path.abspath(path)
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
            })
    return { 'result': result, }
  
#------------------------------------------------------------------------------ 

def _upload(params):
    path = params['path'].lstrip('/')
    localPath = unicode(path)
    if not bpio.pathExist(localPath):
        return { 'result': { "success": False, "error": 'local path %s was not found' % path } } 
    result = []
    pathID = backup_fs.ToID(localPath)
    if pathID is None:
        if bpio.pathIsDir(localPath):
            pathID, iter, iterID = backup_fs.AddDir(localPath, True)
            result.append('new folder was added: %s' % localPath)
        else:
            pathID, iter, iterID = backup_fs.AddFile(localPath, True)
            result.append('new file was added: %s' % localPath)
    print '_add_file_folder', pathID, localPath
    backup_control.StartSingle(pathID)
    backup_fs.Calculate()
    backup_control.Save()
    control.request_update()
    result.append('backup started: %s' % pathID)
    return { 'result': result, }

#------------------------------------------------------------------------------ 

def _delete(params):
    localPath = params['path'].lstrip('/')
    localName = params['name']
    pathID = params['id']
    if not packetid.Valid(pathID):
        return { 'result': { "success": False, "error": "path %s is not valid" % pathID} }
    version = None
    pathID_, version_ = packetid.SplitBackupID(pathID)
    if packetid.IsCanonicalVersion(version_) and version_ == localName:
        version = version_
        pathID = pathID_
    if not backup_fs.ExistsID(pathID):
        return { 'result': { "success": False, "error": "path %s not found" % pathID} }
    if version:
        backup_control.DeleteBackup(pathID+'/'+version, saveDB=False, calculate=False)
    else:
        backup_control.DeletePathBackups(pathID, saveDB=False, calculate=False)
        backup_fs.DeleteLocalDir(settings.getLocalBackupsDir(), pathID)
        backup_fs.DeleteByID(pathID)
    backup_fs.Scan()
    backup_fs.Calculate()
    backup_control.Save()
    control.request_update()
    backup_monitor.A('restart')
    return { 'result': { "success": True, "error": None } }

    
    
#------------------------------------------------------------------------------ 

def _download(params):
    localName = params['name']
    backupID = params['id']
    restorePath = bpio.portablePath(params['dest_path'])
    overwrite = params['overwrite']
    if not packetid.Valid(backupID):
        return { 'result': { "success": False, "error": "path %s is not valid" % backupID} }
    pathID, version = packetid.SplitBackupID(backupID)
    if not pathID:
        return { 'result': { "success": False, "error": "path %s is not valid" % backupID} }
    if backup_control.IsBackupInProcess(backupID):
        return { 'result': { "success": True, "error": None } }
    if backup_control.HasTask(pathID):
        return { 'result': { "success": True, "error": None } }
    localPath = backup_fs.ToPath(pathID)
    if localPath == restorePath:
        restorePath = os.path.dirname(restorePath)
    def _itemRestored(backupID, result): 
        backup_fs.ScanID(packetid.SplitBackupID(backupID)[0])
        backup_fs.Calculate()
    restore_monitor.Start(backupID, restorePath, _itemRestored) 
    return { 'result': { "success": True, "error": None } }

#------------------------------------------------------------------------------ 

def _rename(params):
    return { 'result': { "success": False, "error": "not done yet" } }


