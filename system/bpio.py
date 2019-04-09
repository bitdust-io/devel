#!/usr/bin/python
# bpio.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (bpio.py) is part of BitDust Software.
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
.. module:: bpio.

This module is for simple BitDust routines that do not require importing any of our code.:
    - print logs
    - file system IO operations
    - pack/unpack lists and dictionaries into strings
    - some methods to operate with file system paths
    - list Linux mount points and Windows drives
    - methods to manage system processes

Most used method here is ``log`` - prints a log string.

TODO: need to do some refactoring here
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from io import open

#------------------------------------------------------------------------------

import os
import sys
import imp
import platform
import glob
import re

#------------------------------------------------------------------------------

from lib import strng

from logs import lg

from system import local_fs

#------------------------------------------------------------------------------

LocaleInstalled = False
PlatformInfo = None
X11isRunning = None

#------------------------------------------------------------------------------


def init():
    """
    This method must be called firstly, before any logs will be printed.

    This installs a system locale, so all output messages will have a
    correct encoding.
    """
    InstallLocale()
    if Linux() or Mac():
        lg.setup_unbuffered_stdout()


def shutdown():
    """
    This is the last method to be invoked by the program before main process
    will stop.
    """
    lg.restore_original_stdout()
    lg.close_log_file()
    lg.disable_logs()


def InstallLocale():
    """
    Here is a small trick to refresh current default encoding.
    """
    global LocaleInstalled
    if LocaleInstalled:
        return False
    try:
        import sys
        if sys.version_info[0] == 2:
            reload(sys)  # @UndefinedVariable
            if Windows():
                if hasattr(sys, "setdefaultencoding"):
                    import locale
                    denc = locale.getpreferredencoding()
                    if not denc:
                        sys.setdefaultencoding('UTF8')
                    else:
                        sys.setdefaultencoding(denc)
            else:
                sys.setdefaultencoding('UTF8')
        LocaleInstalled = True
    except:
        lg.exc()
    return LocaleInstalled


def ostype():
    """
    Return current platform: "Linux", "Windows", "Darwin".

    MacOS is not supported yet. Don't print anything in ostype because
    used in bppipe.py and stdout goes to tar file.
    """
    global PlatformInfo
    if PlatformInfo is None:
        PlatformInfo = platform.uname()
    return PlatformInfo[0]


def osversion():
    """
    Return something like: "2.6.32.9-rscloud" or "XP".
    """
    global PlatformInfo
    if PlatformInfo is None:
        PlatformInfo = platform.uname()
    return PlatformInfo[2]


def osinfo():
    """
    Return full OS info, like: "Linux-2.6.32.9-rscloud-x86_64-with-
    Ubuntu-12.04-precise" or "Windows-XP-5.1.2600-SP3".
    """
    return str(platform.platform()).strip()


def osinfofull():
    """
    Return detailed system info.
    """
    import pprint
    o = ''
    o += '=====================================================\n'
    o += '=====================================================\n'
    o += '=====================================================\n'
    o += 'platform.uname(): ' + str(platform.uname()) + '\n'
    try:
        o += '__file__: ' + str(__file__) + '\n'
    except:
        o += 'variable __file__ is not defined\n'
    o += 'sys.executable: ' + sys.executable + '\n'
    o += 'os.path.abspath("."): ' + os.path.abspath('.') + '\n'
    o += 'os.path.abspath(sys.argv[0]): ' + os.path.abspath(sys.argv[0]) + '\n'
    o += 'os.path.expanduser("~"): ' + os.path.expanduser('~') + '\n'
    o += 'sys.argv: ' + pprint.pformat(sys.argv) + '\n'
    o += 'sys.path:\n' + pprint.pformat(sys.path) + '\n'
    o += 'os.environ:\n' + pprint.pformat(list(os.environ.items())) + '\n'
    o += '=====================================================\n'
    o += '=====================================================\n'
    o += '=====================================================\n'
    return o


