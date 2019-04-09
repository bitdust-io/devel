#!/usr/bin/python
# backup_fs.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
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

from lib import strng

from logs import lg

from system import bpio

from main import settings

from lib import misc
from lib import packetid
from lib import diskspace

from userid import my_id
from userid import global_id

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
_ItemsCount = 0
_FilesCount = 0
_DirsCount = 0
_SizeFiles = 0
_SizeFolders = 0
_SizeBackups = 0

#------------------------------------------------------------------------------


def fs(customer_idurl=None):
    """
    Access method for forward index: [path] -> [ID].
    """
    global _FileSystemIndexByName
    if not customer_idurl:
        customer_idurl = my_id.getLocalID()
    if customer_idurl not in _FileSystemIndexByName:
        _FileSystemIndexByName[customer_idurl] = {}
    return _FileSystemIndexByName[customer_idurl]


def fsID(customer_idurl=None):
    """
    Access method for backward index: [ID] -> [path].
    """
    global _FileSystemIndexByID
    if not customer_idurl:
        customer_idurl = my_id.getLocalID()
    if customer_idurl not in _FileSystemIndexByID:
        _FileSystemIndexByID[customer_idurl] = {}
    return _FileSystemIndexByID[customer_idurl]


def customerIDURLFromRootItem(iter):
    """
    """
    global _FileSystemIndexByName
    for customerIDURL, rootIter in _FileSystemIndexByName.items():
        if rootIter == iter:
            return customerIDURL
    return None


def customerIDURLFromRootItemID(iterID):
    """
    """
    global _FileSystemIndexByID
    for customerIDURL, rootIterID in _FileSystemIndexByID.items():
        if rootIterID == iterID:
            return customerIDURL
    return None


def known_customers():
    """
    """
    global _FileSystemIndexByID
    return list(_FileSystemIndexByID.keys())


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


def init():
    """
    Some initial steps can be done here.
    """
    lg.out(4, 'backup_fs.init')
    # fn_index = settings.BackupIndexFileName()
    # fs()[fn_index] = settings.BackupIndexFileName()
    # fsID()[fn_index] = FSItemInfo(fn_index, fn_index, FILE)
    # fsID()[fn_index].read_stats(os.path.join(settings.getLocalBackupsDir(), fn_index))
    # SetFile(settings.BackupIndexFileName(), settings.BackupIndexFileName())


def shutdown():
    """
    Should be called when the program is finishing.
    """
    lg.out(4, 'backup_fs.shutdown')

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

    def filename(self):
        return os.path.basename(self.unicodename)

    def name(self):
        return self.unicodename

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
        self.versions[version] = [maxblocknum, sizebytes, ]

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
                } for v in self.list_versions(sorted=True)]
            }
        e = strng.to_text(self.unicodename, encoding=encoding)
        return '%s %d %d %s\n%s\n' % (self.path_id, self.type,
                                      self.size, self.pack_versions(), e,)

    def unserialize(self, src, decoding='utf-8', from_json=False):
        if from_json:
            try:
                self.unicodename = strng.to_text(src['n'], encoding=decoding)
                self.path_id = strng.to_text(src['i'], encoding=decoding)
                self.type = src['t']
                self.size = src['s']
                self.key_id = strng.to_text(src['k'], encoding=decoding)
                self.versions = {
                    strng.to_text(v['n']): [v['b'], v['s'], ] for v in src['v']
                }
            except:
                lg.exc()
                raise KeyError('Incorrect item format:\n%s' % src)
            return True

        try:
            details, name = strng.to_text(src, encoding=decoding).split('\n')[:2]
        except:
            raise Exception('Incorrect item format:\n%s' % src)
        if not details or not name:
            raise Exception('Incorrect item format:\n%s' % src)
        try:
            self.unicodename = name
            details = details.split(' ')
            self.path_id, self.type, self.size = details[:3]
            self.type, self.size = int(self.type), int(self.size)
            self.unpack_versions(' '.join(details[3:]))
        except:
            lg.exc()
            raise KeyError('Incorrect item format:\n%s' % src)
        return True

#------------------------------------------------------------------------------


