#!/usr/bin/python
# backup_fs.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (backup_fs.py) is part of BitDust Software.
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
.. module:: backup_fs.

This is some kind of file system.
To store backed up data on remote peers we can not use original files and folders names -
they must be encrypted or indexed. I decide to use index, but keep the files and folders structure.
Instead of names I am using numbers.

For example::

  C:/Documents and Settings/veselin/Application Data/Google/

Can have a path ID like this::

  0/2/0/5/23

Linux paths can be indexed same way::

  /home/veselin/Documents/document.pdf

Can be translated to::

  0/2/4/18

The software keeps 2 index dictionaries in the memory:

* path -> ID
* ID -> path

Those dictionaries are trees - replicates the file system structure.
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from __future__ import print_function
from six.moves import range
from io import StringIO

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

import os
import sys
import time
import json
import random

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from bitdust.lib import strng

from bitdust.logs import lg

from bitdust.system import bpio

from bitdust.main import settings
from bitdust.main import listeners

from bitdust.services import driver

from bitdust.lib import misc
from bitdust.lib import packetid
from bitdust.lib import jsn

from bitdust.crypt import my_keys

from bitdust.contacts import identitycache

from bitdust.interface import api

from bitdust.userid import my_id
from bitdust.userid import global_id
from bitdust.userid import id_url

#------------------------------------------------------------------------------

INFO_KEY = 'i'
UNKNOWN = -1
FILE = 0
DIR = 1
TYPES = {
    UNKNOWN: 'UNKNOWN',
    FILE: 'FILE',
    DIR: 'DIR',
}

#------------------------------------------------------------------------------

_FileSystemIndexByName = {}
_FileSystemIndexByID = {}
_RevisionNumber = {}
_ItemsCount = 0
_FilesCount = 0
_DirsCount = 0
_SizeFiles = 0
_SizeFolders = 0
_SizeBackups = 0

#------------------------------------------------------------------------------


def init():
    """
    Some initial steps can be done here.
    """
    if _Debug:
        lg.out(_DebugLevel, 'backup_fs.init')
    LoadAllIndexes()
    SaveIndex()


def shutdown():
    """
    Should be called when the program is finishing.
    """
    if _Debug:
        lg.out(_DebugLevel, 'backup_fs.shutdown')
    ClearAllIndexes()


#------------------------------------------------------------------------------


def fs(customer_idurl=None, key_alias='master'):
    """
    Access method for forward index: [path] -> [ID].
    """
    global _FileSystemIndexByName
    if customer_idurl is None:
        customer_idurl = my_id.getIDURL()
    customer_idurl = id_url.field(customer_idurl)
    if customer_idurl not in _FileSystemIndexByName:
        _FileSystemIndexByName[customer_idurl] = {}
        if _Debug:
            lg.dbg(_DebugLevel, 'new customer registered : %r' % customer_idurl)
    if key_alias is None:
        return _FileSystemIndexByName[customer_idurl]
    if key_alias not in _FileSystemIndexByName[customer_idurl]:
        _FileSystemIndexByName[customer_idurl][key_alias] = {}
        if _Debug:
            lg.dbg(_DebugLevel, 'new key alias registered for customer %r : %r' % (customer_idurl, key_alias))
    return _FileSystemIndexByName[customer_idurl][key_alias]


def fsID(customer_idurl=None, key_alias='master'):
    """
    Access method for backward index: [ID] -> [path].
    """
    global _FileSystemIndexByID
    if customer_idurl is None:
        customer_idurl = my_id.getIDURL()
    customer_idurl = id_url.field(customer_idurl)
    if customer_idurl not in _FileSystemIndexByID:
        _FileSystemIndexByID[customer_idurl] = {}
        if _Debug:
            lg.dbg(_DebugLevel, 'new customer registered : %r' % customer_idurl)
    if key_alias is None:
        return _FileSystemIndexByID[customer_idurl]
    if key_alias not in _FileSystemIndexByID[customer_idurl]:
        _FileSystemIndexByID[customer_idurl][key_alias] = {}
        if _Debug:
            lg.dbg(_DebugLevel, 'new key alias registered for customer %r : %r' % (customer_idurl, key_alias))
    return _FileSystemIndexByID[customer_idurl][key_alias]


#------------------------------------------------------------------------------


def revision(customer_idurl=None, key_alias='master'):
    """
    Mutator method to access current software revision number.
    """
    global _RevisionNumber
    if customer_idurl is None:
        customer_idurl = my_id.getIDURL()
    customer_idurl = id_url.field(customer_idurl)
    if customer_idurl not in _RevisionNumber:
        _RevisionNumber[customer_idurl] = {}
        if _Debug:
            lg.dbg(_DebugLevel, 'new customer registered : %r' % customer_idurl)
    if key_alias not in _RevisionNumber[customer_idurl]:
        _RevisionNumber[customer_idurl][key_alias] = -1
        if _Debug:
            lg.dbg(_DebugLevel, 'new key alias registered for customer %r : %r' % (customer_idurl, key_alias))
    return _RevisionNumber[customer_idurl][key_alias]


def commit(new_revision_number=None, customer_idurl=None, key_alias='master'):
    """
    Need to be called after any changes in the index database.

    This increase revision number by 1 or set revision to ``new_revision_number`` if not None.
    """
    global _RevisionNumber
    if customer_idurl is None:
        customer_idurl = my_id.getIDURL()
    customer_idurl = id_url.field(customer_idurl)
    if customer_idurl not in _RevisionNumber:
        _RevisionNumber[customer_idurl] = {}
        if _Debug:
            lg.dbg(_DebugLevel, 'new customer registered : %r' % customer_idurl)
    if key_alias not in _RevisionNumber[customer_idurl]:
        _RevisionNumber[customer_idurl][key_alias] = 0
        if _Debug:
            lg.dbg(_DebugLevel, 'new key alias registered for customer %r : %r' % (customer_idurl, key_alias))
    old_v = _RevisionNumber[customer_idurl][key_alias]
    if new_revision_number is not None:
        _RevisionNumber[customer_idurl][key_alias] = new_revision_number
    else:
        _RevisionNumber[customer_idurl][key_alias] += 1
    new_v = _RevisionNumber[customer_idurl][key_alias]
    if _Debug:
        lg.args(_DebugLevel, old=old_v, new=new_v, c=customer_idurl, k=key_alias)
    return old_v, new_v


def forget(customer_idurl=None, key_alias=None):
    """
    Release currently known revision number for the corresponding index.
    """
    global _RevisionNumber
    if _Debug:
        lg.args(_DebugLevel, c=customer_idurl, k=key_alias)
    if customer_idurl is None:
        _RevisionNumber.clear()
        return
    customer_idurl = id_url.field(customer_idurl)
    if customer_idurl not in _RevisionNumber:
        lg.warn('customer %r was not registered' % customer_idurl)
        return
    if key_alias is None:
        _RevisionNumber[customer_idurl].clear()
        return
    if key_alias not in _RevisionNumber[customer_idurl]:
        lg.warn('key alias %r was not registered for customer %r' % (key_alias, customer_idurl))
        return
    _RevisionNumber[customer_idurl].pop(key_alias)


#------------------------------------------------------------------------------


def known_customers():
    global _FileSystemIndexByID
    return list(_FileSystemIndexByID.keys())


def known_keys_aliases(customer_idurl):
    global _FileSystemIndexByID
    if customer_idurl is None:
        customer_idurl = my_id.getIDURL()
    customer_idurl = id_url.field(customer_idurl)
    return list(_FileSystemIndexByID.get(customer_idurl, {}).keys())


#------------------------------------------------------------------------------


def counter():
    """
    Software keeps track of total number of indexed items, this returns that
    value.
    """
    global _ItemsCount
    return _ItemsCount


def numberfiles():
    """
    Number of indexed files.
    """
    global _FilesCount
    return _FilesCount


def numberfolders():
    """
    Number of indexed files.
    """
    global _DirsCount
    return _DirsCount


def sizefiles():
    """
    Total size of all indexed files.
    """
    global _SizeFiles
    return _SizeFiles


def sizefolders():
    """
    Total size of all indexed folders.

    May be incorrect, because folder size is not calculated regular yet.
    """
    global _SizeFolders
    return _SizeFolders


def sizebackups():
    """
    Total size of all indexed backups.
    """
    global _SizeBackups
    return _SizeBackups


#------------------------------------------------------------------------------