def windows_version():
    """
    Useful to detect current Windows version: XP, Vista, 7 or 8.
    """
    if getattr(sys, 'getwindowsversion', None) is not None:
        return sys.getwindowsversion()[0]  # @UndefinedVariable
    return 0


def Linux():
    """
    Return True if current platform is Linux.
    """
    return ostype() == "Linux"


def Windows():
    """
    Return True if current platform is Windows.
    """
    return ostype() == "Windows"


def Mac():
    """
    Return True if current platform is Mac.
    """
    return ostype() == "Darwin"


def Android():
    """
    Return True if running on Android inside Kivy.
    """
    return 'ANDROID_ARGUMENT' in os.environ


def isFrozen():
    """
    Return True if BitDust is running from exe, not from sources.
    """
    return main_is_frozen()


def isConsoled():
    """
    Return True if output can be sent to console.
    """
    if getExecutableFilename().count('pythonw.exe'):
        return False
    if not sys.stdout:
        return False
    return True

#-------------------------------------------------------------------------------


def list_dir_safe(dirpath):
    """
    A safe wrapper around built-in ``os.listdir()`` method.
    """
    try:
        return os.listdir(dirpath)
    except:
        return []


def list_dir_recursive(dirpath):
    """
    Recursively scan files and folders under ``dirpath`` and return them in the
    list.
    """
    r = []
    for name in os.listdir(dirpath):
        full_name = os.path.join(dirpath, name)
        if os.path.isdir(full_name):
            r.extend(list_dir_recursive(full_name))
        else:
            r.append(full_name)
    return r


def traverse_dir_recursive(callback, basepath, relpath=''):
    """
    Call ``callback`` method for every file and folder under ``basepath``.

    If method ``callback`` can returns False traverse process will not
    go deeper. Useful to count size of the whole folder.
    """
    for name in os.listdir(basepath):
        realpath = os.path.join(basepath, name)
        subpath = name if relpath == '' else relpath + '/' + name
        go_down = callback(realpath, subpath, name)
        if os.path.isdir(realpath) and go_down:
            traverse_dir_recursive(callback, realpath, subpath)


def rmdir_recursive(dirpath, ignore_errors=False, pre_callback=None):
    """
    Remove a directory, and all its contents if it is not already empty.

    http://mail.python.org/pipermail/python-
    list/2000-December/060960.html If ``ignore_errors`` is True process
    will continue even if some errors happens. Method ``pre_callback``
    can be used to decide before remove the file.
    """
    for name in os.listdir(dirpath):
        full_name = os.path.join(dirpath, name)
        # on Windows, if we don't have write permission we can't remove
        # the file/directory either, so turn that on
        if not os.access(full_name, os.W_OK):
            try:
                os.chmod(full_name, 0o600)
            except:
                continue
        if os.path.isdir(full_name):
            rmdir_recursive(full_name, ignore_errors, pre_callback)
        else:
            if pre_callback:
                if not pre_callback(full_name):
                    continue
            if os.path.isfile(full_name):
                if not ignore_errors:
                    os.remove(full_name)
                else:
                    try:
                        os.remove(full_name)
                    except:
                        lg.out(6, 'bpio.rmdir_recursive can not remove file ' + full_name)
                        continue
    if pre_callback:
        if not pre_callback(dirpath):
            return
    if not ignore_errors:
        os.rmdir(dirpath)
    else:
        try:
            os.rmdir(dirpath)
        except:
            lg.out(6, 'bpio.rmdir_recursive can not remove dir ' + dirpath)