def MakeID(itr, randomized=True):
    """
    Create a new unique number for the folder to create a index ID.

    Parameter ``itrID`` is a reference for a single item in the ``fs()``.
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
                new_id = int(''.join([v() for v in [lambda: random.choice('0123456789'), ] * digits]))
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
    # if not os.path.isfile(path):
    #     raise Exception('File not exist')
    parts = bpio.remotePath(path).split('/')
    if not iter:
        iter = fs()
    if not iterID:
        iterID = fsID()
    resultID = ''
    parentKeyID = None
    # build all tree, skip the last part
    for i in range(len(parts) - 1):
        name = parts[i]
        if not name:
            continue
        p = '/'.join(parts[:i + 1])
        if bpio.Linux() or bpio.Mac():
            p = '/' + p
        # if not bpio.pathIsDir(p):
        #     raise Exception('Directory not exist: %s' % str(p))
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
    return resultID, iter, iterID


def AddDir(path, read_stats=False, iter=None, iterID=None, key_id=None):
    """
    Add directory to the index, but do not read folder content.

        >>> import backup_fs
        >>> backup_fs.AddDir('C:/Program Files/Adobe/')
        ('0/0/0', {0: 0}, {'i': <DIR Adobe -1>})
        >>> backup_fs.AddDir('C:/Program Files/Google/')
        ('0/0/1', {0: 1}, {'i': <DIR Google -1>})
        >>> backup_fs.AddDir('E:/games/')
        ('1/0', {0: 0}, {'i': <DIR games -1>})
        >>> backup_fs.fs()
        {u'c:': {0: 0, u'Program Files': {0: 0, u'Google': {0: 1}, u'Adobe': {0: 0}}}, u'e:': {0: 1, u'games': {0: 0}}}

    Parameter ``path`` must be in "portable" form.
    """
    parts = bpio.remotePath(path).split('/')
    if not iter:
        iter = fs()
    if not iterID:
        iterID = fsID()
    resultID = ''
    parentKeyID = None
    for i in range(len(parts)):
        name = parts[i]
        if not name:
            continue
        p = '/'.join(parts[:i + 1])
        if bpio.Linux() or bpio.Mac():
            p = '/' + p
        # if not bpio.pathIsDir(p):
        #     raise Exception('Directory not exist: %s' % str(p))
        if name not in iter:
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
    return resultID.lstrip('/'), iter, iterID


def AddLocalPath(localpath, read_stats=False, iter=None, iterID=None, key_id=None):
    """
    Operate like ``AddDir()`` but also recursively reads the entire folder and
    put all items in the index. Parameter ``localpath`` can be a file or folder
    path in "portable" form.

        >>> import backup_fs
        >>> i = backup_fs.AddLocalPath('C:/Program Files/7-Zip/')
        >>> import pprint
        >>> pprint.pprint(backup_fs.fs())
        {u'c:': {0: 0,
                 u'Program Files': {0: 0,
                                    u'7-Zip': {0: 0,
                                               u'7-zip.chm': 0,
                                               u'7-zip.dll': 1,
                                               u'7z.dll': 2,
                                               u'7z.exe': 3,
                                               u'7z.sfx': 4,
                                               u'7zCon.sfx': 5,
                                               u'7zFM.exe': 6,
                                               u'7zG.exe': 7,
                                               u'7zip_pad.xml': 8,
                                               u'Lang': {0: 10,
                                                         u'en.ttt': 0,
                                                         u'ru.txt': 1},
                                               u'Uninstall.exe': 11,
                                               u'descript.ion': 9}}}}
    """
    def recursive_read_dir(local_path, path_id, iter, iterID):
        c = 0
        lastID = -1
        path = bpio.portablePath(local_path)
        if not os.access(path, os.R_OK):
            return c
        for localname in bpio.list_dir_safe(path):
            p = os.path.join(path, localname)  # .encode("utf-8")
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
        path_id, iter, iterID = AddDir(
            localpath, read_stats=read_stats, iter=iter, iterID=iterID, key_id=key_id)
        num = recursive_read_dir(localpath, path_id, iter, iterID)
        return path_id, iter, iterID, num
    else:
        path_id, iter, iterID = AddFile(
            localpath, read_stats=read_stats, iter=iter, iterID=iterID, keyID=key_id)
        return path_id, iter, iterID, 1
    return None, None, None, 0


def PutItem(name, parent_path_id, as_folder=False, iter=None, iterID=None, key_id=None):
    """
    Acts like AddFile() but do not follow the directory structure. This just
    "bind" some local path (file or dir) to one item in the catalog - by default as a top level item.
    The name of new item will be equal to the local path.
    """
    remote_path = bpio.remotePath(name)
    if not iter:
        iter = fs()
    if not iterID:
        iterID = fsID()
    # make an ID for the filename
    newItemID = MakeID(iter)
    resultID = (parent_path_id.strip('/') + '/' + str(newItemID)).strip('/')
    typ = DIR if as_folder else FILE
    ii = FSItemInfo(name=remote_path, path_id=resultID, typ=typ, key_id=key_id)
    iter[ii.name()] = newItemID
    iterID[newItemID] = ii
    return resultID, iter, iterID

#------------------------------------------------------------------------------


def SetFile(item, iter=None, iterID=None):
    """
    Put existing FSItemInfo ``item`` (for some single file) into the index.

    This is used when loading index from file. Should create all parent
    items in the index.
    """
    if iter is None:
        iter = fs()
    if iterID is None:
        iterID = fsID()
    parts = item.path_id.lstrip('/').split('/')
    for j in range(len(parts)):
        part = parts[j]
        id = misc.ToInt(part, part)
        if j == len(parts) - 1:
            if item.name() not in iter:
                iter[item.name()] = id
                iterID[id] = item
            return True
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
            return False
    return False


def SetDir(item, iter=None, iterID=None):
    """
    Same, but ``item`` is a folder.
    """
    if iter is None:
        iter = fs()
    if iterID is None:
        iterID = fsID()
    parts = item.path_id.lstrip('/').split('/')
    itemname = item.name()
    for j in range(len(parts)):
        part = parts[j]
        id = misc.ToInt(part, part)
        if j == len(parts) - 1:
            if itemname not in iter:
                iter[itemname] = {}
            iter[itemname][0] = int(id)
            if id not in iterID:
                iterID[id] = {}
            iterID[id][INFO_KEY] = item
            return True
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
            raise Exception('Wrong data type in the index')
        if not found:
            return False
    return False

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
                raise Exception('Error, file or directory ID missed in the index')
            path_id += '/' + str(iter[name][0])
        elif isinstance(iter[name], int):
            if j != len(parts) - 1:
                return None
            path_id += '/' + str(iter[name])
        else:
            raise Exception('Wrong data type in the index')
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
                raise Exception('Error, directory info missed in the index')
            name = iterID[id][INFO_KEY].name()
            if bpio.pathIsDriveLetter(name) or bpio.pathIsNetworkLocation(name):
                path += name
            else:
                path += '/' + name
        elif isinstance(iterID[id], FSItemInfo):
            if j != len(parts) - 1:
                return None
            path += '/' + iterID[id].name()
            # (('/' + iterID[id].name()) if ('/' in pathID) else iterID[id].name())
        else:
            raise Exception('Wrong data type in the index')
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
                raise Exception('Error, directory info missed in the index')
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
            raise Exception('Wrong data type in the index')
        if name not in iter:
            raise Exception('Can not found target name in the index')
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
        name = parts[j]  # .encode('utf-8') # parts[j]
        if name not in iter:
            return None
        if isinstance(iter[name], dict):
            if 0 not in iter[name]:
                raise Exception('Error, directory ID missed in the index')
            id = iter[name][0]
            path_id += '/' + str(id)
        elif isinstance(iter[name], int):
            id = iter[name]
            path_id += '/' + str(id)
            if j != len(parts) - 1:
                return None
        else:
            raise Exception('Wrong data type in the index')
        if id not in iterID:
            raise Exception('Can not found target ID in the index')
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
    customerGlobalID, remotePath, versionName = packetid.SplitBackupID(backupID)
    if not remotePath:
        return False
    if not iterID:
        iterID = fsID(global_id.GlobalUserToIDURL(customerGlobalID))
    info = GetByID(remotePath, iterID=iterID)
    if info is None:
        return False
    if not info.has_version(versionName):
        lg.warn('%s do not have version %s' % (remotePath, versionName))
        return False
    info.delete_version(versionName)
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
        raise Exception('Error, directory ID missed in the index')
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
        raise Exception('Error, directory info missed in the index')
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
    Use ``WalkByPath()`` to check existence if that ``ID``.
    """
    iter_and_path = WalkByID(pathID, iterID=iterID)
    if iter_and_path is None:
        return False
    return True


