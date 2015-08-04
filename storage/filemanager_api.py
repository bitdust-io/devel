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

from services import driver

#------------------------------------------------------------------------------ 

def process(json_request):
    lg.out(4, 'filemanager_api.process %s' % json_request)
    if not driver.is_started('service_backups'):
        return { 'result': {
            "success": False,
            "error": "network [service_backups] is not started: %s" % (
               driver.services().get('service_backups', '!!! not found !!!')) }}
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
        elif mode == 'delete':
            result = _delete(json_request['params'])
        lg.out(14, '    %s' % pprint.pformat(result))
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
        # return { "result": { "success": False, "error": lst }}        
    for item in lst:
        if item[2] == 'index':
            continue
        result.append({
            "type": item[0], 
            "name": item[1],
            "id": item[2],
            "rights": "",
            "size": str(item[3]),
            "date": item[4]
        })
    # pprint.pprint(result)
    return { 'result': result, }
        
        
        
    
#    root_item_id = backup_fs.ToID(path)
#    if root_item_id:
#        root_item = backup_fs.WalkByID(root_item_id)
#        if not root_item:
#            lg.warn('backup_fs item %s was not found, but exist' % root_item_id)
#            return { "result": { "success": False, "error": 'backup_fs item %s was not found, but exist' % root_item_id }}
#        root_item = root_item[0]
#        print path, root_item_id, root_item
#        if isinstance(root_item, backup_fs.FSItemInfo):
#            root_item_info = root_item
#        else:
#            root_item_info = root_item.get(backup_fs.INFO_KEY, None)
#            if root_item_info and isinstance(root_item_info, backup_fs.FSItemInfo):
#                for version in root_item_info.list_versions(True, True):
#                    # print root_item_id, version, misc.TimeStructFromVersion(packetid.SplitBackupID(version)[1])
#                    result.append({
#                        "name": str(root_item_id + '/' + version),
#                        "rights": "", # "drwxr-xr-x",
#                        "size": str(root_item_info.get_version_size(version)),
#                        # "date": "-".join(map(str,misc.TimeStructFromVersion(packetid.SplitBackupID(version)[1]))),
#                        # "date": list(misc.TimeStructFromVersion(packetid.SplitBackupID(version)[1])),
#                        'date': time.strftime("%Y-%m-%d %H:%M:%S", misc.TimeStructFromVersion(packetid.SplitBackupID(version)[1])),
#                        "type": "file", 
#                    })
#        for pathID, localPath, item in backup_fs.ListChilds(root_item):
#            item_size = 0
#            item_time = 0 
#            for version in item.list_versions(True, True):
#                version_size = item.get_version_size(version)
#                if version_size > 0:
#                    item_size += version_size 
#                version_time = misc.TimeFromBackupID(version)
#                if version_time and version_time > item_time:
#                    item_time = version_time
#            # print pathID, localPath, item_size, item_time
#            result.append({
#                "name": item.name(),
#                "rights": "", # "drwxr-xr-x",
#                "size": str(item_size),
#                # "date": "-".join(map(str,time.gmtime(item_time))) if item_time else '',
#                # "date": list(time.gmtime(item_time)) if item_time else [],
#                "date": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(item_time)) if item_time else '',
#                "type": "dir", 
#            })
#    else:
#        for pathID, localPath, item in backup_fs.ListRootItems():
#            item_size = 0 
#            item_time = 0 
#            for version in item.list_versions(True, True):
#                version_size = item.get_version_size(version)
#                if version_size > 0:
#                    item_size += version_size 
#                version_time = misc.TimeFromBackupID(version)
#                if version_time and version_time > item_time:
#                    item_time = version_time
#            result.append({
#                "name": item.name(),
#                "rights": "", # "drwxr-xr-x",
#                "size": str(item_size),
#                # "date": "-".join(map(str,time.gmtime(item_time))) if item_time else '',
#                # "date": list(time.gmtime(item_time)) if item_time else [],
#                "date": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(item_time)) if item_time else '',
#                "type": "dir", 
#            })
#    pprint.pprint(result)
#    return { 'result': result, }

#------------------------------------------------------------------------------ 

def _list_local(params):
    result = []
    path = params['path'].lstrip('/')
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
    backup_monitor.A('restart')
    return { 'result': { "success": True, "error": None } }

    
    
#------------------------------------------------------------------------------ 

def _rename(params):
    pass
    

#------------------------------------------------------------------------------ 

def _rename(params):
    pass