def getDirectorySize(directory, include_subfolders=True):
    """
    Platform dependent way to calculate folder size.
    """
    if Windows():
        import win32file  # @UnresolvedImport
        import win32con  # @UnresolvedImport
        import pywintypes  # @UnresolvedImport
        DIR_EXCLUDES = set(['.', '..'])
        MASK = win32con.FILE_ATTRIBUTE_DIRECTORY | win32con.FILE_ATTRIBUTE_SYSTEM
        REQUIRED = win32con.FILE_ATTRIBUTE_DIRECTORY
        FindFilesW = win32file.FindFilesW

        def _get_dir_size(path):
            total_size = 0
            try:
                items = FindFilesW(path + r'\*')
            except pywintypes.error as ex:
                return total_size
            for item in items:
                total_size += item[5]
                if item[0] & MASK == REQUIRED and include_subfolders:
                    name = item[8]
                    if name not in DIR_EXCLUDES:
                        total_size += _get_dir_size(path + '\\' + name)
            return total_size
        return _get_dir_size(directory)
    dir_size = 0
    if not include_subfolders:
        for filename in os.listdir(directory):
            filepath = os.path.abspath(os.path.join(directory, filename))
            if os.path.isfile(filepath):
                try:
                    dir_size += os.path.getsize(filepath)
                except:
                    pass
    else:
        for (path, dirs, files) in os.walk(directory):
            for file in files:
                filename = os.path.join(path, file)
                if os.path.isfile(filename):
                    try:
                        dir_size += os.path.getsize(filename)
                    except:
                        pass
    return dir_size

#-------------------------------------------------------------------------------

def WriteBinaryFile(filename, data):
    return local_fs.WriteBinaryFile(filename=filename, data=data)


def ReadBinaryFile(filename, decode_encoding=None):
    return local_fs.ReadBinaryFile(filename=filename, decode_encoding=decode_encoding)


def WriteTextFile(filepath, data):
    return local_fs.WriteTextFile(filepath=filepath, data=data)


def ReadTextFile(filename):
    return local_fs.ReadTextFile(filename=filename)

#-------------------------------------------------------------------------------


def _pack_list(lst):
    """
    The core method, convert list of strings to one big string.
    Every line in the string will store a single item from list. First
    line will keep a number of items. So items in the list should be a
    strings and not contain "\n".\ This is useful to store a list of
    users IDs in the local file.
    """
    return str(len(lst)) + u'\n' + u'\n'.join(lst)


def _unpack_list(src):
    """
    The core method, read a list from string.
    Return a tuple : (resulted list, list with lines from rest string or None).
    First line of the ``src`` should contain a number of items in the list.
    """
    if not src.strip():
        return list(), None
    words = src.splitlines()
    if len(words) == 0:
        return list(), None
    try:
        length = int(words[0])
    except:
        return words, None
    res = words[1:]
    if len(res) < length:
        res += [u'', ] * (length - len(res))
    elif len(res) > length:
        return res[:length], res[length:]
    return res, None


def _read_list(path):
    """
    Read list from file on disk.
    """
    src = ReadTextFile(path)
    if src is None:
        return None
    return _unpack_list(src)[0]


def _write_list(path, lst):
    """
    Write a list to the local file.
    """
    return WriteTextFile(path, _pack_list(lst))


def _pack_dict(dictionary, sort=False):
    """
    The core method, convert dictionary to the string.

    Every line in resulted string will contain a key, value pair,
    separated with single space. So keys and must not contain spaces.
    Values must not contain new lines. If ``sort`` is True the resulted
    string will be sorted by keys.
    """
    if sort:
        seq = sorted(dictionary.keys())
    else:
        seq = list(dictionary.keys())
    return u'\n'.join([u'%s %s' % (k, strng.to_text(str(dictionary[k]))) for k in seq])


def _unpack_dict_from_list(lines):
    """
    Read dictionary from list, every item in the list is a string with (key,
    value) pair, separated with space.
    """
    dct = {}
    for line in lines:
        words = line.split(u' ')
        if len(words) < 2:
            continue
        dct[words[0]] = u' '.join(words[1:])
    return dct


def _unpack_dict(src):
    """
    The core method, creates dictionary from string.
    """
    lines = strng.to_text(src).split(u'\n')
    return _unpack_dict_from_list(lines)


def _read_dict(path, default=None):
    """
    Read dictionary from local file.

    If file not exist or no read access - returns ``default`` value.
    """
    src = ReadTextFile(path)
    if src is None:
        return default
    return _unpack_dict(src.strip())


