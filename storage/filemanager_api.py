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
import pprint
import traceback

from logs import lg

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
    print '_list', root_item_id
    if not root_item_id:
        for pathID, localPath, item in backup_fs.ListRootItems():
            result.append({
                "name": item.name(),
                "rights": "drwxr-xr-x",
                "size": str(item.size if item else ''),
                "date": '',
                "type": "dir" if item.type != backup_fs.FILE else "file", 
            })
    else:
        for pathID, localPath, item in backup_fs.ListByID(root_item_id):
            print pathID, localPath, item
            result.append({
                "name": item.name(),
                "rights": "drwxr-xr-x",
                "size": str(item.size if item else ''),
                "date": item.get_latest_version() if item else '',
                "type": "dir" if item.type != backup_fs.FILE else "file", 
            })
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

