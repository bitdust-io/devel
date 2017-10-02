#!/usr/bin/python
# local_fs.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (local_fs.py) is part of BitDust Software.
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
.. module:: local_fs.

This module should be able to provide access to local file system. The
GUI needs to show all existing local files, just like in Explorer.
"""

import os
import sys
import stat

from logs import lg

from main import settings

from system import bpio
from storage import backup_fs
from storage import backup_control
from storage import backup_monitor

#------------------------------------------------------------------------------

def mount(private_key_id, root_folder_name):
    return None


def unmount(root_folder_name):
    return None


def statfs():
    return None


def ls(location='.'):
    # always assume we have absolute path location
    path = '/' + location.lstrip('/')
    lst = backup_fs.ListByPathAdvanced(path)
    if not isinstance(lst, list):
        lg.warn('backup_fs.ListByPathAdvanced returned: %s' % lst)
        return None
    result = []
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
    return {
        'result': 'OK',
        'ls': result,
    }


def chown(location, idurl, params):
    return None


def chgrp(location, group_iurl, params):
    return None


def chmod(location, idurl, group_iurl, params):
    return None


def mkfile(location, idurl=None, group_iurl=None, params=None):
    # always assume we have absolute path location
    path = '/' + location.lstrip('/')
    pathID = backup_fs.ToID(path)
    if pathID is not None:
        return None
    pathID, _, _ = backup_fs.AddFile(path, read_stats=True)
    backup_control.Save()
    return {
        'result': 'OK',
        'id': pathID,
        'path': path,
    }


def mkdir(location):
    # always assume we have absolute path location
    path = '/' + location.lstrip('/')
    pathID = backup_fs.ToID(path)
    if pathID is not None:
        return None
    pathID, _, _ = backup_fs.AddDir(path, read_stats=True)
    backup_control.Save()
    return {
        'result': 'OK',
        'id': pathID,
        'path': path,
    }


def upfile(location, local_path, idurl=None, group_iurl=None, params=None):
    # always assume we have absolute path location
    path = '/' + location.lstrip('/')
    localPath = unicode(local_path)
    if not bpio.pathExist(localPath):
        return None
    pathID = backup_fs.ToID(localPath)
    if pathID is None:
        if bpio.pathIsDir(localPath):
            pathID, _, _ = backup_fs.AddDir(localPath, read_stats=True)
        else:
            pathID, _, _ = backup_fs.AddFile(localPath, read_stats=True)
    bk_task = backup_control.StartSingle(pathID, localPath)
    backup_fs.Calculate()
    backup_control.Save()
    return {
        'result': 'OK',
        'id': pathID,
        'path': path,
        'local_path': localPath,
        'task_number': bk_task.number,
        'task_created': bk_task.created,
    }

def rm(location, params=None):
    # always assume we have absolute path location
    path = '/' + location.lstrip('/')
    pathID = backup_fs.ToID(path)
    if pathID is None:
        return None
    item = backup_fs.GetByID(pathID)
    if not item:
        return None
    if item.type != backup_fs.FILE:
        return None
    backup_control.DeletePathBackups(pathID, saveDB=False, calculate=False)
    backup_fs.DeleteLocalDir(settings.getLocalBackupsDir(), pathID)
    backup_fs.DeleteByID(pathID)
    backup_fs.Scan()
    backup_fs.Calculate()
    backup_control.Save()
    backup_monitor.A('restart')
    return {
        'result': 'OK',
        'id': pathID,
        'path': path,
        'type': item.type,
        'size': item.size,
    }


def rmdir(location):
    # always assume we have absolute path location
    path = '/' + location.lstrip('/')
    pathID = backup_fs.ToID(path)
    if pathID is None:
        return None
    item = backup_fs.GetByID(pathID)
    if not item:
        return None
    if item.type not in [backup_fs.DIR, backup_fs.PARENT, ]:
        return None
    backup_control.DeletePathBackups(pathID, saveDB=False, calculate=False)
    backup_fs.DeleteLocalDir(settings.getLocalBackupsDir(), pathID)
    backup_fs.DeleteByID(pathID)
    backup_fs.Scan()
    backup_fs.Calculate()
    backup_control.Save()
    backup_monitor.A('restart')
    return {
        'result': 'OK',
        'id': pathID,
        'path': path,
        'type': backup_fs.TYPES[item.type],
        'size': item.size,
    }