def _write_dict(path, dictionary, sort=False):
    """
    Write dictionary to the file.
    """
    data = _pack_dict(dictionary, sort)
    return WriteTextFile(path, data)


def _dir_exist(path):
    """
    Just calls os.path.isdir() method.
    """
    return os.path.isdir(path)


def _dir_make(path):
    """
    Creates a new folder on disk, call built-in os.mkdir() method.

    Set access mode to 0777.
    """
    os.mkdir(path, 0o777)


def _dirs_make(path):
    """
    Create a new folder and all sub dirs, call built-in os.makedirs() method.

    Set access mode to 0777.
    """
    os.makedirs(path, 0o777)


def _dir_remove(path):
    """
    Remove directory recursively.
    """
    rmdir_recursive(path)

#------------------------------------------------------------------------------


def backup_and_remove(path):
    """
    Backup and remove the file.

    Backed up file will have ".backup" at the end. In fact it just tries
    to rename the original file, but also do some checking before. If
    file with ".backup" already exist it will try to remove it before.
    """
    bkpath = path + '.backup'
    if not os.path.exists(path):
        return
    if os.path.exists(bkpath):
        try:
            os.remove(bkpath)
        except:
            lg.out(1, 'bpio.backup_and_remove ERROR can not remove file ' + bkpath)
            lg.exc()
    try:
        os.rename(path, bkpath)
    except:
        lg.out(1, 'bpio.backup_and_remove ERROR can not rename file %s to %s' % (path, bkpath))
        lg.exc()
    if os.path.exists(path):
        try:
            os.remove(path)
        except:
            lg.out(1, 'bpio.backup_and_remove ERROR can not remove file ' + path)
            lg.exc()


def restore_and_remove(path, overwrite_existing=False):
    """
    Restore file and remove the backed up copy.

    Just renames the file with ".backup" at the end to its 'true' name.
    This is reverse method to ``backup_and_remove``.
    """
    bkpath = path + '.backup'
    if not os.path.exists(bkpath):
        return
    if os.path.exists(path):
        if not overwrite_existing:
            return
        try:
            os.remove(path)
        except:
            lg.out(1, 'bpio.restore_and_remove ERROR can not remove file ' + path)
            lg.exc()
    try:
        os.rename(bkpath, path)
    except:
        lg.out(1, 'bpio.restore_and_remove ERROR can not rename file %s to %s' % (path, bkpath))
        lg.exc()


def remove_backuped_file(path):
    """
    Tries to remove the file with ".backup" at the end.
    """
    bkpath = path + '.backup'
    if not os.path.exists(bkpath):
        return
    try:
        os.remove(bkpath)
    except:
        lg.out(1, 'bpio.remove_backuped_file ERROR can not remove file ' + bkpath)
        lg.exc()

#------------------------------------------------------------------------------


def LowerPriority():
    """
    Platform dependent method to lower the priority of the running process.
    """
    try:
        sys.getwindowsversion()  # @UndefinedVariable
    except:
        isWindows = False
    else:
        isWindows = True
    if isWindows:
        # Based on:
        #   "Recipe 496767: Set Process Priority In Windows" on ActiveState
        #   http://code.activestate.com/recipes/496767/
        import win32api  # @UnresolvedImport
        import win32process  # @UnresolvedImport
        import win32con  # @UnresolvedImport
        pid = win32api.GetCurrentProcessId()
        handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, True, pid)
        win32process.SetPriorityClass(handle, win32process.BELOW_NORMAL_PRIORITY_CLASS)
    else:
        import os
        os.nice(20)


def HigherPriority():
    try:
        sys.getwindowsversion()  # @UndefinedVariable
    except:
        isWindows = False
    else:
        isWindows = True
    if isWindows:
        import win32api  # @UnresolvedImport
        import win32process  # @UnresolvedImport
        import win32con  # @UnresolvedImport
        pid = win32api.GetCurrentProcessId()
        handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, True, pid)
        win32process.SetPriorityClass(handle, win32process.REALTIME_PRIORITY_CLASS)
    else:
        import os
        os.nice(1)