class FSItemInfo():

    """
    A class to represent a remote file or folder.
    """

    def __init__(self, name='', path_id='', typ=UNKNOWN, key_id=None):
        self.unicodename = strng.to_text(name)
        self.path_id = path_id
        self.type = typ
        self.size = -1
        self.key_id = key_id
        self.versions = {}

    def __repr__(self):
        return '<%s %s %d %s>' % (TYPES[self.type], misc.unicode_to_str_safe(self.name()), self.size, self.key_id)

    def to_json(self):
        return {
            'name': self.unicodename,
            'path_id': self.path_id,
            'type': self.type,
            'size': self.size,
            'key_id': self.key_id,
            'versions': self.versions,
        }

    def filename(self):
        return os.path.basename(self.unicodename)

    def name(self):
        return self.unicodename

    def key_alias(self):
        if not self.key_id:
            return 'master'
        return self.key_id.split('$')[0]

    def exist(self):
        return self.size != -1

    def set_size(self, sz):
        self.size = sz

    def read_stats(self, path):
        if not bpio.pathExist(path):
            return False
        if bpio.pathIsDir(path):
            return False
        try:
            s = os.stat(path)
        except:
            try:
                s = os.stat(path.decode('utf-8'))
            except:
                lg.exc()
                return False
        self.size = int(s.st_size)
        return True

    def read_versions(self, local_path):
        path = bpio.portablePath(local_path)
        if not bpio.pathExist(path):
            return 0
        if not os.access(path, os.R_OK):
            return 0
        totalSize = 0
        for version in bpio.list_dir_safe(path):
            if self.get_version_info(version)[0] >= 0:
                continue
            versionSize = 0
            maxBlock = -1
            if not packetid.IsCanonicalVersion(version):
                continue
            versionpath = os.path.join(path, version)
            if not bpio.pathExist(versionpath):
                continue
            if not os.access(versionpath, os.R_OK):
                return 0
            for filename in bpio.list_dir_safe(versionpath):
                filepath = os.path.join(versionpath, filename)
                if not packetid.IsPacketNameCorrect(filename):
                    lg.warn('incorrect file name found: %s' % filepath)
                    continue
                try:
                    blockNum, supplierNum, _ = filename.split('-')
                    blockNum, supplierNum = int(blockNum), int(supplierNum)
                except:
                    lg.warn('incorrect file name found: %s' % filepath)
                    continue
                try:
                    sz = int(os.path.getsize(filepath))
                except:
                    lg.exc()
                    sz = 0
                # TODO:
                # add some bytes because on remote machines all files are stored as signed.Packet()
                # so they have a header and files size will be bigger than on local machine
                # we do not know how big head is, so just add an approximate value
                versionSize += sz + 1024
                maxBlock = max(maxBlock, blockNum)
            self.set_version_info(version, maxBlock, versionSize)
            totalSize += versionSize
        return totalSize

    def add_version(self, version):
        self.versions[version] = [-1, -1]

    def set_version_info(self, version, maxblocknum, sizebytes):
        self.versions[version] = [maxblocknum, sizebytes]

    def get_version_info(self, version):
        return self.versions.get(version, [-1, -1])

    def get_version_size(self, version):
        return self.versions.get(version, [-1, -1])[1]

    def delete_version(self, version):
        self.versions.pop(version, None)

    def has_version(self, version):
        return version in self.versions

    def any_version(self):
        return len(self.versions) > 0

    def list_versions(self, sorted=False, reverse=False):
        if sorted:
            return misc.sorted_versions(list(self.versions.keys()), reverse)
        return list(self.versions.keys())

    def get_versions(self):
        return self.versions

    def get_latest_version(self):
        if len(self.versions) == 0:
            return None
        return self.list_versions(True)[0]

    def pack_versions(self):
        out = []
        for version in self.list_versions(True):
            info = self.versions[version]
            out.append(version + ':' + str(info[0]) + ':' + str(info[1]))
        return ' '.join(out)

    def unpack_versions(self, inpt):
        for word in inpt.split(' '):
            if not word.strip():
                continue
            try:
                version, maxblock, sz = word.split(':')
                maxblock, sz = int(maxblock), int(sz)
            except:
                version, maxblock, sz = word, -1, -1
            self.set_version_info(version, maxblock, sz)

    def serialize(self, encoding='utf-8', to_json=False):
        if _Debug:
            lg.args(_DebugLevel, k=self.key_id, pid=self.path_id, v=list(self.versions.keys()), i=id(self), iv=id(self.versions))
        if to_json:
            return {
                'n': strng.to_text(self.unicodename, encoding=encoding),
                'i': strng.to_text(self.path_id),
                't': self.type,
                's': self.size,
                'k': self.key_id,
                'v': [{
                    'n': v,
                    'b': self.versions[v][0],
                    's': self.versions[v][1],
                } for v in self.list_versions(sorted=True)],
            }
        e = strng.to_text(self.unicodename, encoding=encoding)
        return '%s %d %d %s\n%s\n' % (self.path_id, self.type, self.size, self.pack_versions(), e)

    def unserialize(self, src, decoding='utf-8', from_json=False):
        if from_json:
            try:
                self.unicodename = strng.to_text(src['n'], encoding=decoding)
                self.path_id = strng.to_text(src['i'], encoding=decoding)
                self.type = src['t']
                self.size = src['s']
                self.key_id = my_keys.latest_key_id(strng.to_text(src['k'], encoding=decoding))
                self.versions = {strng.to_text(v['n']): [v['b'], v['s']] for v in src['v']}
            except:
                lg.exc()
                raise KeyError('Incorrect item format:\n%s' % src)
            if _Debug:
                lg.args(_DebugLevel, k=self.key_id, pid=self.path_id, v=list(self.versions.keys()), i=id(self), iv=id(self.versions))
            return True

        try:
            details, name = strng.to_text(src, encoding=decoding).split('\n')[:2]
        except:
            raise Exception('incorrect item format:\n%s' % src)
        if not details or not name:
            raise Exception('incorrect item format:\n%s' % src)
        try:
            self.unicodename = name
            details = details.split(' ')
            self.path_id, self.type, self.size = details[:3]
            self.type, self.size = int(self.type), int(self.size)
            self.unpack_versions(' '.join(details[3:]))
        except:
            lg.exc()
            raise KeyError('incorrect item format:\n%s' % src)
        if _Debug:
            lg.args(_DebugLevel, k=self.key_id, pid=self.path_id, v=list(self.versions.keys()), i=id(self), iv=id(self.versions))
        return True


#------------------------------------------------------------------------------


def MakeID(itr, randomized=True):
    """
    Create a new unique number for the file or folder to create a index ID.

    Parameter ``itr`` is a reference for a single item in the ``fs()``.
    """
    current_ids = []
    for k in itr.keys():
        if k == 0:
            continue
        if k == settings.BackupIndexFileName():
            continue
        try:
            if isinstance(itr[k], int):
                current_ids.append(int(itr[k]))
            elif isinstance(itr[k], dict) and 0 in itr[k]:
                current_ids.append(int(itr[k][0]))
            else:
                continue
        except:
            lg.exc()
            continue
    new_id = 0
    if randomized:
        digits = 1
        while True:
            attempts = 0
            new_id = int(random.choice('0123456789'))
            while new_id in current_ids and attempts <= 2:
                new_id = int(''.join([v() for v in [
                    lambda: random.choice('0123456789'),
                ]*digits]))
                attempts += 1
            if new_id not in current_ids:
                return new_id
            digits += 1
    while new_id in current_ids:
        new_id += 1
    return new_id


#------------------------------------------------------------------------------


def AddFile(path, read_stats=False, iter=None, iterID=None, key_id=None):
    """
    Scan all components of the ``path`` and create an item in the index for
    that file.

        >>> import backup_fs
        >>> backup_fs.AddFile('C:/Documents and Settings/veselin/Application Data/Google/GoogleEarth/myplaces.kml')
        ('0/0/0/0/0/0/0', {0: 0, u'myplaces.kml': 0}, {'i': <PARENT GoogleEarth -1>, 0: <FILE myplaces.kml -1>})

    Here path must be in "portable" form - only '/' allowed, assume path is a file, not a folder.
    """
    parts = bpio.remotePath(path).split('/')
    key_alias = 'master'
    if key_id:
        key_alias = key_id.split('$')[0]
    if iter is None:
        iter = fs(key_alias=key_alias)
    if iterID is None:
        iterID = fsID(key_alias=key_alias)
    resultID = ''
    parentKeyID = None
    # build whole tree, skip the last part
    for i in range(len(parts) - 1):
        name = parts[i]
        if not name:
            continue
        p = '/'.join(parts[:i + 1])
        if bpio.Linux() or bpio.Mac():
            p = '/' + p
        if name not in iter:
            # made a new ID for this folder, ID starts from 0. new folders will get the last ID +1
            # or it may find a free place in the middle, if some folders or files were removed before
            # this way we try to protect the files and directories names. we store index in the encrypted files
            id = MakeID(iter)
            # build a unique backup id for that file including all indexed ids
            resultID += '/' + str(id)
            # make new sub folder
            ii = FSItemInfo(name=name, path_id=resultID.lstrip('/'), typ=DIR, key_id=(key_id or parentKeyID))
            if read_stats:
                ii.read_stats(p)
            # we use 0 key as decimal value, all files and folders are strings - no conflicts possible 0 != '0'
            iter[ii.name()] = {0: id}
            # also save index from opposite side
            iterID[id] = {INFO_KEY: ii}
        else:
            # get an existing ID from the index
            id = iter[name][0]
            # go down into the existing forest
            resultID += '/' + str(id)
        # move down to the next level
        parentKeyID = iterID[id][INFO_KEY].key_id
        iter = iter[name]
        iterID = iterID[id]
    # the last part of the path is a filename
    filename = parts[-1]
    # make an ID for the filename
    id = MakeID(iter)
    resultID += '/' + str(id)
    resultID = resultID.lstrip('/')
    ii = FSItemInfo(name=filename, path_id=resultID, typ=FILE, key_id=(key_id or parentKeyID))
    if read_stats:
        ii.read_stats(path)
    iter[ii.name()] = id
    iterID[id] = ii
    # finally make a complete backup id - this a relative path to the backed up file
    return resultID, ii, iter, iterID