def ExistsBackupID(backupID, iterID=None):
    """
    Return True if backup with that ``backupID`` exist in the index.
    """
    customerGlobalID, remotePath, version = packetid.SplitBackupID(backupID)
    if not remotePath:
        return False
    if not iterID:
        iterID = fsID(global_id.GlobalUserToIDURL(customerGlobalID))
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
        raise Exception('Error, directory ID missed in the index')
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
        raise Exception('Error, directory info missed in the index')
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


def TraverseByID(callback, iterID=None):
    """
    Calls method ``callback(path_id, path, info)`` for every item in the index.
    """
    if iterID is None:
        iterID = fsID()
#     customer_idurl = customerIDURLFromRootItemID(iterID)
#     customer_id = global_id.UrlToGlobalID(customer_idurl)

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
                    ResolvePath(path, i[id].name()),                                # remotePath
                    i[id],                                                          # item
                )
            else:
                raise Exception('Error, wrong item type in the index')

    startpth = '' if bpio.Windows() else '/'
    recursive_traverse(iterID, '', startpth, callback)


def TraverseByIDSorted(callback, iterID=None):
    """
    Same but sort file and folder names before traversing child nodes.
    """
    if iterID is None:
        iterID = fsID()
#     customer_idurl = customerIDURLFromRootItemID(iterID)
#     customer_id = global_id.UrlToGlobalID(customer_idurl)

    def recursive_traverse(i, path_id, path, cb):
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
                dirs.append((id, ResolvePath(path, i[id][INFO_KEY].name()),))
            elif isinstance(i[id], FSItemInfo):
                files.append((id, ResolvePath(path, i[id].name()),))
            else:
                raise Exception('Error, wrong item type in the index')
        dirs.sort(key=lambda e: e[1])
        files.sort(key=lambda e: e[1])
        for id, pth in dirs:
            recursive_traverse(i[id], (path_id + '/' + str(id)).lstrip('/') if path_id else str(id), path, cb)
        for id, pth in files:
            cb((path_id + '/' + str(id)).lstrip('/') if path_id else str(id), ResolvePath(pth), i[id], False)
        del dirs
        del files

    startpth = '' if bpio.Windows() else '/'
    recursive_traverse(iterID, '', startpth, callback)


def TraverseChildsByID(callback, iterID=None):
    """
    """
    if iterID is None:
        iterID = fsID()
