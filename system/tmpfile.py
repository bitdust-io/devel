#!/usr/bin/python
# tmpfile.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (tmpfile.py) is part of BitDust Software.
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
.. module:: tmpfile.

Keep track of temporary files created in the program. The temp folder is
placed in the BitDust data directory. All files are divided into several
sub folders.
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

import os
import tempfile
import time

from twisted.internet import task  # @UnresolvedImport

#------------------------------------------------------------------------------

from logs import lg

from system import bpio

#------------------------------------------------------------------------------

_TempDirPath = None
_FilesDict = {}
_CollectorTask = None
_SubDirs = {

    'outbox': 60 * 60 * 1,
    # hold onto outbox files 1 hour
    # so we can handle resends if contact is off-line

    'tcp-in': 60 * 10,
    # 10 minutes for incoming tcp files

    'udp-in': 60 * 10,
    # 10 minutes for incoming udp files

    'proxy-in': 60 * 10,
    # 10 minutes for incoming proxy files

    'proxy-out': 60 * 10,
    # 10 minutes for outgoing proxy files

    'propagate': 60 * 10,
    # propagate happens often enough,
    # 10 minutes should be enough

    'backup': 60 * 10,
    # 10 minutes for backup files

    'restore': 0,
    # never remove files during restore process, they must be cleaned afterwards

    'raid': 60 * 10,
    # 10 minutes for backup files

    'idsrv': 60,
    # 1 minute for incoming xml identity files

    'error': 60 * 60 * 24 * 30,
    # store errors for one month

    'all': 0,
    # other files. do not know when to remove
    # they can be even in another location
    # use register(name, filename)

}

#------------------------------------------------------------------------------


def init(temp_dir_path=''):
    """
    Must be called before all other things here.

    - check existence and access mode of temp folder
    - creates a needed sub folders
    - call ``startup_clean()``
    - starts collector task to call method ``collect()`` every 5 minutes
    """
    lg.out(4, 'tmpfile.init')
    global _TempDirPath
    global _SubDirs
    global _FilesDict
    global _CollectorTask

    if _TempDirPath is None:
        if temp_dir_path != '':
            _TempDirPath = temp_dir_path
        else:
            os_temp_dir = tempfile.gettempdir()
            temp_dir = os.path.join(os_temp_dir, 'bitdust')

            if not os.path.exists(temp_dir):
                try:
                    os.mkdir(temp_dir)
                except:
                    lg.out(2, 'tmpfile.init ERROR can not create ' + temp_dir)
                    lg.exc()
                    temp_dir = os_temp_dir

            if not os.access(temp_dir, os.W_OK):
                lg.out(2, 'tmpfile.init ERROR no write permissions to ' + temp_dir)
                temp_dir = os_temp_dir

            _TempDirPath = temp_dir
        lg.out(6, 'tmpfile.init  _TempDirPath=' + _TempDirPath)

    for name in _SubDirs.keys():
        if not os.path.exists(subdir(name)):
            try:
                os.makedirs(subdir(name))
            except:
                lg.out(2, 'tmpfile.init ERROR can not create ' + subdir(name))
                lg.exc()

    for name in _SubDirs.keys():
        if name not in _FilesDict:
            _FilesDict[name] = {}

    startup_clean()

    if _CollectorTask is None:
        _CollectorTask = task.LoopingCall(collect)
        _CollectorTask.start(60 * 5)


def shutdown():
    """
    Do not need to remove any files here, just stop the collector task.
    """
    lg.out(4, 'tmpfile.shutdown')
    global _CollectorTask
    if _CollectorTask is not None:
        _CollectorTask.stop()
        del _CollectorTask
        _CollectorTask = None


def subdir(name):
    """
    Return a path to given sub folder.
    """
    global _TempDirPath
    if _TempDirPath is None:
        init()
    return os.path.join(_TempDirPath, name)


def register(filepath):
    """
    You can create a temp file in another place and call this method to be able
    to hadle this file later.
    """
    global _FilesDict
    subdir, filename = os.path.split(filepath)
    name = os.path.basename(subdir)
    if name not in list(_FilesDict.keys()):
        name = 'all'
    _FilesDict[name][filepath] = time.time()


def make(name, extension='', prefix=''):
    """
    Make a new file under sub folder ``name`` and return a tuple of it's file
    descriptor and path.

    .. warning::    Remember you need to close the file descriptor by your own.
    The ``tmpfile`` module will remove it later - do not worry.
    This is a job for our collector.
    However if you will keep the file opened for awhile
    it should print a ```WARNING``` in logs because will fail to delete it.
    """
    global _TempDirPath
    global _FilesDict
    if _TempDirPath is None:
        init()
    if name not in list(_FilesDict.keys()):
        name = 'all'
    try:
        fd, filename = tempfile.mkstemp(extension, prefix, subdir(name))
        _FilesDict[name][filename] = time.time()
    except:
        lg.out(1, 'tmpfile.make ERROR creating file in sub folder ' + name)
        lg.exc()
        return None, ''
    if _Debug:
        lg.out(_DebugLevel, 'tmpfile.make ' + filename)
    return fd, filename