def AddDir(path, read_stats=False, iter=None, iterID=None, key_id=None, force_path_id=None):
    """
    Add specific local directory to the index, but do not read content of the folder.
    """
    parts = bpio.remotePath(path).split('/')
    force_path_id_parts = []
    if force_path_id is not None:
        force_path_id_parts = bpio.remotePath(force_path_id).split('/')
    key_alias = 'master' if not key_id else key_id.split('$')[0]
    if iter is None:
        iter = fs(key_alias=key_alias)
    if iterID is None:
        iterID = fsID(key_alias=key_alias)
    resultID = ''
    parentKeyID = None
    ii = None
    for i in range(len(parts)):
        name = parts[i]
        if not name:
            continue
        p = '/'.join(parts[:i + 1])
        if bpio.Linux() or bpio.Mac():
            p = '/' + p
        if name not in iter:
            id = 0
            if force_path_id_parts:
                id = int(force_path_id_parts[0])
                force_path_id_parts = force_path_id_parts[1:]
            else:
                id = MakeID(iter)
            resultID += '/' + str(id)
            ii = FSItemInfo(name, path_id=resultID.lstrip('/'), typ=DIR, key_id=(key_id or parentKeyID))
            if read_stats:
                ii.read_stats(p)
            iter[ii.name()] = {0: id}
            iterID[id] = {INFO_KEY: ii}
        else:
            id = iter[name][0]
            resultID += '/' + str(id)
        parentKeyID = iterID[id][INFO_KEY].key_id
        iter = iter[name]
        iterID = iterID[id]
        if i == len(parts) - 1:
            if iterID[INFO_KEY].type != DIR:
                lg.warn('not a dir: %s' % iterID[INFO_KEY])
            iterID[INFO_KEY].type = DIR
    return resultID.lstrip('/'), ii, iter, iterID


def AddLocalPath(localpath, read_stats=False, iter=None, iterID=None, key_id=None):
    """
    Operates like ``AddDir()`` but also recursively reads the entire folder and
    put all items in the index. Parameter ``localpath`` can be a file or folder path.
    """

    def recursive_read_dir(local_path, path_id, iter, iterID):
        c = 0
        lastID = -1
        path = bpio.portablePath(local_path)
        if not os.access(path, os.R_OK):
            return c
        for localname in bpio.list_dir_safe(path):
            p = os.path.join(path, localname)
            name = strng.to_text(localname)
            if bpio.pathIsDir(p):
                if name not in iter:
                    id = MakeID(iter, lastID)
                    ii = FSItemInfo(name=name, path_id=(path_id + '/' + str(id)).lstrip('/'), typ=DIR, key_id=key_id)
                    iter[ii.name()] = {0: id}
                    if read_stats:
                        ii.read_stats(p)
                    iterID[id] = {INFO_KEY: ii}
                    lastID = id
                else:
                    id = iter[name][0]
                c += recursive_read_dir(p, path_id + '/' + str(id), iter[name], iterID[id])
            else:
                id = MakeID(iter, lastID)
                ii = FSItemInfo(name=name, path_id=(path_id + '/' + str(id)).lstrip('/'), typ=FILE, key_id=key_id)
                if read_stats:
                    ii.read_stats(p)
                iter[ii.name()] = id
                iterID[id] = ii
                c += 1
                lastID = id
        return c

    localpath = bpio.portablePath(localpath)
    if bpio.pathIsDir(localpath):
        path_id, itemInfo, iter, iterID = AddDir(localpath, read_stats=read_stats, iter=iter, iterID=iterID, key_id=key_id)
        num = recursive_read_dir(localpath, path_id, iter, iterID)
        return path_id, iter, iterID, num
    else:
        path_id, itemInfo, iter, iterID = AddFile(localpath, read_stats=read_stats, iter=iter, iterID=iterID, keyID=key_id)
        return path_id, iter, iterID, 1
    return None, None, None, 0


def PutItem(name, parent_path_id, as_folder=False, iter=None, iterID=None, key_id=None):
    """
    Acts like AddFile() but do not follow the directory structure. This just
    "bind" some local path (file or folder) to one single item in the catalog - by default as a top level item.
    The name of new item will be equal to the local filename.
    """
    remote_path = bpio.remotePath(name)
    key_alias = 'master' if not key_id else key_id.split('$')[0]
    if iter is None:
        iter = fs(key_alias=key_alias)
    if iterID is None:
        iterID = fsID(key_alias=key_alias)
    # make an ID for the filename
    newItemID = MakeID(iter)
    resultID = (parent_path_id.strip('/') + '/' + str(newItemID)).strip('/')
    typ = DIR if as_folder else FILE
    ii = FSItemInfo(name=remote_path, path_id=resultID, typ=typ, key_id=key_id)
    iter[ii.name()] = newItemID
    iterID[newItemID] = ii
    return resultID, ii, iter, iterID


#------------------------------------------------------------------------------


def SetFile(item, customer_idurl=None):
    """
    Put existing FSItemInfo ``item`` (for some single file) into the index.

    This is used when loading index from file. Should create all parent
    items in the index.

    Returns two boolean flags: success or not, modified or not
    """
    key_alias = item.key_alias()
    iter = fs(customer_idurl, key_alias)
    iterID = fsID(customer_idurl, key_alias)
    parts = item.path_id.lstrip('/').split('/')
    for j in range(len(parts)):
        part = parts[j]
        id = misc.ToInt(part, part)
        if j == len(parts) - 1:
            if item.name() not in iter:
                iter[item.name()] = id
                iterID[id] = item
                return True, True
            if item.pack_versions() == iterID[id].pack_versions():
                return True, False
            iterID[id] = item
            lg.warn('updated list of versions for %r' % item)
            return True, True
        found = False
        for name in iter.keys():
            if name == 0:
                continue
            if isinstance(iter[name], dict):
                if iter[name][0] == id:
                    iter = iter[name]
                    iterID = iterID[id]
                    found = True
                    break
                continue
        if not found:
            return False, False
    return False, False


def SetDir(item, customer_idurl=None):
    """
    Same, but ``item`` is a folder.
    """
    key_alias = item.key_alias()
    iter = fs(customer_idurl, key_alias)
    iterID = fsID(customer_idurl, key_alias)
    parts = item.path_id.lstrip('/').split('/')
    itemname = item.name()
    for j in range(len(parts)):
        part = parts[j]
        id = misc.ToInt(part, part)
        if j == len(parts) - 1:
            modified = False
            if itemname not in iter:
                iter[itemname] = {}
                modified = True
            if iter[itemname].get(0) != int(id):
                modified = True
            iter[itemname][0] = int(id)
            if id not in iterID:
                iterID[id] = {}
                modified = True
            cur_item = iterID[id].get(INFO_KEY)
            if not cur_item:
                modified = True
            iterID[id][INFO_KEY] = item
            return True, modified
        found = False
        for name in iter.keys():
            if name == 0:
                continue
            if isinstance(iter[name], int):
                continue
            if isinstance(iter[name], dict):
                if iter[name][0] == id:
                    iter = iter[name]
                    iterID = iterID[id]
                    found = True
                    break
                continue
            if strng.is_string(iter[name]):
                if iter[name] == itemname:
                    iter = iter[name]
                    iterID = iterID[id]
                    found = True
                    break
                continue
            raise Exception('wrong data type in the index')
        if not found:
            return False, False
    return False, False


#------------------------------------------------------------------------------


def WalkByPath(path, iter=None):
    """
    Search for ``path`` in the index - starting from root node if ``iter`` is None.

    Return None or tuple (iterator, ID).

      >>> backup_fs.WalkByPath('C:/Program Files/7-Zip/7z.exe')
      (3, '0/0/0/3')
      >>> backup_fs.WalkByPath('C:/Program Files/7-Zip/Lang/')
      ({0: 10, u'ru.txt': 1, u'en.ttt': 0}, '0/0/0/10')
    """
    if iter is None:
        iter = fs()
    ppath = bpio.remotePath(path)
    if ppath in iter:
        if isinstance(iter[ppath], int):
            return iter, str(iter[path])
        return iter[ppath], str(iter[ppath][0])
    if ppath == '' or ppath == '/':
        return iter, iter[0] if 0 in iter else ''
    path_id = ''
    parts = ppath.lstrip('/').split('/')
    for j in range(len(parts)):
        name = parts[j]
        if name not in iter:
            return None
        if isinstance(iter[name], dict):
            if 0 not in iter[name]:
                raise Exception('file or directory ID missed in the index')
            path_id += '/' + str(iter[name][0])
        elif isinstance(iter[name], int):
            if j != len(parts) - 1:
                return None
            path_id += '/' + str(iter[name])
        else:
            raise Exception('wrong data type in the index')
        if j == len(parts) - 1:
            return iter[name], path_id.lstrip('/')
        iter = iter[name]
    return None