#     customer_idurl = customerIDURLFromRootItemID(iterID)
#     customer_id = global_id.UrlToGlobalID(customer_idurl)

    def list_traverse(i, path_id, path, cb):
        name = None
        if path not in ['', '/']:
            path += '/'
        if isinstance(i, FSItemInfo):
            # cb(i.type, name, path_id, i)
            return
        if INFO_KEY in i:
            info = i[INFO_KEY]
            name = info.name()
            path += name
            # cb(info.type, name, path_id, info)
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
                raise Exception('Error, wrong item type in the index')
        dirs.sort(key=lambda e: e[1])
        files.sort(key=lambda e: e[1])
        for id, pth, num_childs in dirs:
            cb(DIR,
               ResolvePath(pth),
               (path_id + '/' + str(id)).lstrip('/') if path_id else str(id),
               i[id][INFO_KEY],
               num_childs)
        for id, pth in files:
            cb(FILE,
               ResolvePath(pth),
               (path_id + '/' + str(id)).lstrip('/') if path_id else str(id),
               i[id],
               False)
        del dirs
        del files

    startpth = '' if bpio.Windows() else '/'
    list_traverse(iterID, '', startpth, callback)


def IterateIDs(iterID=None):
    """
    You can iterate all index using that method:

        >>> for pathID, localPath, itemInfo in p2p.backup_fs.IterateIDs():
        ...     print pathID, localPath, itemInfo
        ...
        0 c: <PARENT c: -1>
        0/0 c:/Program Files <PARENT Program Files -1>
        0/0/0 c:/Program Files/7-Zip <DIR 7-Zip -1>
        0/0/0/0 c:/Program Files/7-Zip/7-zip.chm <FILE 7-zip.chm -1>
        0/0/0/1 c:/Program Files/7-Zip/7-zip.dll <FILE 7-zip.dll -1>
        0/0/0/2 c:/Program Files/7-Zip/7z.dll <FILE 7z.dll -1>
        0/0/0/3 c:/Program Files/7-Zip/7z.exe <FILE 7z.exe -1>
        0/0/0/4 c:/Program Files/7-Zip/7z.sfx <FILE 7z.sfx -1>
        0/0/0/5 c:/Program Files/7-Zip/7zCon.sfx <FILE 7zCon.sfx -1>
        0/0/0/6 c:/Program Files/7-Zip/7zFM.exe <FILE 7zFM.exe -1>
        0/0/0/7 c:/Program Files/7-Zip/7zG.exe <FILE 7zG.exe -1>
        0/0/0/9 c:/Program Files/7-Zip/descript.ion <FILE descript.ion -1>
        0/0/0/10 c:/Program Files/7-Zip/Lang <DIR Lang -1>
        0/0/0/10/0 c:/Program Files/7-Zip/Lang/en.ttt <FILE en.ttt -1>
        0/0/0/10/1 c:/Program Files/7-Zip/Lang/ru.txt <FILE ru.txt -1>
        0/0/0/11 c:/Program Files/7-Zip/Uninstall.exe <FILE Uninstall.exe -1>
        0/0/0/8 c:/Program Files/7-Zip/7zip_pad.xml <FILE 7zip_pad.xml -1>
    """
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
                    ResolvePath(path, i[id].name()),                                # remotePath
                    i[id],                                                          # item
                )
            else:
                raise Exception('Error, wrong item type in the index')

    startpth = '' if bpio.Windows() else '/'
    return recursive_iterate(iterID, '', startpth)

#------------------------------------------------------------------------------


def GetBackupStatusInfo(backupID, item_info, item_name, parent_path_existed=None):
    from storage import backup_control
    from storage import restore_monitor
    from storage import backup_matrix
    blocks, percent, weakBlock, weakPercent = backup_matrix.GetBackupRemoteStats(backupID)
    totalNumberOfFiles, maxBlockNum, statsArray = backup_matrix.GetBackupStats(backupID)
    ret = {
        'state': 'ready',
        'delivered': misc.percent2string(percent),
        'reliable': misc.percent2string(weakPercent),
        'fragments': totalNumberOfFiles,
        'weak_block': weakBlock,
        'max_block': maxBlockNum,
        'suppliers': [{
            'stored': misc.percent2string(i[0]),
            'fragments': i[1],
        } for i in statsArray],
    }
    if backup_control.IsBackupInProcess(backupID):
        backupObj = backup_control.GetRunningBackupObject(backupID)
        if backupObj:
            ret['state'] = 'uploading'
            ret['progress'] = misc.percent2string(backupObj.progress())
            return ret
    elif restore_monitor.IsWorking(backupID):
        restoreObj = restore_monitor.GetWorkingRestoreObject(backupID)
        if restoreObj:
            maxBlockNum = backup_matrix.GetKnownMaxBlockNum(backupID)
            currentBlock = max(0, restoreObj.block_number)
            percent = 0.0
            if maxBlockNum > 0:
                percent = 100.0 * currentBlock / maxBlockNum
            ret['state'] = 'downloading'
            ret['progress'] = misc.percent2string(percent)
            return ret
    return ret