#-------------------------------------------------------------------------------


def shortPath(path):
    """
    Get absolute 'short' path in Unicode, converts to 8.3 windows filenames.
    """
    path_ = os.path.abspath(path)
    if not Windows():
        return strng.to_text(path_)
    if not os.path.exists(path_):
        if os.path.isdir(os.path.dirname(path_)):
            res = shortPath(os.path.dirname(path_))
            return strng.to_text(os.path.join(res, os.path.basename(path_)))
        return strng.to_text(path_)
    try:
        import win32api  # @UnresolvedImport
        spath = win32api.GetShortPathName(path_)
        return strng.to_text(spath)
    except:
        lg.exc()
        return strng.to_text(path_)


def longPath(path):
    """
    Get absolute 'long' path in Unicode, convert to full path, even if it was
    in 8.3 format.
    """
    path_ = os.path.abspath(path)
    if not Windows():
        return strng.to_text(path_)
    if not os.path.exists(path_):
        return strng.to_text(path_)
    try:
        import win32api  # @UnresolvedImport
        lpath = win32api.GetLongPathName(path_)
        return strng.to_text(lpath)
    except:
        lg.exc()
    return strng.to_text(path_)


# def portablePath(path):
#    """
#    For Windows changes all separators to Linux format:
#        - "\\" -> "/"
#        - "\" -> "/"
#    If ``path`` is unicode convert to utf-8.
#    """
#    p = path
#    if Windows():
#        p = p.replace('\\\\', '/').replace('\\', '/')
#    if isinstance(p, unicode):
#        return p.encode('utf-8')
#    return p


def remotePath(path):
    """
    Simplify and clean "remote" path value.
    """
    p = strng.to_text(path)
    if p == u'' or p == u'/':
        return p
    p = p.lstrip(u'/').lstrip(u'\\')
    if p.endswith(u'/') and len(p) > 1:
        p = p.rstrip(u'/')
    return p


def portablePath(path):
    """
    Fix path to fit for our use:

    - do convert to absolute path
    - for Windows:
        - change all separators to Linux format: "\\"->"/" and "\"=>"/"
        - convert disk letter to lower case
    - convert to unicode
    """
    path = strng.to_text(path)
    if path == u'' or path == u'/':
        return path
    if Windows() and len(path) == 2 and path[1] == u':':
        # "C:" -> "C:/"
        path += u'/'
    if path.count(u'~'):
        path = os.path.expanduser(path)
    p = os.path.abspath(path)
    if Windows():
        p = p.replace(u'\\', u'/')
        if len(p) >= 2:
            if p[1] == u':':
                p = p[0].lower() + p[1:]
            elif p[:2] == u'//':
                p = u'\\\\' + p[2:]
    if p.endswith(u'/') and len(p) > 1:
        p = p.rstrip(u'/')
    return p


def pathExist(localpath):
    """
    My own "portable" version of built-in ``os.path.exist()`` method.
    """
    if os.path.exists(localpath):
        return True
    p = portablePath(localpath)
    if os.path.exists(p):
        return True
    if Windows() and pathIsNetworkLocation(localpath):
        return True
    return False


def pathIsDir(localpath):
    """
    Assume localpath is exist and return True if this is a folder.
    """
    if os.path.isdir(localpath):
        return True
    if os.path.exists(localpath) and os.path.isfile(localpath):
        return False
    # don't know... let's try portable path
    p = portablePath(localpath)
    if os.path.isdir(p):
        return True
    if os.path.exists(localpath) and os.path.isfile(p):
        return False
    if Windows() and pathIsNetworkLocation(localpath):
        return True
    # may be path is not exist at all?
    if not os.path.exists(localpath):
        return False
    if not os.path.exists(p):
        return False
    # ok, on Linux we have devices, mounts, links ...
    if Linux():
        try:
            import stat
            st = os.path.stat(localpath)
            return stat.S_ISDIR(st.st_mode)
        except:
            return False
    # now we are in really big trouble
    raise Exception('Path not exist: %s' % p)
    return False