def WalkByID(pathID, iterID=None):
    """
    Same, but search by ID:

        >>> backup_fs.WalkByID('0/0/0/10/1')
        (<FILE ru.txt 19107>, u'c:/Program Files/7-Zip/Lang/ru.txt')

    Both "walk" operations is working at O(log(n)) performance.
    """
    if iterID is None:
        iterID = fsID()
    if pathID is None:
        return None
    if pathID.strip() == '' or pathID.strip() == '/':
        return iterID, ''
    path = ''
    parts = pathID.strip('/').split('/')
    for j in range(len(parts)):
        part = parts[j]
        id = misc.ToInt(part, part)
        if id not in iterID:
            return None
        if isinstance(iterID[id], dict):
            if INFO_KEY not in iterID[id]:
                raise Exception('directory info missed in the index')
            name = iterID[id][INFO_KEY].name()
            if bpio.pathIsDriveLetter(name) or bpio.pathIsNetworkLocation(name):
                path += name
            else:
                path += '/' + name
        elif isinstance(iterID[id], FSItemInfo):
            if j != len(parts) - 1:
                return None
            path += '/' + iterID[id].name()
        else:
            raise Exception('wrong data type in the index')
        if j == len(parts) - 1:
            return iterID[id], ResolvePath(path)
        iterID = iterID[id]
    return None


#------------------------------------------------------------------------------


def DeleteByID(pathID, iter=None, iterID=None):
    """
    Delete item from index and return its path or None if not found.
    """
    if iter is None:
        iter = fs()
    if iterID is None:
        iterID = fsID()
    path = ''
    parts = pathID.strip('/').split('/')
    for j in range(len(parts)):
        part = parts[j]
        id = misc.ToInt(part, part)
        if id not in iterID:
            return None
        if isinstance(iterID[id], dict):
            if INFO_KEY not in iterID[id]:
                raise Exception('directory info missed in the index')
            name = iterID[id][INFO_KEY].name()
            if bpio.pathIsDriveLetter(name) or bpio.pathIsNetworkLocation(name):
                path += name
            else:
                path += '/' + name
        elif isinstance(iterID[id], FSItemInfo):
            name = iterID[id].name()
            path += '/' + name
            if j != len(parts) - 1:
                return None
        else:
            raise Exception('wrong data type in the index')
        if name not in iter:
            raise Exception('can not found target name in the index')
        if j == len(parts) - 1:
            iterID.pop(id)
            iter.pop(name)
            return path
        iterID = iterID[id]
        iter = iter[name]
    return None


def DeleteByPath(path, iter=None, iterID=None):
    """
    Delete given ``path`` from the index and return its ID.
    """
    if iter is None:
        iter = fs()
    if iterID is None:
        iterID = fsID()
    path_id = ''
    ppath = bpio.remotePath(path)
    parts = ppath.lstrip('/').split('/')
    if ppath in iter:
        path_id = iter[ppath]
        iter.pop(ppath)
        iterID.pop(path_id)
        return str(path_id)
    for j in range(len(parts)):
        name = parts[j]
        if name not in iter:
            return None
        if isinstance(iter[name], dict):
            if 0 not in iter[name]:
                raise Exception('directory ID missed in the index')
            id = iter[name][0]
            path_id += '/' + str(id)
        elif isinstance(iter[name], int):
            id = iter[name]
            path_id += '/' + str(id)
            if j != len(parts) - 1:
                return None
        else:
            raise Exception('wrong data type in the index')
        if id not in iterID:
            raise Exception('can not found target ID in the index')
        if j == len(parts) - 1:
            iter.pop(name)
            iterID.pop(id)
            return path_id.lstrip('/')
        iter = iter[name]
        iterID = iterID[id]
    return None


def DeleteBackupID(backupID, iterID=None):
    """
    Return backup from the index by its full ID.
    """
    keyAlias, customerGlobalID, remotePath, versionName = packetid.SplitBackupIDFull(backupID)
    if remotePath is None:
        lg.warn('%r has wrong format, remote path is not recognized' % backupID)
        return False
    customer_idurl = global_id.GlobalUserToIDURL(customerGlobalID)
    if iterID is None:
        iterID = fsID(customer_idurl, keyAlias)
    info = GetByID(remotePath, iterID=iterID)
    if info is None:
        lg.warn('not able to find file info for %r' % remotePath)
        return False
    if not info.has_version(versionName):
        lg.warn('%s do not have version %s' % (remotePath, versionName))
        return False
    info.delete_version(versionName)
    if _Debug:
        lg.args(_DebugLevel, backupID=backupID, versionName=versionName)
    return True


#------------------------------------------------------------------------------


def ToID(lookup_path, iter=None):
    """
    A wrapper for ``WalkByPath()`` method.
    """
    iter_and_id = WalkByPath(lookup_path, iter=iter)
    if iter_and_id is None:
        return None
    return iter_and_id[1]


def ToPath(pathID, iterID=None):
    """
    Get a full relative path from ``pathID``, this is a wrapper for
    ``WalkByID()`` method::

        >>> backup_fs.ToPath("/0/0/12/1")
        u'/home/veselin/Documents/somefile.txt'

    Return None if that ``pathID`` does not exist in the index.
    """
    iter_and_path = WalkByID(pathID, iterID=iterID)
    if iter_and_path is None:
        return None
    return iter_and_path[1]


#------------------------------------------------------------------------------


def GetByID(pathID, iterID=None):
    """
    Return iterator to item with given ID, search in the index with
    ``WalkByID()``.
    """
    iter_and_path = WalkByID(pathID, iterID=iterID)
    if iter_and_path is None:
        return None
    if isinstance(iter_and_path[0], dict):
        return iter_and_path[0][INFO_KEY]
    return iter_and_path[0]


def GetByPath(path, iter=None, iterID=None):
    """
    This calls ``ToID()`` first to get the ID and than use ``GetByID()`` to
    take the item.

    In fact we store items by ID, to have fast search by path we also
    keep opposite index. So we need to use second index to get the ID at
    first and than use the main index to get the item.
    """
    path_id = ToID(path, iter=iter)
    if not path_id:
        return None
    return GetByID(path_id, iterID=iterID)


def GetIteratorsByPath(path, iter=None, iterID=None):
    """
    Returns both iterators (iter, iterID) for given path, or None if not found.
    """
    iter_and_id = WalkByPath(path, iter=iter)
    if iter_and_id is None:
        return None
    iter_and_path = WalkByID(iter_and_id[1], iterID=iterID)
    if iter_and_path is None:
        return None
    return iter_and_id[1], iter_and_id[0], iter_and_path[0]


#------------------------------------------------------------------------------


def IsDir(path, iter=None):
    """
    Use ``WalkByPath()`` to check if the item with that ``path`` is directory.
    """
    iter_and_id = WalkByPath(path, iter=iter)
    if iter_and_id is None:
        return False
    iter, pathid = iter_and_id
    if pathid == '':
        return True
    if not isinstance(iter, dict):
        return False
    if 0 not in iter:
        raise Exception('directory ID missed in the index')
    return True


def IsFile(path, iter=None):
    """
    Same, but return True if this is a file.
    """
    iter_and_id = WalkByPath(path, iter=iter)
    if iter_and_id is None:
        return False
    iter, pathid = iter_and_id
    if isinstance(iter, int):
        return True
    if path in iter and isinstance(iter[path], int):
        return True
    return False


def IsDirID(pathID, iterID=None):
    """
    Return True if item with that ID is folder.
    """
    iter_and_path = WalkByID(pathID, iterID=iterID)
    if iter_and_path is None:
        return False
    iterID, path = iter_and_path
    if isinstance(iterID, FSItemInfo):
        return False
    if INFO_KEY not in iterID:
        raise Exception('directory info missed in the index')
    return True


def IsFileID(pathID, iterID=None):
    """
    Return True if item with that ID is a file.
    """
    iter_and_path = WalkByID(pathID, iterID=iterID)
    if iter_and_path is None:
        return False
    iterID, path = iter_and_path
    if not isinstance(iterID, FSItemInfo):
        return False
    return True


def Exists(path, iter=None):
    """
    Use ``WalkByPath()`` to check existence if that ``path``.
    """
    iter_and_id = WalkByPath(path, iter=iter)
    if iter_and_id is None:
        return False
    return True


def ExistsID(pathID, iterID=None):
    """
    Use ``WalkByPath()`` to check existence if that ``ID`` in the catalog.
    """
    iter_and_path = WalkByID(pathID, iterID=iterID)
    if iter_and_path is None:
        return False
    return True


def ExistsBackupID(backupID, iterID=None):
    """
    Return True if backup with that ``backupID`` exist in the index.
    """
    keyAlias, customerGlobalID, remotePath, version = packetid.SplitBackupIDFull(backupID)
    if not remotePath:
        return False
    if iterID is None:
        iterID = fsID(global_id.GlobalUserToIDURL(customerGlobalID), keyAlias)
    iter_and_path = WalkByID(remotePath, iterID=iterID)
    if iter_and_path is None:
        return False
    return iter_and_path[0].has_version(version)


#------------------------------------------------------------------------------