def ExtractVersions(pathID, item_info, path_exist=None, customer_id=None):
    if not customer_id:
        customer_id = item_info.key_id or my_id.getGlobalID(key_alias='master')
    item_size = 0
    item_time = 0
    # item_status = ''
    versions = []
    for version, version_info in item_info.versions.items():
        backupID = packetid.MakeBackupID(customer_id, pathID, version)
        version_time = misc.TimeFromBackupID(version)
        if version_time and version_time > item_time:
            item_time = version_time
        version_maxblocknum = version_info[0]
        version_size = version_info[1]
        if version_size > 0:
            item_size += version_size
        if packetid.IsCanonicalVersion(version):
            # 0 1234 56 78 9  11 13 15
            # F 2013 11 20 05 38 03 PM
            b = version
            version_label = '%s-%s-%s %s:%s:%s %s' % (
                b[1:5], b[5:7], b[7:9], b[9:11], b[11:13], b[13:15], b[15:17])
        else:
            version_label = backupID
        backup_info_dict = GetBackupStatusInfo(backupID, item_info, item_info.name(), path_exist)
        backup_info_dict.update({
            'backup_id': backupID,
            'label': version_label,
            'time': version_time,
            'size': version_size,
            # 'blocks': version_maxblocknum + 1,
        })
        versions.append(backup_info_dict)
    item_time = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(item_time)) if item_time else ''
    return (item_size, item_time, versions)

#------------------------------------------------------------------------------

def ListRootItems(iter=None, iterID=None):
    """
    """
    if iter is None:
        iter = fs()
    if iterID is None:
        iterID = fsID()
#     customer_idurl = customerIDURLFromRootItemID(iterID)
#     customer_id = global_id.UrlToGlobalID(customer_idurl)
    result = []
    root_items = WalkByPath('', iter=iter)
    for item_id in root_items[0].values():
        item = GetByID(str(item_id), iterID=iterID)
        if item:
            result.append((str(item_id), item.name(), item))
    return result


def ListChilds(iterID):
    """
    """
    lg.out(4, 'backup_fs.ListChilds %s' % (iterID))
    result = []
    if isinstance(iterID, FSItemInfo):
        return [('', '', iterID), ]
    if not isinstance(iterID, dict):
        raise Exception('Wrong data type in the index')
    if INFO_KEY not in iterID:
        raise Exception('Error, directory info missed in the index')
    for id in iterID.keys():
        if id == INFO_KEY:
            continue
        if isinstance(iterID[id], dict):
            if INFO_KEY not in iterID[id]:
                raise Exception('Error, directory info missed in the index')
            name = iterID[id][INFO_KEY].name()
            itm = iterID[id][INFO_KEY]
        elif isinstance(iterID[id], FSItemInfo):
            name = iterID[id].name()
            itm = iterID[id]
        else:
            raise Exception('Wrong data type in the index')
        result.append((str(id), name, itm))
    return result


def ListByID(pathID, iterID=None):
    """
    List sub items in the index at given ``ID``.
    """
    lg.out(4, 'backup_fs.ListByID %s' % (pathID))
    if iterID is None:
        iterID = fsID()
#     customer_idurl = customerIDURLFromRootItemID(iterID)
#     customer_id = global_id.UrlToGlobalID(customer_idurl)
    iter_and_path = WalkByID(pathID, iterID=iterID)
    if iter_and_path is None:
        return None
    result = []
    iterID, path = iter_and_path
    if isinstance(iterID, FSItemInfo):
        return [(pathID, ResolvePath(path), iterID), ]
    if not isinstance(iterID, dict):
        raise Exception('Wrong data type in the index')
    if INFO_KEY not in iterID and pathID.strip() != '':
        raise Exception('Error, directory info missed in the index')
    for id in iterID.keys():
        if id == INFO_KEY:
            continue
        if isinstance(iterID[id], dict):
            if INFO_KEY not in iterID[id]:
                raise Exception('Error, directory info missed in the index')
            name = iterID[id][INFO_KEY].name()
            itm = iterID[id][INFO_KEY]
        elif isinstance(iterID[id], FSItemInfo):
            name = iterID[id].name()
            itm = iterID[id]
        else:
            raise Exception('Wrong data type in the index')
        result.append(((pathID + '/' + str(id)).lstrip('/'), ResolvePath(path, name), itm))
    return result


def ListByPath(path, iter=None):
    """
    List sub items in the index at given ``path``.
    """
    lg.out(4, 'backup_fs.ListByPath %s' % (path))
    if iter is None:
        iter = fs()
#     customer_idurl = customerIDURLFromRootItem(iter)
#     customer_id = global_id.UrlToGlobalID(customer_idurl)
    if path in ['', '/']:
        return ListRootItems()
    path = bpio.remotePath(path)
    iter_and_id = WalkByPath(path, iter=iter)
    if iter_and_id is None:
        return None
    result = []
    iter, path_id = iter_and_id
    if isinstance(iter, int):
        return [(path_id, ResolvePath(path), None), ]
    if not isinstance(iter, dict):
        raise Exception('Wrong data type in the index')
    if 0 not in iter:
        raise Exception('Error, directory ID missed in the index')
    for key in iter.keys():
        if key == 0:
            continue
        if isinstance(iter[key], dict):
            if 0 not in iter[key]:
                raise Exception('Error, directory ID missed in the index')
            id = iter[key][0]
        elif isinstance(iter[key], int):
            id = iter[key]
        else:
            raise Exception('Wrong data type in the index')
        result.append(((path_id + '/' + str(id)).lstrip('/'), ResolvePath(path, key)))
    return result


def ListAllBackupIDs(sorted=False, reverse=False, iterID=None):
    """
    Traverse all index and list all backup IDs.
    """
    if iterID is None:
        iterID = fsID()
    # customer_idurl = customerIDURLFromRootItemID(iterID)
    # customer_id = global_id.UrlToGlobalID(customer_idurl)
    lst = []

    def visitor(path_id, _, info):
        for version in info.list_versions(sorted, reverse):
            lst.append(packetid.MakeBackupID(info.key_id, path_id.lstrip('/'), version))

    TraverseByID(visitor, iterID=iterID)
    return lst


