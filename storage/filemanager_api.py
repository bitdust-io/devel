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

from lib import packetid
from lib import misc

#------------------------------------------------------------------------------ 

def process(json_request):
    lg.out(4, 'filemanager_api.process %s' % json_request)
    mode = ''
    try:
        if isinstance(json_request, str) or isinstance(json_request, unicode):
            import json
            json_request = json.loads(json_request)
        mode = json_request['params']['mode']
        if mode == 'list':
            result = _list(json_request['params'])
        elif mode == 'listlocal':
            result = _list_local(json_request['params'])
        elif mode == 'addfilefolder':
            result = _add_file_folder(json_request['params'])
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
    from storage import backup_fs
    root_item_id = backup_fs.ToID(path)
    if root_item_id:
        root_item = backup_fs.WalkByID(root_item_id)
        if not root_item:
            lg.warn('backup_fs item %s was not found, but exist' % root_item_id)
            return { "result": { "success": False, "error": 'backup_fs item %s was not found, but exist' % root_item_id }}
        root_item = root_item[0]
        root_item_info = root_item.get(backup_fs.INFO_KEY, None)
        if root_item_info and isinstance(root_item_info, backup_fs.FSItemInfo):
            for version in root_item_info.list_versions(True, True):
                # print root_item_id, version, misc.TimeStructFromVersion(packetid.SplitBackupID(version)[1])
                result.append({
                    "name": str(root_item_id + '/' + version),
                    "rights": "", # "drwxr-xr-x",
                    "size": str(root_item_info.get_version_size(version)),
                    # "date": "-".join(map(str,misc.TimeStructFromVersion(packetid.SplitBackupID(version)[1]))),
                    # "date": list(misc.TimeStructFromVersion(packetid.SplitBackupID(version)[1])),
                    'date': time.strftime("YYYY-mm-dd HH:MM:SS", misc.TimeStructFromVersion(packetid.SplitBackupID(version)[1])),
                    "type": "file", 
                })
        for pathID, localPath, item in backup_fs.ListChilds(root_item):
            item_size = 0
            item_time = 0 
            for version in item.list_versions(True, True):
                version_size = item.get_version_size(version)
                if version_size > 0:
                    item_size += version_size 
                version_time = misc.TimeFromBackupID(version)
                if version_time and version_time > item_time:
                    item_time = version_time
            # print pathID, localPath, item_size, item_time
            result.append({
                "name": item.name(),
                "rights": "", # "drwxr-xr-x",
                "size": str(item_size),
                # "date": "-".join(map(str,time.gmtime(item_time))) if item_time else '',
                # "date": list(time.gmtime(item_time)) if item_time else [],
                "date": time.strftime("YYYY-mm-dd HH:MM:SS", time.gmtime(item_time)) if item_time else '',
                "type": "dir", 
            })
    else:
        for pathID, localPath, item in backup_fs.ListRootItems():
            item_size = 0 
            item_time = 0 
            for version in item.list_versions(True, True):
                version_size = item.get_version_size(version)
                if version_size > 0:
                    item_size += version_size 
                version_time = misc.TimeFromBackupID(version)
                if version_time and version_time > item_time:
                    item_time = version_time
            result.append({
                "name": item.name(),
                "rights": "", # "drwxr-xr-x",
                "size": str(item_size),
                # "date": "-".join(map(str,time.gmtime(item_time))) if item_time else '',
                # "date": list(time.gmtime(item_time)) if item_time else [],
                "date": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(item_time)) if item_time else '',
                "type": "dir", 
            })
    pprint.pprint(result)
    return { 'result': result, }

#------------------------------------------------------------------------------ 

def _list_local(params):
    result = []
    path = params['path'].lstrip('/')
    from system import bpio
    if path == '' or path == '/' and bpio.Windows():
        for itemname in bpio.listLocalDrivesWindows():
            result.append({
                "name": itemname,
                "rights": "drwxr-xr-x",
                "size": "",
                "date": "",
                "type": "dir", 
            })
    else:
        apath = os.path.abspath(path)
        for itemname in bpio.list_dir_safe(apath):
            itempath = os.path.join(apath, itemname)
            result.append({
                "name": itemname,
                "rights": "drwxr-xr-x",
                "size": str(os.path.getsize(itempath)),
                "date": str(os.path.getmtime(itempath)),
                "type": "dir" if os.path.isdir(itempath) else "file", 
            })
    return { 'result': result, }
  
#------------------------------------------------------------------------------ 

def _add_file_folder(params):
    path = params['path'].lstrip('/')
    from system import bpio
    from storage import backup_fs
    from storage import backup_control
    localPath = unicode(path)
    if not bpio.pathExist(localPath):
        return { "success": False, "error": 'local path %s was not found' % path } 
    result = []
    pathID = backup_fs.ToID(localPath)
    if pathID is None:
        if bpio.pathIsDir(localPath):
            pathID, iter, iterID = backup_fs.AddDir(localPath, True)
            result.append('new folder was added: %s' % localPath)
        else:
            pathID, iter, iterID = backup_fs.AddFile(localPath, True)
            result.append('new file was added: %s' % localPath)
    backup_control.StartSingle(pathID)
    backup_fs.Calculate()
    backup_control.Save()
    result.append('backup started: %s' % pathID)
    return { 'result': result, }