def HasChilds(path, iter=None):
    """
    Return True if that item has some childs in the index.
    """
    if iter is None:
        iter = fs()
    if not path or path == '/':
        return len(iter) > 0
    iter_and_id = WalkByPath(path, iter=iter)
    if iter_and_id is None:
        return False
    iter, _ = iter_and_id
    if not isinstance(iter, dict):
        return False
    if 0 not in iter:
        raise Exception('directory ID missed in the index')
    return len(iter) > 0


def HasChildsID(pathID, iterID=None):
    """
    Same, but access to item by its ID.
    """
    if iterID is None:
        iterID = fsID()
    if not pathID:
        return len(iterID) > 0
    iter_and_path = WalkByID(pathID, iterID=iterID)
    if iter_and_path is None:
        return False
    iterID, _ = iter_and_path
    if not isinstance(iterID, dict):
        return False
    if INFO_KEY not in iterID:
        raise Exception('directory info missed in the index')
    return len(iterID) > 0


#------------------------------------------------------------------------------


def ResolvePath(head, tail=''):
    """
    Smart join of path locations when read items from catalog.
    """
    if not head or head.strip().lstrip('/') == '':
        return tail.strip().lstrip('/')
    if not tail or tail.strip().lstrip('/') == '':
        return head.strip().lstrip('/') if head else ''
    return head.strip().lstrip('/') + '/' + tail.strip().lstrip('/')


def TraverseByID(callback, iterID=None, base_path_id=''):
    """
    Calls method ``callback(path_id, path, info)`` for every item in the index.
    """
    if iterID is None:
        iterID = fsID()

    def recursive_traverse(i, path_id, path, cb):
        name = None
        if path not in ['', '/']:
            path += '/'
        if isinstance(i, FSItemInfo):
            cb(path_id, ResolvePath(path), i)
            return
        if INFO_KEY in i:
            name = i[INFO_KEY].name()
            path += name
            cb(path_id, ResolvePath(path), i[INFO_KEY])
        for id in i.keys():
            if id == INFO_KEY:
                continue
            if isinstance(i[id], dict):
                recursive_traverse(i[id], path_id + '/' + str(id) if path_id else str(id), path, cb)
            elif isinstance(i[id], FSItemInfo):
                cb(
                    (path_id + '/' + str(id)).lstrip('/') if path_id else str(id),  # pathID
                    ResolvePath(path, i[id].name()),  # remotePath
                    i[id],  # item
                )
            else:
                raise Exception('wrong item of type %r in the index: %r' % (type(i[id]), i[id]))

    startpth = '' if bpio.Windows() else '/'
    recursive_traverse(iterID, base_path_id, startpth, callback)


def TraverseByIDSorted(callback, iterID=None):
    """
    Same but sort file and folder names before traversing child nodes.
    """
    if iterID is None:
        iterID = fsID()

    def recursive_traverse_sorted(i, path_id, path, cb):
        name = None
        if path not in ['', '/']:
            path += '/'
        if isinstance(i, FSItemInfo):
            cb(path_id, ResolvePath(path), i, False)
            return
        if INFO_KEY in i:
            name = i[INFO_KEY].name()
            path += name
            cb(path_id, ResolvePath(path), i[INFO_KEY], len(i) > 1)
        dirs = []
        files = []
        for id in i.keys():
            if id == INFO_KEY:
                continue
            if isinstance(i[id], dict):
                dirs.append((id, ResolvePath(path, i[id][INFO_KEY].name())))
            elif isinstance(i[id], FSItemInfo):
                files.append((id, ResolvePath(path, i[id].name())))
            else:
                raise Exception('wrong item type in the index')
        dirs.sort(key=lambda e: e[1])
        files.sort(key=lambda e: e[1])
        for id, pth in dirs:
            recursive_traverse_sorted(i[id], (path_id + '/' + str(id)).lstrip('/') if path_id else str(id), path, cb)
        for id, pth in files:
            cb((path_id + '/' + str(id)).lstrip('/') if path_id else str(id), ResolvePath(pth), i[id], False)
        del dirs
        del files

    startpth = '' if bpio.Windows() else '/'
    recursive_traverse_sorted(iterID, '', startpth, callback)


def TraverseChildsByID(callback, iterID=None):
    if iterID is None:
        iterID = fsID()

    def list_traverse(i, path_id, path, cb):
        name = None
        if path not in ['', '/']:
            path += '/'
        if isinstance(i, FSItemInfo):
            return
        if INFO_KEY in i:
            info = i[INFO_KEY]
            name = info.name()
            path += name
        dirs = []
        files = []
        for id in i.keys():
            if id == INFO_KEY:
                continue
            if isinstance(i[id], dict):
                item_name = i[id][INFO_KEY].name()
                dirs.append((id, item_name, len(i[id]) - 1))
            elif isinstance(i[id], FSItemInfo):
                item_name = i[id].name()
                files.append((id, item_name))
            else:
                raise Exception('wrong item type in the index')
        dirs.sort(key=lambda e: e[1])
        files.sort(key=lambda e: e[1])
        for id, pth, num_childs in dirs:
            cb(DIR, ResolvePath(pth), (path_id + '/' + str(id)).lstrip('/') if path_id else str(id), i[id][INFO_KEY], num_childs)
        for id, pth in files:
            cb(FILE, ResolvePath(pth), (path_id + '/' + str(id)).lstrip('/') if path_id else str(id), i[id], False)
        del dirs
        del files

    startpth = '' if bpio.Windows() else '/'
    list_traverse(iterID, '', startpth, callback)


def IterateIDs(iterID=None):
    if iterID is None:
        iterID = fsID()

    def recursive_iterate(i, path_id, path):
        name = None
        if path not in ['', '/']:
            path += '/'
        if INFO_KEY in i:
            name = i[INFO_KEY].name()
            path += name
            yield path_id, ResolvePath(path), i[INFO_KEY]
        for id in i.keys():
            if id == INFO_KEY:
                continue
            if isinstance(i[id], dict):
                for t in recursive_iterate(i[id], (path_id + '/' + str(id)).lstrip('/') if path_id else str(id), path):
                    yield t
            elif isinstance(i[id], FSItemInfo):
                yield (
                    (path_id + '/' + str(id)).lstrip('/') if path_id else str(id),  # pathID
                    ResolvePath(path, i[id].name()),  # remotePath
                    i[id],  # item
                )
            else:
                raise Exception('wrong item type in the index')

    startpth = '' if bpio.Windows() else '/'
    return recursive_iterate(iterID, '', startpth)


#------------------------------------------------------------------------------


def ExtractVersions(pathID, item_info, path_exist=None, customer_id=None, backup_info_callback=None):
    if not customer_id:
        customer_id = item_info.key_id or my_id.getGlobalID(key_alias='master')
    item_size = 0
    item_time = 0
    versions = []
    for version, version_info in item_info.versions.items():
        backupID = packetid.MakeBackupID(customer_id, pathID, version)
        version_time = misc.TimeFromBackupID(version)
        if version_time and version_time > item_time:
            item_time = version_time
        version_size = version_info[1]
        if version_size > 0:
            item_size += version_size
        if packetid.IsCanonicalVersion(version):
            # 0 1234 56 78 9  11 13 15
            # F 2013 11 20 05 38 03 PM
            b = version
            version_label = '%s-%s-%s %s:%s:%s %s' % (
                b[1:5],
                b[5:7],
                b[7:9],
                b[9:11],
                b[11:13],
                b[13:15],
                b[15:17],
            )
        else:
            version_label = backupID
        backup_info_dict = {
            'backup_id': backupID,
            'label': version_label,
            'time': version_time,
            'size': version_size,
        }
        if backup_info_callback:
            backup_info_dict.update(backup_info_callback(backupID, item_info, item_info.name(), path_exist))
        versions.append(backup_info_dict)
    item_time = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(item_time)) if item_time else ''
    return item_size, item_time, versions


#------------------------------------------------------------------------------


def ListAllBackupIDs(customer_idurl=None, sorted=False, reverse=False):
    """
    Traverse all index and list all backup IDs for all of the customers.
    """
    lst = []

    def visitor(path_id, _, info):
        for version in info.list_versions(sorted, reverse):
            lst.append(packetid.MakeBackupID(info.key_id, path_id.lstrip('/'), version))

    if customer_idurl is None:
        for customer_idurl in known_customers():
            for key_alias in known_keys_aliases(customer_idurl):
                TraverseByID(visitor, iterID=fsID(customer_idurl, key_alias))
    else:
        for key_alias in known_keys_aliases(customer_idurl):
            TraverseByID(visitor, iterID=fsID(customer_idurl, key_alias))
    return lst


def ListAllBackupIDsFull(sorted=False, reverse=False, iterID=None, base_path_id=None):
    """
    Same, but also return items info.
    """
    if iterID is None:
        iterID = fsID()
    if base_path_id is None:
        if INFO_KEY in iterID:
            base_path_id = iterID[INFO_KEY].path_id
    lst = []

    def visitor(path_id, path, info):
        for version in info.list_versions(sorted=sorted, reverse=reverse):
            backupID = packetid.MakeBackupID(info.key_id, path_id.lstrip('/'), version)
            lst.append((info.name(), backupID, info.get_version_info(version), ResolvePath(path), info))

    TraverseByID(visitor, iterID=iterID, base_path_id=base_path_id)
    return lst