def ListAllBackupIDsFull(sorted=False, reverse=False, iterID=None):
    """
    Same, but also return items info.
    """
    if iterID is None:
        iterID = fsID()
    # customer_idurl = customerIDURLFromRootItemID(iterID)
    # customer_id = global_id.UrlToGlobalID(customer_idurl)
    lst = []

    def visitor(path_id, path, info):
        for version in info.list_versions(sorted=sorted, reverse=reverse):
            backupID = packetid.MakeBackupID(info.key_id, path_id.lstrip('/'), version)
            lst.append((info.name(), backupID, info.get_version_info(version), ResolvePath(path), info))

    TraverseByID(visitor, iterID=iterID)
    return lst


def ListSelectedFolders(selected_dirs_ids, sorted=False, reverse=False, iterID=None):
    """
    List items from index only if they are sub items of ``selected_dirs_ids``
    list.
    """
    if iterID is None:
        iterID = fsID()
    # customer_idurl = customerIDURLFromRootItemID(iterID)
    # customer_id = global_id.UrlToGlobalID(customer_idurl)
    lst = []

    def visitor(path_id, path, info, num_childs):
        basepathid = path_id[:path_id.rfind('/')] if path_id.count('/') else ''
        if basepathid in selected_dirs_ids:
            lst.append((info.type, path_id, ResolvePath(path), info.size, info.list_versions(sorted, reverse)))
        return True

    TraverseByIDSorted(visitor, iterID=iterID)
    return lst


def ListExpandedFoldersAndBackups(expanded_dirs, selected_items, iterID=None):
    """
    Another advanced method to list items from index.
    """
    lst = []
    backups = []

    def visitor(path_id, path, info, num_childs):
        basepathid = path_id[:path_id.rfind('/')] if path_id.count('/') else ''
        if basepathid in expanded_dirs:
            lst.append((info.type, path_id, ResolvePath(path), info.size, info.get_versions()))
        if path_id in selected_items:
            for version in info.list_versions():
                backups.append((path_id + '/' + version).lstrip('/'))
        return True

    TraverseByIDSorted(visitor, iterID=iterID)
    return lst, backups


def ListChildsByPath(path, recursive=False, iter=None, iterID=None):
    """
    List all items at given ``path`` and return data as a list of dict objects.
    Return string with error message if operation failed.
    """
    if iter is None:
        iter = fs()
    if iterID is None:
        iterID = fsID()
    # customer_idurl = customerIDURLFromRootItem(iter)
    # customer_id = global_id.UrlToGlobalID(customer_idurl)
    if path == '/':
        path = ''
    path = bpio.remotePath(path)
    # lg.out(4, 'backup_fs.ListByPathAdvanced %s' % (path))
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
        (item_size, item_time, versions) = ExtractVersions(item_id, item_info, path_exist)  # , customer_id)
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
            sub_lookup = ListChildsByPath(sub_dir['path'])
            if not isinstance(sub_lookup, list):
                return sub_lookup
            result.extend(sub_lookup)
    return result


def ListByPathAdvanced(path, iter=None, iterID=None):
    """
    List all items at given ``path`` and return data in tuples:

        (type, name, path_id, size, time, remote_path, num_childs, item, versions)

    """
    if iter is None:
        iter = fs()
    if iterID is None:
        iterID = fsID()
    # customer_idurl = customerIDURLFromRootItem(iter)
    # customer_id = global_id.UrlToGlobalID(customer_idurl)
    if path == '/':
        path = ''
    path = bpio.remotePath(path)
    # lg.out(4, 'backup_fs.ListByPathAdvanced %s' % (path))
    iter_and_id = WalkByPath(path, iter=iter)
    if iter_and_id is None:
        return '%s not found' % path
    iter, pathID = iter_and_id
    iter_and_path = WalkByID(pathID, iterID=iterID)
    if iter_and_path is None:
        return '%s exist, but not found: %s' % (pathID, path)
    iterID, path_exist = iter_and_path
    if path != path_exist:
        return '%s exist, but not valid: %s' % (path_exist, path)
    result = []

    def visitor(item_type, item_name, item_path_id, item_info, num_childs):
        if item_type == DIR:
            item_id = (pathID + '/' + item_path_id).strip('/')
            (item_size, item_time, versions) = ExtractVersions(item_id, item_info, path_exist)  # , customer_id)
            result.append(('dir', item_info.name(), item_id,
                           item_size, item_time, path, num_childs, item_info, versions))
        elif item_type == FILE:
            item_id = (pathID + '/' + item_path_id).strip('/')
            (item_size, item_time, versions) = ExtractVersions(item_id, item_info, path_exist)  # , customer_id)
            result.append(('file', item_info.name(), item_id,
                           item_size, item_time, path, False, item_info, versions))

    TraverseChildsByID(visitor, iterID)
    return result