def pathIsDriveLetter(path):
    """
    Return True if ``path`` is a Windows drive letter.
    """
    p = path.rstrip('/').rstrip('\\')
    if len(p) != 2:
        return False
    if p[1] != ':':
        return False
    if not p[0].isalpha():
        return False
    return True


def pathIsNetworkLocation(path):
    """
    Return True if ``path`` is a Windows network location.

        >>> pathIsNetworkLocation(r'\\remote_machine')
        True
    """
    p = path.rstrip('/').rstrip('\\')
    if len(p) < 3:
        return False
    if not p.startswith('\\\\'):
        return False
    if p[2:].count('\\') or p[2:].count('/'):
        return False
    return True

#------------------------------------------------------------------------------


def main_is_frozen():
    """
    Return True if BitDust is started from .exe not from sources.

    http://www.py2exe.org/index.cgi/HowToDetermineIfRunningFromExe
    """
    return (hasattr(sys, "frozen") or       # new py2exe
            hasattr(sys, "importers") or    # old py2exe
            imp.is_frozen("__main__"))      # tools/freeze


def isGUIpossible():
    """
    """
    # if Windows():
    #     return True
    # if Mac():
    #     return True
    # if Linux():
    #     return X11_is_running()
    # All the UI now will be created using Electron framework.
    # To make it possible we need to run local API rest_http/json_rpc server.
    # So here we always return False from now.
    return False


def X11_is_running():
    """
    Linux method to check if BitDust GUI is possible.

    http://stackoverflow.com/questions/1027894/detect-if-x11-is-
    available-python
    """
    global X11isRunning
    if not Linux():
        return False
    if X11isRunning is not None:
        return X11isRunning
    try:
        from subprocess import Popen, PIPE
        p = Popen(["xset", "-q"], stdout=PIPE, stderr=PIPE)
        p.communicate()
        result = p.returncode == 0
    except:
        result = False
    X11isRunning = result
    return X11isRunning

#------------------------------------------------------------------------------


def getExecutableDir():
    """
    A smart way to detect the path of executable folder.
    """
    if main_is_frozen():
        path = os.path.dirname(os.path.abspath(sys.executable))
    else:
        try:
            path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        except:
            path = os.path.dirname(os.path.abspath(sys.argv[0]))
    return strng.to_text(path)


def getExecutableFilename():
    """
    A smart way to detect executable file name.
    """
    if main_is_frozen():
        path = os.path.abspath(sys.executable)
    else:
        path = os.path.abspath(sys.argv[0])
    return strng.to_text(path)


def getUserName():
    """
    Return current user name in unicode string.
    """
    try:
        import pwd
    except ImportError:
        try:
            import getpass
        except:
            pass
        pwd = None
    try:
        if pwd:
            return pwd.getpwuid(os.geteuid()).pw_name
        else:
            return getpass.getuser()
    except:
        pass
    return os.path.basename(strng.to_text(os.path.expanduser('~')))

#------------------------------------------------------------------------------


def listHomeDirLinux():
    """
    Just return a list of files and folders in the user home dir.
    """
    if Windows():
        return []
    rootlist = []
    homedir = os.path.expanduser('~')
    for dirname in os.listdir(homedir):
        if os.path.isdir(os.path.join(homedir, dirname)):
            rootlist.append(dirname)
    return rootlist


def listLocalDrivesWindows():
    """
    Return a list of drive letters under Windows.

    This list should include only "fixed", "writable" and "real" drives,
    not include cd drives, network drives, USB drives, etc.
    """
    if not Windows():
        return []
    rootlist = []
    try:
        import win32api  # @UnresolvedImport
        import win32file  # @UnresolvedImport
        drives = (drive for drive in win32api.GetLogicalDriveStrings().split("\000") if drive)
        for drive in drives:
            if win32file.GetDriveType(drive) == 3:
                rootlist.append(drive)
    except:
        lg.exc()
    return rootlist