def ListChildsByPath(path, recursive=False, iter=None, iterID=None, backup_info_callback=None):
    """
    List all items at given ``path`` and return data as a list of dict objects.
    Return string with error message if operation failed.
    """
    if iter is None:
        iter = fs()
    if iterID is None:
        iterID = fsID()
    if path == '/':
        path = ''
    path = bpio.remotePath(path)
    iter_and_id = WalkByPath(path, iter=iter)
    if iter_and_id is None:
        return 'path "%s" not found' % path
    iter, pathID = iter_and_id
    iter_and_path = WalkByID(pathID, iterID=iterID)
    if iter_and_path is None:
        return 'item "%s" exist, but not path "%s" not found, catalog index is not consistent' % (pathID, path)
    iterID, path_exist = iter_and_path
    if path != path_exist:
        return 'item "%s" exist, but path "%s" is not valid, catalog index is not consistent' % (path_exist, path)
    if isinstance(iterID, FSItemInfo):
        return 'path "%s" is a file' % path
    result = []
    sub_dirs = []

    def visitor(item_type, item_name, item_path_id, item_info, num_childs):
        item_id = (pathID + '/' + item_path_id).strip('/')
        item_size, item_time, versions = ExtractVersions(item_id, item_info, path_exist, backup_info_callback=backup_info_callback)
        i = {
            'type': item_type,
            'name': item_info.name(),
            'path': ResolvePath(path, item_info.name()),
            'path_id': item_id,
            'total_size': item_size,
            'latest': item_time,
            'childs': num_childs,
            'item': item_info.serialize(to_json=True),
            'versions': versions,
        }
        result.append(i)
        if item_type == DIR:
            sub_dirs.append(i)

    TraverseChildsByID(visitor, iterID)

    if recursive:
        for sub_dir in sub_dirs:
            sub_lookup = ListChildsByPath(sub_dir['path'], recursive=False, iter=iter, iterID=iterID, backup_info_callback=backup_info_callback)
            if not isinstance(sub_lookup, list):
                return sub_lookup
            result.extend(sub_lookup)
    return result


#------------------------------------------------------------------------------


def MakeLocalDir(basedir, backupID):
    """
    This creates a local folder for that given ``backupID`` - this is a relative path,
    a ``basedir`` must be a root folder.

    For example::
      MakeLocalDir("c:/temp", "alice@p2p.net:0/1/2/3/F123456")

    should create a folder with such absolute path::
      c:/temp/alice@p2p.net/0/1/2/3/F123456

    Do some checking and call built-in method ``os.makedirs()``.
    """
    if not bpio.pathIsDir(basedir):
        raise Exception('directory not exist: %s' % basedir)
    customerGlobalID, remotePath = packetid.SplitPacketID(backupID)
    if not customerGlobalID:
        customerGlobalID = my_id.getGlobalID()
    path = os.path.join(basedir, customerGlobalID, remotePath)
    if os.path.exists(path):
        if not bpio.pathIsDir(path):
            raise Exception('can not create directory %s' % path)
    else:
        os.makedirs(path)
    return path


def DeleteLocalDir(basedir, pathID):
    """
    Remove local sub folder at given ``basedir`` root path.
    """
    if not bpio.pathIsDir(basedir):
        raise Exception('directory not exist: %s' % basedir)
    customer, pth = packetid.SplitPacketID(pathID)
    path = os.path.join(basedir, customer, pth)
    if not os.path.exists(path):
        return
    if not bpio.pathIsDir(path):
        raise Exception('path %s is not a directory' % path)
    bpio.rmdir_recursive(path, ignore_errors=True)


def DeleteLocalBackup(basedir, backupID):
    """
    Remove local files for that backup.
    """
    count_and_size = [0, 0]
    if not bpio.pathIsDir(basedir):
        raise Exception('directory not exist: %s' % basedir)
    customer, pth = packetid.SplitPacketID(backupID)
    backupDir = os.path.join(basedir, customer, pth)
    if not bpio.pathExist(backupDir):
        return count_and_size[0], count_and_size[1]
    if not bpio.pathIsDir(backupDir):
        raise Exception('path %s is not a directory' % backupDir)

    def visitor(fullpath):
        if os.path.isfile(fullpath):
            try:
                count_and_size[1] += os.path.getsize(fullpath)
                count_and_size[0] += 1
            except:
                pass
        return True

    counter = bpio.rmdir_recursive(backupDir, ignore_errors=True, pre_callback=visitor)
    if _Debug:
        lg.args(_DebugLevel, backupDir=backupDir, counter=counter)
    return count_and_size[0], count_and_size[1]


#------------------------------------------------------------------------------


def Scan(basedir=None, customer_idurl=None, key_alias='master'):
    """
    Walk all items in the index and check if local files and folders with same
    names exists.

    Parameter ``basedir`` is a root path of that structure, default is
    ``lib.settings.getLocalBackupsDir()``. Also calculate size of the
    files.
    """
    if customer_idurl is None:
        customer_idurl = my_id.getIDURL()
    if basedir is None:
        basedir = settings.getLocalBackupsDir()
    iterID = fsID(customer_idurl, key_alias=key_alias)
    summ = [
        0,
        0,
    ]

    def visitor(path_id, path, info):
        info.read_stats(path)
        if info.exist():
            summ[0] += info.size
        k_alias = key_alias
        if info.key_id:
            k_alias = packetid.KeyAlias(info.key_id)
        customer_id = global_id.MakeGlobalID(idurl=customer_idurl, key_alias=k_alias)
        versions_path = bpio.portablePath(os.path.join(basedir, customer_id, path_id))
        summ[1] += info.read_versions(versions_path)

    TraverseByID(visitor, iterID=iterID)
    return summ[0], summ[1]


def ScanID(pathID, basedir=None, customer_idurl=None, key_alias='master'):
    """
    Same as `Scan`, but check only single item in the index.
    """
    if customer_idurl is None:
        customer_idurl = my_id.getIDURL()
    if basedir is None:
        basedir = settings.getLocalBackupsDir()
    iter_and_path = WalkByID(pathID, iterID=fs(customer_idurl, key_alias=key_alias))
    if not iter_and_path:
        return
    itr, path = iter_and_path
    if isinstance(iter, dict):
        if INFO_KEY not in iter:
            return
        itr = iter[INFO_KEY]
    k_alias = key_alias
    if itr and itr.key_id:
        k_alias = packetid.KeyAlias(itr.key_id)
    customer_id = global_id.MakeGlobalID(idurl=customer_idurl, key_alias=k_alias)
    itr.read_stats(path)
    itr.read_versions(bpio.portablePath(os.path.join(basedir, customer_id)))


def Calculate(iterID=None):
    """
    Scan all items in the index and calculate folder and backups sizes.
    """
    global _SizeFiles
    global _SizeFolders
    global _SizeBackups
    global _ItemsCount
    global _FilesCount
    _ItemsCount = 0
    _FilesCount = 0
    _DirsCount = 0
    _SizeFiles = 0
    _SizeFolders = 0
    _SizeBackups = 0

    def recursive_calculate(i):
        global _SizeFiles
        global _SizeFolders
        global _SizeBackups
        global _ItemsCount
        global _FilesCount
        global _DirsCount
        folder_size = 0
        for id in i.keys():
            if id == INFO_KEY:
                continue
            if isinstance(i[id], FSItemInfo):
                if i[id].exist():
                    folder_size += i[id].size
                if i[id].type == FILE:
                    _FilesCount += 1
                    if i[id].exist():
                        _SizeFiles += i[id].size
                if i[id].type == DIR:
                    _DirsCount += 1
                    if i[id].exist():
                        _SizeFolders += i[id].size
                for version in i[id].list_versions():
                    versionSize = i[id].get_version_info(version)[1]
                    if versionSize > 0:
                        _SizeBackups += versionSize
                _ItemsCount += 1
            elif isinstance(i[id], dict):
                sub_folder_size = recursive_calculate(i[id])
                if sub_folder_size != -1:
                    folder_size += sub_folder_size
            else:
                raise Exception('wrong item type in the index')
        if INFO_KEY in i:
            i[INFO_KEY].size = folder_size
            if i[INFO_KEY].type == FILE:
                _FilesCount += 1
                if i[INFO_KEY].exist():
                    _SizeFiles += i[INFO_KEY].size
            if i[INFO_KEY].type == DIR:
                _DirsCount += 1
                if i[INFO_KEY].exist():
                    _SizeFolders += i[INFO_KEY].size
            for version in i[INFO_KEY].list_versions():
                versionSize = i[INFO_KEY].get_version_info(version)[1]
                if versionSize > 0:
                    _SizeBackups += versionSize
            _ItemsCount += 1
        return folder_size

    if iterID is None:
        iterID = fsID()
    ret = recursive_calculate(iterID)
    if _Debug:
        lg.out(_DebugLevel, 'backup_fs.Calculate %d %d %d %d' % (_ItemsCount, _FilesCount, _SizeFiles, _SizeBackups))
    return ret


#------------------------------------------------------------------------------


def Clear(customer_idurl, key_alias=None):
    """
    Erase all items in the index for given customer and key alias and also forget the latest revision.
    """
    fs(customer_idurl, key_alias).clear()
    fsID(customer_idurl, key_alias).clear()
    # forget(customer_idurl, key_alias)