def ListAllBackupIDsAdvanced(sorted=False, reverse=False, iterID=None):
    """
    List all existing backups and return items info.
    """
    if not iterID:
        iterID = fsID()
    # customer_idurl = customerIDURLFromRootItemID(iterID)
    # customer_id = global_id.UrlToGlobalID(customer_idurl)

    result = []

    def visitor(path_id, path, info, num_childs):
        if (len(info.versions) == 0):
            return
        dirpath = os.path.dirname(path)
        (item_size, item_time, versions) = ExtractVersions(path_id, info, dirpath)  # , customer_id)
        if info.type == DIR:
            result.append(('dir', info.name(), path_id,
                           item_size, item_time, dirpath, num_childs, info.exist(), versions,))
        elif info.type == FILE:
            result.append(('file', info.name(), path_id,
                           item_size, item_time, dirpath, num_childs, info.exist(), versions,))

    TraverseByIDSorted(visitor, iterID=iterID)
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
        raise Exception('Directory not exist: %s' % basedir)
    customerGlobalID, remotePath = packetid.SplitPacketID(backupID)
    if not customerGlobalID:
        customerGlobalID = my_id.getGlobalID()
    path = os.path.join(basedir, customerGlobalID, remotePath)
    if os.path.exists(path):
        if not bpio.pathIsDir(path):
            raise Exception('Can not create directory %s' % path)
    else:
        os.makedirs(path)
    return path


def DeleteLocalDir(basedir, pathID):
    """
    Remove local sub folder at given ``basedir`` root path.
    """
    if not bpio.pathIsDir(basedir):
        raise Exception('Directory not exist: %s' % basedir)
    customer, pth = packetid.SplitPacketID(pathID)
    path = os.path.join(basedir, customer, pth)
    if not os.path.exists(path):
        return
    if not bpio.pathIsDir(path):
        raise Exception('Error, %s is not a directory' % path)
    bpio.rmdir_recursive(path, ignore_errors=True)


def DeleteLocalBackup(basedir, backupID):
    """
    Remove local files for that backup.
    """
    count_and_size = [0, 0, ]
    if not bpio.pathIsDir(basedir):
        raise Exception('Directory not exist: %s' % basedir)
    customer, pth = packetid.SplitPacketID(backupID)
    backupDir = os.path.join(basedir, customer, pth)
    if not bpio.pathExist(backupDir):
        return count_and_size[0], count_and_size[1]
    if not bpio.pathIsDir(backupDir):
        raise Exception('Error, %s is not a directory' % backupDir)

    def visitor(fullpath):
        if os.path.isfile(fullpath):
            try:
                count_and_size[1] += os.path.getsize(fullpath)
                count_and_size[0] += 1
            except:
                pass
        return True

    bpio.rmdir_recursive(backupDir, ignore_errors=True, pre_callback=visitor)
    return count_and_size[0], count_and_size[1]

#------------------------------------------------------------------------------


def Scan(basedir=None, customer_idurl=None):
    """
    Walk all items in the index and check if local files and folders with same
    names exists.

    Parameter ``basedir`` is a root path of that structure, default is
    ``lib.settings.getLocalBackupsDir()``. Also calculate size of the
    files.
    """
    if not customer_idurl:
        customer_idurl = my_id.getLocalID()
    if basedir is None:
        basedir = settings.getLocalBackupsDir()
        # os.path.join(settings.getLocalBackupsDir(), global_id.UrlToGlobalID(customer_idurl))
    iterID = fsID(customer_idurl)
    summ = [0, 0, ]

    def visitor(path_id, path, info):
        info.read_stats(path)
        if info.exist():
            summ[0] += info.size
        key_alias = 'master'
        if info.key_id:
            key_alias = packetid.KeyAlias(info.key_id)
        customer_id = global_id.MakeGlobalID(idurl=customer_idurl, key_alias=key_alias)
        versions_path = bpio.portablePath(os.path.join(basedir, customer_id, path_id))
        summ[1] += info.read_versions(versions_path)

    TraverseByID(visitor, iterID=iterID)
    return summ[0], summ[1]