def make_dir(name, extension='', prefix=''):
    """
    """
    global _TempDirPath
    global _FilesDict
    if _TempDirPath is None:
        init()
    if name not in list(_FilesDict.keys()):
        name = 'all'
    try:
        dirname = tempfile.mkdtemp(extension, prefix, subdir(name))
        _FilesDict[name][dirname] = time.time()
    except:
        lg.out(1, 'tmpfile.make_dir ERROR creating folder in ' + name)
        lg.exc()
        return None
    if _Debug:
        lg.out(_DebugLevel, 'tmpfile.make_dir ' + dirname)
    return dirname


def erase(name, filename, why='no reason'):
    """
    However you can remove not needed file immediately, this is a good way
    also.

    But outside of this module you better use method ``throw_out``.
    """
    global _FilesDict
    if name in list(_FilesDict.keys()):
        try:
            _FilesDict[name].pop(filename, '')
        except:
            lg.warn('we do not know about file [%s] in sub folder %s, we tried because %s' % (filename, name, why))
    else:
        lg.warn('we do not know sub folder: %s, we tried because %s' % (name, why))

    if not os.path.exists(filename):
        lg.warn('[%s] not exist' % filename)
        return

    if os.path.isfile(filename):
        if not os.access(filename, os.W_OK):
            lg.warn('[%s] no write permissions' % filename)
            return
        try:
            os.remove(filename)
            if _Debug:
                lg.out(_DebugLevel, 'tmpfile.erase [%s] : "%s"' % (filename, why))
        except:
            lg.out(2, 'tmpfile.erase ERROR can not remove [%s], we tried because %s' % (filename, why))
            # exc()

    elif os.path.isdir(filename):
        bpio.rmdir_recursive(filename, ignore_errors=True)
        if _Debug:
            lg.out(_DebugLevel, 'tmpfile.erase recursive [%s] : "%s"' % (filename, why))

    else:
        raise Exception('[%s] not exist' % filename)


def throw_out(filepath, why='dont know'):
    """
    A more smart way to remove not needed temporary file, accept a full
    ``filepath``.
    """
    global _FilesDict
    global _SubDirs
    subdir, _ = os.path.split(filepath)
    name = os.path.basename(subdir)
    erase(name, filepath, why)


def collect():
    """
    Removes old temporary files.
    """
    if _Debug:
        lg.out(_DebugLevel - 4, 'tmpfile.collect')
    global _FilesDict
    global _SubDirs
    erase_list = []
    for name in _FilesDict.keys():
        # for data and parity files we have special rules
        # we do not want to remove Data or Parity here.
        # backup_monitor should take care of this.
        if name == 'data-par':
            continue

        else:
            # how long we want to keep the file?
            lifetime = _SubDirs.get(name, 0)
            # if this is not set - keep forever
            if lifetime == 0:
                continue
            for filename, filetime in _FilesDict[name].items():
                # if file is too old - remove it
                if time.time() - filetime > lifetime:
                    erase_list.append((name, filename))

    for name, filename in erase_list:
        erase(name, filename, 'collected')

    if _Debug:
        lg.out(_DebugLevel - 4, 'tmpfile.collect %d files erased' % len(erase_list))

    del erase_list


def startup_clean():
    """
    At startup we want to scan all sub folders and remove the old files.

    We will get creation time with built-in ``os.stat`` method.
    """
    global _TempDirPath
    global _SubDirs
    if _Debug:
        lg.out(_DebugLevel - 4, 'tmpfile.startup_clean in %s' % _TempDirPath)
    if _TempDirPath is None:
        return
    counter = 0
    limit_counts = 200
    for name in os.listdir(_TempDirPath):
        # we want to scan only our folders
        # do not want to be responsible of other files
        if name not in list(_SubDirs.keys()):
            continue

        # for data and parity files we have special rules
        # we do not want to remove Data or Parity here.
        # backup_monitor should take care of this.
        if name == 'data-par':
            pass

        else:
            lifetime = _SubDirs.get(name, 0)
            if lifetime == 0:
                continue
            for filename in os.listdir(subdir(name)):
                filepath = os.path.join(subdir(name), filename)
                if os.path.isfile(filepath):
                    filetime = os.stat(filepath).st_ctime
                    if time.time() - filetime > lifetime:
                        erase(name, filepath, 'startup cleaning')
                        counter += 1
                        if counter > limit_counts:
                            break
                elif os.path.isdir(filepath):
                    erase(name, filepath, 'startup cleaning')
                    counter += 1
                    if counter > limit_counts:
                        break
                else:
                    raise Exception('%s not exist' % filepath)

#------------------------------------------------------------------------------


if __name__ == '__main__':
    lg.set_debug_level(18)
    init()
    fd, filename = make('raid')
    os.write(fd, 'TEST FILE')
    os.close(fd)
    from twisted.internet import reactor  # @UnresolvedImport
    reactor.run()