def ClearAllIndexes():
    global _FileSystemIndexByID
    global _FileSystemIndexByName
    global _RevisionNumber
    _FileSystemIndexByID.clear()
    _FileSystemIndexByName.clear()
    _RevisionNumber.clear()


#------------------------------------------------------------------------------


def SerializeIndex(customer_idurl, key_alias=None, encoding='utf-8', filter_cb=None):
    """
    Use this to write index to the local file.
    """
    cnt = [0]
    result = {}

    def cb(path_id, path, info, k_alias):
        if filter_cb is not None:
            if not filter_cb(path_id, path, info):
                return
        result[k_alias]['items'].append(info.serialize(encoding=encoding, to_json=True))
        cnt[0] += 1

    key_aliases = []
    if key_alias:
        key_aliases.append(key_alias)
    else:
        key_aliases.extend(known_keys_aliases(customer_idurl))
    for k_alias in key_aliases:
        if k_alias not in result:
            result[k_alias] = {}
        if 'items' not in result[k_alias]:
            result[k_alias]['items'] = []
        TraverseByID(
            callback=lambda path_id, path, info: cb(path_id, path, info, k_alias),
            iterID=fsID(customer_idurl, k_alias),
        )
    if _Debug:
        lg.dbg(_DebugLevel, 'done with %d indexed files of %d aliases for %r' % (cnt[0], len(key_aliases), customer_idurl))
    return result


def UnserializeIndex(json_data, customer_idurl=None, new_revision=None, deleted_path_ids=[], decoding='utf-8'):
    """
    Read index from ``StringIO`` object.
    """
    if customer_idurl is None:
        customer_idurl = my_id.getIDURL()
    customer_idurl = id_url.field(customer_idurl)
    total_count = 0
    total_modified_count = 0
    updated_keys = []
    for key_alias in json_data.keys():
        if new_revision is not None:
            cur_revision = revision(customer_idurl, key_alias)
            if cur_revision >= new_revision:
                if _Debug:
                    lg.dbg(_DebugLevel, 'ignore items for %r with alias %r because current revision is up to date: %d >= %d' % (customer_idurl, key_alias, cur_revision, new_revision))
                continue
        count = 0
        count_modified = 0
        modified_items = set()
        known_items = set()
        new_files = []
        to_be_removed_items = set()
        to_be_removed_items.update(deleted_path_ids)
        for json_item in json_data[key_alias]['items']:
            item = FSItemInfo()
            item.unserialize(json_item, decoding=decoding, from_json=True)
            if item.path_id in deleted_path_ids:
                continue
            known_items.add(item.path_id)
            if item.type == FILE:
                success, modified = SetFile(item, customer_idurl=customer_idurl)
                if not success:
                    lg.warn('Can not put FILE item into the tree: %s' % str(item))
                    raise ValueError('Can not put FILE item into the tree: %s' % str(item))
                count += 1
                if modified:
                    count_modified += 1
                    modified_items.add(item.path_id)
                    new_files.append(item)
            elif item.type == DIR:
                success, modified = SetDir(item, customer_idurl=customer_idurl)
                if not success:
                    lg.warn('Can not put DIR item into the tree: %s' % str(item))
                    raise ValueError('Can not put DIR item into the tree: %s' % str(item))
                count += 1
                if modified:
                    count_modified += 1
                    modified_items.add(item.path_id)
            else:
                raise ValueError('Incorrect entry type')

        if _Debug:
            lg.args(_DebugLevel, c=customer_idurl, k=key_alias, new_files=len(new_files))

        def _one_item(path_id, path, info):
            if path_id not in known_items:
                if path_id != settings.BackupIndexFileName():
                    to_be_removed_items.add(path_id)

        TraverseByID(_one_item, iterID=fsID(customer_idurl, key_alias))
        if _Debug:
            lg.dbg(_DebugLevel, 'from %d known items %d were modified and %d items marked to be removed' % (len(known_items), len(modified_items), len(to_be_removed_items)))
        for path_id in to_be_removed_items:
            deleted_info = {}
            if key_alias.startswith('share_'):
                deleted_iter_and_path = WalkByID(path_id, iterID=fsID(customer_idurl, key_alias))
                if deleted_iter_and_path:
                    deleted_file_item, deleted_file_path = deleted_iter_and_path
                    full_glob_id = global_id.MakeGlobalID(idurl=customer_idurl, path=path_id, key_alias=key_alias)
                    full_remote_path = global_id.MakeGlobalID(idurl=customer_idurl, path=deleted_file_path, key_alias=key_alias)
                    deleted_info = dict(
                        global_id=full_glob_id,
                        remote_path=full_remote_path,
                        size=max(0, deleted_file_item.size),
                        type=TYPES.get(deleted_file_item.type, 'unknown').lower(),
                        customer=customer_idurl.to_id(),
                        versions=[dict(backup_id=v) for v in deleted_file_item.versions.keys()],
                    )
            DeleteByID(path_id, iter=fs(customer_idurl, key_alias), iterID=fsID(customer_idurl, key_alias))
            count_modified += 1
            if deleted_info:
                snapshot = dict(
                    global_id=deleted_info['global_id'],
                    remote_path=deleted_info['remote_path'],
                    size=deleted_info['size'],
                    type=deleted_info['type'],
                    customer=deleted_info['customer'],
                    versions=deleted_info['versions'],
                )
                listeners.push_snapshot('shared_file', snap_id=full_glob_id, deleted=True, data=snapshot)
            if driver.is_on('service_shared_data'):
                from bitdust.access import shared_access_coordinator
                shared_access_coordinator.on_file_deleted(customer_idurl, key_alias, path_id)

        total_count += count
        total_modified_count += count_modified
        if new_revision is not None and new_revision > cur_revision:
            old_rev = None
            new_rev = None
            old_rev, new_rev = commit(new_revision_number=new_revision, customer_idurl=customer_idurl, key_alias=key_alias)
            Scan(customer_idurl=customer_idurl, key_alias=key_alias)
            updated_keys.append(key_alias)
            if key_alias.startswith('share_'):
                for new_file_item in new_files:
                    if new_file_item.path_id == settings.BackupIndexFileName():
                        continue
                    new_file_path = ToPath(new_file_item.path_id, iterID=fsID(customer_idurl, key_alias))
                    if new_file_path:
                        full_glob_id = global_id.MakeGlobalID(idurl=customer_idurl, path=new_file_item.path_id, key_alias=key_alias)
                        full_remote_path = global_id.MakeGlobalID(idurl=customer_idurl, path=new_file_path, key_alias=key_alias)
                        snapshot = dict(
                            global_id=full_glob_id,
                            remote_path=full_remote_path,
                            size=max(0, new_file_item.size),
                            type=TYPES.get(new_file_item.type, 'unknown').lower(),
                            customer=customer_idurl.to_id(),
                            versions=[dict(backup_id=v) for v in new_file_item.versions.keys()],
                        )
                        listeners.push_snapshot('shared_file', snap_id=full_glob_id, data=snapshot)
            if _Debug:
                lg.args(_DebugLevel, count=count, modified=count_modified, c=customer_idurl, k=key_alias, old_rev=old_rev, new_rev=new_rev)
    if _Debug:
        lg.dbg(_DebugLevel, 'done with %d total items and %d modified, loaded data for %d keys' % (total_count, total_modified_count, len(updated_keys)))
    return total_count, total_modified_count, updated_keys


#------------------------------------------------------------------------------


def SaveIndex(customer_idurl=None, key_alias='master', encoding='utf-8'):
    if customer_idurl is None:
        customer_idurl = my_id.getIDURL()
    customer_idurl = id_url.field(customer_idurl)
    customer_id = customer_idurl.to_id()
    index_file_path = settings.BackupIndexFilePath(customer_idurl, key_alias)
    if not os.path.isdir(os.path.dirname(index_file_path)):
        os.makedirs(os.path.dirname(index_file_path))
    json_data = {}
    json_data[customer_id] = SerializeIndex(
        customer_idurl=customer_idurl,
        key_alias=key_alias,
        encoding=encoding,
    )
    rev = revision(customer_idurl, key_alias)
    src = '%d\n' % rev
    src += jsn.dumps(
        json_data,
        indent=1,
        separators=(',', ':'),
        encoding=encoding,
    )
    if _Debug:
        lg.args(_DebugLevel, rev=rev, c=customer_id, k=key_alias, sz=len(src), path=index_file_path)
    return bpio.WriteTextFile(index_file_path, src)