def ScanID(pathID, basedir=None, customer_idurl=None):
    """
    Same as `Scan`, but check only single item in the index.
    """
    if not customer_idurl:
        customer_idurl = my_id.getLocalID()
    if basedir is None:
        basedir = settings.getLocalBackupsDir()
        # basedir = os.path.join(settings.getLocalBackupsDir(), global_id.UrlToGlobalID(customer_idurl))
    iter_and_path = WalkByID(pathID, iterID=fs(customer_idurl))
    if not iter_and_path:
        return
    itr, path = iter_and_path
    if isinstance(iter, dict):
        if INFO_KEY not in iter:
            return
        itr = iter[INFO_KEY]
    key_alias = 'master'
    if itr and itr.key_id:
        key_alias = packetid.KeyAlias(itr.key_id)
    customer_id = global_id.MakeGlobalID(idurl=customer_idurl, key_alias=key_alias)
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
                        # lg.out(16, '        [file] %s : %d bytes' % (i[id].path, i[id].size))
                if i[id].type == DIR:
                    _DirsCount += 1
                    if i[id].exist():
                        _SizeFolders += i[id].size
                        # lg.out(16, '        [file] %s : %d bytes' % (i[id].path, i[id].size))
                for version in i[id].list_versions():
                    versionSize = i[id].get_version_info(version)[1]
                    if versionSize > 0:
                        _SizeBackups += versionSize
                        # lg.out(16, '        [version] %s : %d bytes' % (i[id].path+'/'+version, versionSize))
                _ItemsCount += 1
            elif isinstance(i[id], dict):
                sub_folder_size = recursive_calculate(i[id])
                if sub_folder_size != -1:
                    folder_size += sub_folder_size
            else:
                raise Exception('Error, wrong item type in the index')
        if INFO_KEY in i:
            i[INFO_KEY].size = folder_size
            if i[INFO_KEY].type == FILE:
                _FilesCount += 1
                if i[INFO_KEY].exist():
                    _SizeFiles += i[INFO_KEY].size
                    # lg.out(16, '        [file] %s : %d bytes' % (i[INFO_KEY].path, i[INFO_KEY].size))
            if i[INFO_KEY].type == DIR:
                _DirsCount += 1
                if i[INFO_KEY].exist():
                    _SizeFolders += i[INFO_KEY].size
                    # lg.out(16, '        [file] %s : %d bytes' % (i[INFO_KEY].path, i[INFO_KEY].size))
            for version in i[INFO_KEY].list_versions():
                versionSize = i[INFO_KEY].get_version_info(version)[1]
                if versionSize > 0:
                    _SizeBackups += versionSize
                    # lg.out(16, '        [version] %s : %d bytes' % (i[INFO_KEY].path+'/'+version, versionSize))
            _ItemsCount += 1
        return folder_size

    if iterID is None:
        iterID = fsID()
    ret = recursive_calculate(iterID)
    lg.out(16, 'backup_fs.Calculate %d %d %d %d' % (
        _ItemsCount, _FilesCount, _SizeFiles, _SizeBackups))
    return ret

#------------------------------------------------------------------------------


def Clear(customer_idurl=None):
    """
    Erase all items in the index.
    """
    fs(customer_idurl=customer_idurl).clear()
    fsID(customer_idurl=customer_idurl).clear()


def Serialize(iterID=None, to_json=False, encoding='utf-8', filter_cb=None):
    """
    Use this to write index to the local file.
    """
    cnt = [0]
    if to_json:
        result = {'items': [], }
    else:
        result = StringIO()

    def cb(path_id, path, info):
        if filter_cb is not None:
            if not filter_cb(path_id, path, info):
                return
        if to_json:
            result['items'].append(info.serialize(encoding=encoding, to_json=True))
        else:
            result.write(info.serialize(encoding=encoding, to_json=False))
        cnt[0] += 1

    TraverseByID(cb, iterID=iterID)
    if to_json:
        # src = json.dumps(result, indent=2, encoding=encoding)
        src = result
    else:
        src = result.getvalue()
        result.close()
    lg.out(6, 'backup_fs.Serialize done with %d indexed files' % cnt[0])
    return src


def Unserialize(raw_data, iter=None, iterID=None, from_json=False, decoding='utf-8'):
    """
    Read index from ``StringIO`` object.
    """
    count = 0
    if from_json:
        # json_data = json.loads(raw_data, encoding=decoding)
        json_data = raw_data
        for json_item in json_data['items']:
            item = FSItemInfo()
            item.unserialize(json_item, decoding=decoding, from_json=True)
            if item.type == FILE:
                if not SetFile(item, iter=iter, iterID=iterID):
                    lg.warn('Can not put FILE item into the tree: %s' % str(item))
                    raise ValueError('Can not put FILE item into the tree: %s' % str(item))
                count += 1
            elif item.type == DIR:
                if not SetDir(item, iter=iter, iterID=iterID):
                    lg.warn('Can not put DIR item into the tree: %s' % str(item))
                    raise ValueError('Can not put DIR item into the tree: %s' % str(item))
                count += 1
            else:
                raise ValueError('Incorrect entry type')

    else:
        inpt = StringIO(raw_data)
        while True:
            src = inpt.readline() + inpt.readline()  # 2 times because we take 2 lines for every item
            if src.strip() == '':
                break
            item = FSItemInfo()
            item.unserialize(src, decoding=decoding, from_json=False)
            if item.type == FILE:
                if not SetFile(item, iter=iter, iterID=iterID):
                    inpt.close()
                    lg.warn('Can not put FILE item into the tree: %s' % str(item))
                    raise ValueError('Can not put FILE item into the tree: %s' % str(item))
                count += 1
            elif item.type == DIR:
                if not SetDir(item, iter=iter, iterID=iterID):
                    inpt.close()
                    lg.warn('Can not put DIR item into the tree: %s' % str(item))
                    raise ValueError('Can not put DIR item into the tree: %s' % str(item))
                count += 1
            else:
                inpt.close()
                raise ValueError('Incorrect entry type')
        inpt.close()
    lg.out(6, 'backup_fs.Unserialize done with %d indexed files' % count)
    return count

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
    # count = Unserialize(inpt)
    json_data = json.loads(inpt.read())
    customer_id = 'veselin@veselin-p2p.ru'
    customer_idurl = global_id.GlobalUserToIDURL(customer_id)
    count = Unserialize(json_data[customer_id], from_json=True, iter=fs(customer_idurl))
    inpt.close()
    # print count
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
    pprint.pprint(fs())
    print()
    pprint.pprint(fsID())
    print()

    print(HasChilds('', iter=fs(customer_idurl)))

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