def listRemovableDrivesWindows():
    """
    Return a list of "removable" drives under Windows.
    """
    l = []
    try:
        import win32file  # @UnresolvedImport
        drivebits = win32file.GetLogicalDrives()
        for d in range(1, 26):
            mask = 1 << d
            if drivebits & mask:
                # here if the drive is at least there
                drname = '%c:\\' % chr(ord('A') + d)
                t = win32file.GetDriveType(drname)
                if t == win32file.DRIVE_REMOVABLE:
                    l.append(drname)
    except:
        lg.exc()
    return l


def listRemovableDrivesLinux():
    """
    Return a list of "removable" drives under Linux.

    The same idea with ``listRemovableDrivesWindows``.
    """
    try:
        return [os.path.join('/media', x) for x in os.listdir('/media')]
    except:
        return []


def listRemovableDrives():
    """
    Platform-independent way to get a list of "removable" locations.

    Used to detect the location to write a copy of Private Key. Should
    detect USB flash drives.
    """
    if Linux():
        return listRemovableDrivesLinux()
    elif Windows():
        return listRemovableDrivesWindows()
    return []


def listMountPointsLinux():
    """
    Return a list of mount points under Linux.

    Used to detect locations for donated space and local backups.
    """
    mounts = os.popen('mount')
    result = []
    if Linux():
        mch = re.compile('^(.+?) on (.+?) type .+?$')
    else:  # Mac
        mch = re.compile('^(.+?) on (.+?).*?$')
    # mo = re.match('^(.+?) on (.+?) type .+?$', line)
    for line in mounts.readlines():
        mo = mch.match(line)
        if mo:
            device = mo.group(1)
            mount_point = mo.group(2)
            if device.startswith('/dev/'):
                result.append(mount_point)
    return result


def getMountPointLinux(path):
    """
    Return mount point for given path.
    """
    path = os.path.abspath(path)
    while not os.path.ismount(path):
        path = os.path.dirname(path)
    return path

#-------------------------------------------------------------------------------


def find_process(applist):
    """
    A portable method to search executed processes.

    You can provide a name or regexp to scan.
    """
    try:
        import psutil
        pidsL = []
        for p in psutil.process_iter():
            try:
                p_pid = p.pid
                p_cmdline = p.cmdline()
            except:
                continue
            if p_pid == os.getpid():
                continue
            for app in applist:
                try:
                    cmdline = ' '.join(p_cmdline)
                except:
                    continue
                if app.startswith('regexp:'):
                    if re.match(app[7:], cmdline) is not None:
                        pidsL.append(p_pid)
                else:
                    if cmdline.count(app):
                        pidsL.append(p_pid)
        if pidsL:
            return pidsL
    except:
        pass
    ostype = platform.uname()[0]
    if ostype == "Windows":
        return find_process_win32(applist)
    else:
        return find_process_linux(applist)
    return []


def kill_process(pid):
    """
    Call to OS ``kill`` procedure. Portable.

    ``pid`` - process id.
    """
    ostype = platform.uname()[0]
    if ostype == "Windows":
        kill_process_win32(pid)
    else:
        kill_process_linux(pid)


def list_processes_linux():
    """
    This function will return an iterator with the process pid/cmdline tuple.

    :return: pid, cmdline tuple via iterator
    :rtype: iterator

    >>> for procs in list_processes_linux():
    >>>     print procs
    ('5593', '/usr/lib/mozilla/kmozillahelper')
    ('6353', 'pickup -l -t fifo -u')
    ('6640', 'kdeinit4: konsole [kdeinit]')
    ('6643', '/bin/bash')
    ('7451', '/usr/bin/python /usr/bin/ipython')
    """
    for pid_path in glob.glob('/proc/[0-9]*'):
        try:
            # cmdline represents the command whith which the process was started
            f = open("%s/cmdline" % pid_path)
            pid = pid_path.split("/")[2]  # get the PID
            # we replace the \x00 to spaces to make a prettier output from kernel
            cmdline = f.read().replace("\x00", " ").rstrip()
            f.close()
            yield (pid, cmdline)
        except:
            pass