def ReadIndex(text_data, new_revision=None, deleted_path_ids=[], encoding='utf-8'):
    total_count = 0
    total_modified_count = 0
    updated_customers_keys = []
    try:
        json_data = jsn.loads(text_data, encoding=encoding)
    except:
        lg.exc()
        return 0, []
    if _Debug:
        lg.args(_DebugLevel, new_revision=new_revision, sz=len(text_data), deleted=deleted_path_ids)
    if not json_data:
        return 0, []
    for customer_id in json_data.keys():
        customer_idurl = global_id.GlobalUserToIDURL(customer_id)
        if not id_url.is_cached(customer_idurl):
            lg.warn('identity %r is not yet cached, skip reading related catalog items' % customer_idurl)
            identitycache.immediatelyCaching(customer_idurl, try_other_sources=False, ignore_errors=True)
            continue
        try:
            count, modified_count, updated_keys = UnserializeIndex(
                json_data[customer_id],
                customer_idurl=customer_idurl,
                new_revision=new_revision,
                deleted_path_ids=deleted_path_ids,
                decoding=encoding,
            )
        except:
            lg.exc()
            continue
        total_count += count
        total_modified_count += modified_count
        if updated_keys:
            for key_alias in updated_keys:
                Calculate(iterID=fsID(customer_idurl, key_alias))
                updated_customers_keys.append((customer_idurl, key_alias))
    if _Debug:
        lg.out(_DebugLevel, 'backup_fs.ReadIndex %d items loaded for %d keys' % (total_count, len(updated_customers_keys)))
    return total_count, updated_customers_keys


def LoadIndex(index_file_path):
    src = bpio.ReadTextFile(index_file_path)
    if not src:
        lg.err('failed reading file %s' % index_file_path)
        return False
    inpt = StringIO(src)
    try:
        new_revision = int(inpt.readline().rstrip('\n'))
    except:
        lg.exc()
        return False
    raw_data = inpt.read()
    inpt.close()
    count, _ = ReadIndex(raw_data, new_revision=new_revision)
    if not count:
        return False
    return count


def LoadAllIndexes():
    index_dir_path = os.path.join(settings.ServiceDir('service_backups'), 'index')
    if not os.path.isdir(index_dir_path):
        os.makedirs(index_dir_path)
    for key_id in os.listdir(index_dir_path):
        if my_keys.latest_key_id(key_id) != key_id:
            lg.warn('ignore old index file for rotated identity: %r' % key_id)
            continue
        index_file_path = os.path.join(index_dir_path, key_id)
        LoadIndex(index_file_path)


#------------------------------------------------------------------------------


def populate_private_files():
    ret = api.files_list(remote_path='', key_id=my_id.getGlobalID(key_alias='master'))
    if ret['status'] != 'OK':
        return
    lst = ret['result']
    for itm in lst:
        if itm['path'] == 'index':
            continue
        snapshot = dict(
            global_id=itm['global_id'],
            remote_path=itm['remote_path'],
            size=itm['size'],
            type=itm['type'],
            customer=itm['customer'],
            versions=[dict(backup_id=v['backup_id'].split('/')[-1]) for v in itm['versions']],
        )
        listeners.push_snapshot('private_file', snap_id=itm['global_id'], data=snapshot)


def populate_shared_files(key_id=None):
    lst = []
    if key_id:
        ret = api.files_list(remote_path='', key_id=key_id)
        if ret['status'] != 'OK':
            return
        lst = ret['result']
    else:
        ret = api.shares_list()
        if ret['status'] != 'OK':
            return
        for one_share in ret['result']:
            ret = api.files_list(remote_path='', key_id=one_share['key_id'])
            if ret['status'] != 'OK':
                return
            lst.extend(ret['result'])
    for itm in lst:
        if itm['path'] == 'index':
            continue
        snapshot = dict(
            global_id=itm['global_id'],
            remote_path=itm['remote_path'],
            size=itm['size'],
            type=itm['type'],
            customer=itm['customer'],
            versions=[dict(backup_id=v['backup_id'].split('/')[-1]) for v in itm['versions']],
        )
        listeners.push_snapshot('shared_file', snap_id=itm['global_id'], data=snapshot)


#------------------------------------------------------------------------------


def _test():
    """
    For tests.
    """
    import pprint
    settings.init()
    filepath = settings.BackupIndexFilePath()
    # print filepath
    src = bpio.ReadTextFile(filepath)
    inpt = StringIO(src)
    inpt.readline()
    json_data = json.loads(inpt.read())
    inpt.close()
    for customer_id in json_data.keys():
        count, modified_count, updated_keys = UnserializeIndex(json_data[customer_id])
        print(customer_id, count)
    Scan()
    Calculate()

    # pprint.pprint(fs())
    # print
    # pprint.pprint(fsID())
    # print

    #     print AddDir('dir1/dir2')
    #     ii = GetIteratorsByPath('dir1')
    #     print ii
    #     print PutItem('fff', as_folder=False, iter=ii[0], iterID=ii[1])
    #
    #     print IsDir('dir1')
    #     print IsFile('dir2/fff')

    print('------------')
    pprint.pprint(fs(key_alias='share_f17b49966dfe85320ac5e7d579d0047c'))
    pprint.pprint(ListChildsByPath(
        path='',
        recursive=True,
        iter=fs(key_alias='share_f17b49966dfe85320ac5e7d579d0047c'),
        iterID=fsID(key_alias='share_f17b49966dfe85320ac5e7d579d0047c'),
    ))
    # print()
    # pprint.pprint(fsID())
    print('------------')

    # print(HasChilds('', iter=fs(customer_idurl)))
    # pprint.pprint([i[1] for i in ListAllBackupIDsFull()])
    # pprint.pprint([i[1] for i in ListAllBackupIDsFull(iterID=WalkByID('0')[0])])

    settings.shutdown()


#     for i in range(10000):
#         r = AddFile('file' + str(i))
#         print r[0], len(fs())
#         # pprint.pprint(fs())

# PutItem('dir4', as_folder=True)

#     print ListByPathAdvanced('TestKey2')
#     return

#     for i in ListByPathAdvanced('TestKey2'):
#         print i # , i[1] # , WalkByPath(i[1])[1]
#         print

#     parent_path = os.path.dirname(bpio.portablePath(unicode('/some/remote/path')))
#     print IsFile(sys.argv[1])
#     if iter_and_iterID is None:
#         _, parent_iter, parent_iterID = AddDir(parent_path, read_stats=False)
#     else:
#         parent_iter, parent_iterID = iter_and_iterID
#     print MapPath('/tmp/com.apple.launchd.KlOCuOQw9M', iter=parent_iter, iterID=parent_iterID)

#     print AddDir('/this/folder/not/exist/', read_stats=True, keyID='KKKKKKK')
#     print AddDir('/this/folder/not/exist/subdir')

#     pprint.pprint(fs())
#     pprint.pprint(fsID())

# print GetByPath('')

# print WalkByID('8/0/0')

# print AppendFile('new', '/Users/veselin/Pictures')

# item = FSItemInfo('new', '/Users/new', FILE)
# SetFile(item)
# print ToID('dir6/ilhan.jpg')
# print WalkByPath('dir6')

# print Exists('/asd')
# print IsDir('/asd')
# MapPath("/Users/veselin/Pictures/fotosess/Thumbs.db")
# pprint.pprint(fs())
# pprint.pprint(fsID())
# for pathID, localPath, item in IterateIDs():
#     sz = diskspace.MakeStringFromBytes(item.size) if item.exist() else ''
#     print '  %s %s %s' % (pathID.ljust(27), localPath.ljust(70), sz.ljust(9))

# pprint.pprint(ListRootItems())
# pprint.pprint(ListAllBackupIDs())
# pprint.pprint(ListChildsByPath((sys.argv[1])))

# print ListByPathAdvanced("")
# pth = '~/Downloads/test/asd'
# ppth = bpio.portablePath(unicode(pth))
# print ppth
# print ToID(ppth)

#    bpio.init()
#    for path in sys.argv[1:]:
#        print path, AddLocalPath(path, True)
#
#    for pathID, localPath, itemInfo in IterateIDs():
#        print pathID, localPath, itemInfo
#
#    print IsDirID('0/0/0')

# pprint.pprint(fs())
# pprint.pprint(fsID())
# s = Serialize()
# print s
#    open('index', 'w').write(s)
#    for id, path in ListByID(''):
#        pprint.pprint(ListByID(id))
#    fs().clear()
#    fsID().clear()
#    inp = StringIO(s)
#    Unserialize(inp)
#    inp.close()
#    pprint.pprint(fs())
#    pprint.pprint(fsID())

# print GetPath('/0/0/0/1/31/12')
# print GetID('C:/.Veselin/diplom/Social/Editor/type 5.vsd.aut')
# print WalkByPath('C:/.Veselin/diplom/Social/Editor/type 5.vsd.aut')
# print WalkByID('/0/0/0/1/31/12')
# print IsDir('C:')
# DeleteByID('/0')
# print ListByID('')
# print 'NEW C:/.Veselin/diplom/', AddLocalPath('C:/.Veselin/diplom/')
# print ListByID('')
# pprint.pprint(ListByPath('c:\.Veselin/diplom/'))
# print DeleteByID('0/0/0/0')
# print DeleteByPath('C:/.Veselin/diplom/Social')
# pprint.pprint(fs())
# pprint.pprint(ListByPath('C:/.Veselin/diplom/Social/Editor'))

# iter = fs()['c:']['work']['modnamama']['_katalog']
# print map(lambda k: iter[k][0] if isinstance(iter, dict) else '', iter.keys())
# pprint.pprint( ListLocalFolder(sys.argv[1]) )
# print ListLocalFolder(sys.argv[1])

if __name__ == '__main__':
    _test()