def find_process_linux(applist):
    """
    You can look for some process name, give a keywords or regexp strings list
    to search.

    This is for Linux.
    """
    pidsL = []
    for pid, cmdline in list_processes_linux():
        try:
            pid = int(pid)
        except:
            continue
        if pid == os.getpid():
            continue
        for app in applist:
            if app.startswith('regexp:'):
                if re.match(app[7:], cmdline) is not None:
                    pidsL.append(pid)
            else:
                if cmdline.find(app) > -1:
                    pidsL.append(pid)
    return pidsL


def find_process_win32(applist):
    """
    Search for process name, for MS Windows.
    """
    pidsL = []
    try:
        import win32com.client  # @UnresolvedImport
        objWMI = win32com.client.GetObject("winmgmts:\\\\.\\root\\CIMV2")
        colProcs = objWMI.ExecQuery("SELECT * FROM Win32_Process")
        for Item in colProcs:
            pid = int(Item.ProcessId)
            if pid == os.getpid():
                continue
            cmdline = Item.Caption.lower()
            if Item.CommandLine:
                cmdline += Item.CommandLine.lower()
            for app in applist:
                if app.startswith('regexp:'):
                    if re.match(app[7:], cmdline) is not None:
                        pidsL.append(pid)
                else:
                    if cmdline.find(app) > -1:
                        pidsL.append(pid)
    except:
        lg.exc()
    return pidsL


def kill_process_linux(pid):
    """
    Make a call to system ``kill`` command.
    """
    try:
        import signal
        os.kill(pid, signal.SIGTERM)
    except:
        lg.exc()


def kill_process_win32(pid):
    """
    Call to system Windows API ``TerminateProcess`` method.
    """
    try:
        from win32api import TerminateProcess, OpenProcess, CloseHandle  # @UnresolvedImport
    except:
        lg.exc()
        return False
    try:
        PROCESS_TERMINATE = 1
        handle = OpenProcess(PROCESS_TERMINATE, False, pid)
    except:
        lg.out(2, 'bpio.kill_process_win32 can not open process %d' % pid)
        return False
    try:
        TerminateProcess(handle, -1)
    except:
        lg.out(2, 'bpio.kill_process_win32 can not terminate process %d' % pid)
        return False
    try:
        CloseHandle(handle)
    except:
        lg.exc()
        return False
    return True


def find_main_process(pid_file_path=None, extra_lookups=[], check_processid_file=True):
    """
    """
    appList = find_process([
        'bitdustnode.exe',
        'BitDustNode.exe',
        'BitDustConsole.exe',
        # 'bitdust.py',
        'regexp:^.*python.*bitdust.py$',
    ] + extra_lookups)
    if not appList:
        return []
    if not check_processid_file:
        return appList
    try:
        if not pid_file_path:
            from main import settings
            pid_file_path = os.path.join(settings.MetaDataDir(), 'processid')
        processid = int(ReadTextFile(pid_file_path))
    except:
        processid = None
    if not processid:
        return appList
    if processid not in appList:
        return []
    return [processid, ]

#------------------------------------------------------------------------------


def detect_number_of_cpu_cores():
    """
    Detects the number of effective CPUs in the system.
    """
    # for Linux, Unix and MacOS
    if hasattr(os, "sysconf"):
        if "SC_NPROCESSORS_ONLN" in os.sysconf_names:
            #Linux and Unix
            ncpus = os.sysconf("SC_NPROCESSORS_ONLN")
            if isinstance(ncpus, int) and ncpus > 0:
                return ncpus
        else:
            # MacOS X
            return int(os.popen2("sysctl -n hw.ncpu")[1].read())  # @UndefinedVariable
    # for Windows
    if "NUMBER_OF_PROCESSORS" in os.environ:
        ncpus = int(os.environ["NUMBER_OF_PROCESSORS"])
        if ncpus > 0:
            return ncpus
    # return the default value
    return 1
